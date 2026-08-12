import logging
import time

import jwt
from channels.db import database_sync_to_async

from eventyay.base.services.jitsi import (
    JitsiServerUnavailable,
    choose_server_for_room,
    normalize_server_url,
)
from eventyay.core.permissions import Permission
from eventyay.features.live.decorators import command, room_action
from eventyay.features.live.exceptions import ConsumerException
from eventyay.features.live.modules.base import BaseModule


logger = logging.getLogger(__name__)

JITSI_PARTICIPANT_TOOLBAR_BUTTONS = [
    "camera",
    "closedcaptions",
    "desktop",
    "filmstrip",
    "fullscreen",
    "hangup",
    "microphone",
    "noisesuppression",
    "profile",
    "raisehand",
    "select-background",
    "settings",
    "tileview",
    "toggle-camera",
    "videoquality",
]

JITSI_MODERATOR_TOOLBAR_BUTTONS = [
    *JITSI_PARTICIPANT_TOOLBAR_BUTTONS,
    "download",
    "etherpad",
    "feedback",
    "fodeviceselection",
    "help",
    "livestreaming",
    "mute-everyone",
    "mute-video-everyone",
    "participants-pane",
    "recording",
    "security",
    "shareaudio",
    "sharedvideo",
    "shortcuts",
    "stats",
    "whiteboard",
]

JITSI_INTERFACE_CONFIG_OVERWRITE = {
    "APP_NAME": "Eventyay Video",
    "NATIVE_APP_NAME": "Eventyay Video",
    "PROVIDER_NAME": "Eventyay",
    "BRAND_WATERMARK_LINK": "",
    "DEFAULT_LOGO_URL": "",
    "DEFAULT_WELCOME_PAGE_LOGO_URL": "",
    "JITSI_WATERMARK_LINK": "",
    "SHOW_BRAND_WATERMARK": False,
    "SHOW_CHROME_EXTENSION_BANNER": False,
    "SHOW_JITSI_WATERMARK": False,
    "SHOW_POWERED_BY": False,
    "SHOW_WATERMARK_FOR_GUESTS": False,
}

JITSI_JWT_LIFETIME_SECONDS = 10 * 60


def normalize_jitsi_room_name(event_id, room_id):
    return f"event-{event_id}-room-{room_id}"


def get_jitsi_room_display_name(room):
    return str(room.name or "room")


def build_jitsi_config_overwrite(
    module_config,
    is_moderator,
    room_display_name=None,
):
    config_overwrite = {
        "startWithAudioMuted": module_config.get(
            "start_with_audio_muted", False
        ),
        "startWithVideoMuted": module_config.get(
            "start_with_video_muted", False
        ),
        "enableUserRolesBasedOnToken": True,
        "readOnlyName": True,
        "enableClosePage": False,
        "disableInviteFunctions": True,
        "disablePolls": True,
        "hiddenPremeetingButtons": ["invite"],
        "disableSelfView": False,
        "breakoutRooms": {
            "hideAddRoomButton": True,
            "hideAutoAssignButton": True,
        },
        "remoteVideoMenu": {
            "disableKick": not is_moderator,
            "disableGrantModerator": not is_moderator,
        },
    }
    if room_display_name:
        config_overwrite["subject"] = room_display_name
    if is_moderator:
        config_overwrite["toolbarButtons"] = JITSI_MODERATOR_TOOLBAR_BUTTONS
    if not is_moderator:
        config_overwrite.update(
            {
                "disableRemoteMute": True,
                "disableModeratorIndicator": True,
                "participantsPane": {
                    "hideModeratorSettingsTab": True,
                    "hideMoreActionsButton": True,
                    "hideMuteAllButton": True,
                },
                "breakoutRooms": {
                    **config_overwrite["breakoutRooms"],
                    "hideJoinRoomButton": True,
                    "hideModeratorSettingsTab": True,
                    "hideMoreActionsButton": True,
                    "hideMuteAllButton": True,
                },
                "toolbarButtons": JITSI_PARTICIPANT_TOOLBAR_BUTTONS,
            }
        )
    return config_overwrite


def build_jitsi_interface_config_overwrite():
    return dict(JITSI_INTERFACE_CONFIG_OVERWRITE)


class JitsiModule(BaseModule):
    prefix = "jitsi"

    @command("room_config")
    @room_action(
        permission_required=Permission.ROOM_JITSI_JOIN,
        module_required="call.jitsi",
    )
    async def room_config(self, body):
        display_name = self.consumer.user.profile.get("display_name")
        if not display_name:
            raise ConsumerException("jitsi.join.missing_profile")

        try:
            server_model = await database_sync_to_async(choose_server_for_room)(
                room=self.room,
                prefer_server=self.module_config.get("prefer_server"),
            )
            if server_model is None:
                raise JitsiServerUnavailable
        except JitsiServerUnavailable:
            raise ConsumerException("jitsi.server_unavailable")

        server = normalize_server_url(server_model.url)
        domain = server["domain"] if server else None
        room_name = normalize_jitsi_room_name(self.consumer.event.id, self.room.id)
        room_display_name = get_jitsi_room_display_name(self.room)
        if not domain:
            raise ConsumerException("jitsi.missing_domain")
        if not server_model.app_id or not server_model.app_secret:
            raise ConsumerException("jitsi.missing_jwt_config")

        is_moderator = bool(await self.consumer.event.has_permission_async(
            user=self.consumer.user,
            permission=Permission.ROOM_JITSI_MODERATE,
            room=self.room,
        ))
        logger.info(
            "Jitsi room_config user=%s room=%s jitsi_room=%s moderator=%s domain=%s server=%s",
            self.consumer.user.pk,
            self.room.id,
            room_name,
            is_moderator,
            domain,
            server_model.pk,
        )

        result = {
            "domain": domain,
            "url": server["url"],
            "protocol": server["protocol"],
            "roomName": room_name,
            "roomDisplayName": room_display_name,
            "userInfo": {
                "displayName": display_name,
                "email": self.consumer.user.profile.get("email") or "",
            },
            "configOverwrite": build_jitsi_config_overwrite(
                self.module_config,
                is_moderator,
                room_display_name,
            ),
            "interfaceConfigOverwrite": build_jitsi_interface_config_overwrite(),
            "moderator": is_moderator,
        }

        result["jwt"] = self._build_jwt(
            server=server_model,
            domain=domain,
            room_name=room_name,
            display_name=display_name,
            is_moderator=is_moderator,
        )

        await self.consumer.send_success(result)

    def _build_jwt(
        self,
        server,
        domain,
        room_name,
        display_name,
        is_moderator,
    ):
        app_id = server.app_id
        app_secret = server.app_secret
        if not app_id or not app_secret:
            raise ConsumerException("jitsi.missing_jwt_config")

        now = int(time.time())
        payload = {
            "aud": "jitsi",
            "iss": app_id,
            "sub": domain,
            "room": room_name,
            "nbf": now - 10,
            "exp": now + JITSI_JWT_LIFETIME_SECONDS,
            "context": {
                "user": {
                    "id": str(self.consumer.user.pk),
                    "name": display_name,
                    "email": self.consumer.user.profile.get("email") or "",
                    "moderator": bool(is_moderator),
                    "affiliation": "owner" if is_moderator else "member",
                }
            },
        }
        headers = {}
        if server.key_id:
            headers["kid"] = server.key_id
        return jwt.encode(payload, app_secret, algorithm="HS256", headers=headers)

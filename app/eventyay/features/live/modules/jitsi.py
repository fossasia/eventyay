import logging
import time

import jwt
from channels.db import database_sync_to_async

from eventyay.base.services.jitsi import (
    JitsiServerUnavailable,
    choose_server_or_raise,
    normalize_server_url,
)
from eventyay.core.permissions import Permission
from eventyay.features.live.decorators import command, room_action
from eventyay.features.live.exceptions import ConsumerException
from eventyay.features.live.modules.base import BaseModule


logger = logging.getLogger(__name__)

JITSI_PARTICIPANT_TOOLBAR_BUTTONS = [
    "camera",
    "chat",
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

MAX_JITSI_ROOM_NAME_LENGTH = 200


def normalize_jitsi_room_name(configured_room_name, room_id):
    room_name = (configured_room_name or "").strip()
    if (
        not room_name
        or room_name == "*"
        or len(room_name) > MAX_JITSI_ROOM_NAME_LENGTH
    ):
        return f"room-{room_id}"
    return room_name


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
            server_model = await database_sync_to_async(choose_server_or_raise)(
                event=self.consumer.event,
                prefer_server=self.module_config.get("prefer_server"),
            )
        except JitsiServerUnavailable:
            raise ConsumerException("jitsi.server_unavailable")

        server = normalize_server_url(server_model.url)
        domain = server["domain"] if server else None
        room_name = normalize_jitsi_room_name(
            self.module_config.get("room_name"),
            self.room.id,
        )
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

        config_overwrite = {
            "startWithAudioMuted": self.module_config.get(
                "start_with_audio_muted", False
            ),
            "startWithVideoMuted": self.module_config.get(
                "start_with_video_muted", False
            ),
            "enableUserRolesBasedOnToken": True,
            "remoteVideoMenu": {
                "disableKick": not is_moderator,
                "disableGrantModerator": not is_moderator,
            },
        }
        if not is_moderator:
            config_overwrite.update(
                {
                    "disableRemoteMute": True,
                    "disableInviteFunctions": True,
                    "disableModeratorIndicator": True,
                    "toolbarButtons": JITSI_PARTICIPANT_TOOLBAR_BUTTONS,
                }
            )

        result = {
            "domain": domain,
            "url": server["url"],
            "protocol": server["protocol"],
            "roomName": room_name,
            "userInfo": {
                "displayName": display_name,
                "email": self.consumer.user.profile.get("email") or "",
            },
            "configOverwrite": config_overwrite,
            "interfaceConfigOverwrite": {},
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

    def _build_jwt(self, server, domain, room_name, display_name, is_moderator):
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
            "exp": now + 60 * 60,
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

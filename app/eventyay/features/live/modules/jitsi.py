import time
from urllib.parse import urlparse

import jwt

from eventyay.core.permissions import Permission
from eventyay.features.live.decorators import command, room_action
from eventyay.features.live.exceptions import ConsumerException
from eventyay.features.live.modules.base import BaseModule


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

        domain = self._normalize_domain(self.module_config.get("domain"))
        room_name = self.module_config.get("room_name") or f"room-{self.room.id}"
        if not domain:
            raise ConsumerException("jitsi.missing_domain")

        is_moderator = await self.consumer.event.has_permission_async(
            user=self.consumer.user,
            permission=Permission.ROOM_JITSI_MODERATE,
            room=self.room,
        )

        result = {
            "domain": domain,
            "roomName": room_name,
            "userInfo": {
                "displayName": display_name,
                "email": self.consumer.user.profile.get("email") or "",
            },
            "configOverwrite": {
                "startWithAudioMuted": self.module_config.get(
                    "start_with_audio_muted", False
                ),
                "startWithVideoMuted": self.module_config.get(
                    "start_with_video_muted", False
                ),
            },
            "interfaceConfigOverwrite": {},
            "moderator": is_moderator,
        }

        if self.module_config.get("jwt_enabled", True):
            result["jwt"] = self._build_jwt(
                domain=domain,
                room_name=room_name,
                display_name=display_name,
                is_moderator=is_moderator,
            )

        await self.consumer.send_success(result)

    def _build_jwt(self, domain, room_name, display_name, is_moderator):
        app_id = self.module_config.get("app_id")
        app_secret = self.module_config.get("app_secret")
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
                }
            },
        }
        headers = {}
        if self.module_config.get("key_id"):
            headers["kid"] = self.module_config["key_id"]
        return jwt.encode(payload, app_secret, algorithm="HS256", headers=headers)

    @staticmethod
    def _normalize_domain(domain):
        if not domain:
            return None
        domain = domain.strip()
        if "://" not in domain:
            return domain.strip("/")
        parsed = urlparse(domain)
        return parsed.netloc or None

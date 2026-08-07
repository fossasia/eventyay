import hashlib
import json
import secrets

from channels.db import database_sync_to_async
from django.conf import settings
from redis.asyncio.lock import Lock
from sentry_sdk import capture_exception

from eventyay.base.models import JanusServer
from eventyay.base.services import turn
from eventyay.base.services.janus import (
    JanusError,
    JanusPluginError,
    choose_server,
    create_videoroom,
    videoroom_add_token_if_exists,
)
from eventyay.base.services.roulette import is_member_of_roulette_call
from eventyay.base.services.user import get_public_user
from eventyay.core.permissions import Permission
from eventyay.core.utils.redis import aredis
from eventyay.features.live.decorators import command, require_event_permission, room_action
from eventyay.features.live.exceptions import ConsumerException
from eventyay.features.live.modules.base import BaseModule


class JanusCallModule(BaseModule):
    prefix = "januscall"

    @database_sync_to_async
    def _servers(self):
        return choose_server(self.consumer.event), turn.choose_server(self.consumer.event)

    @command("room_url")
    @room_action(
        permission_required=Permission.ROOM_JANUSCALL_JOIN,
        module_required="call.janus",
    )
    async def room_url(self, body):
        room_data = await self._get_or_create_janus_room(
            f"room:{self.room.id}", audiobridge=True
        )
        await self.consumer.send_success(room_data)

    @command("channel_url")
    async def channel_url(self, body):
        channel_id = body.get("channel")
        if not await self.consumer.user.is_member_of_channel_async(channel_id):
            raise ConsumerException("janus.denied")
        room_data = await self._get_or_create_janus_room(f"channel:{channel_id}")
        await self.consumer.send_success(room_data)

    @command("roulette_url")
    async def roulette_url(self, body):
        call_id = body.get("call_id")
        if not await is_member_of_roulette_call(call_id, self.consumer.user):
            raise ConsumerException("janus.denied")
        room_data = await self._get_or_create_janus_room(f"roulette:{call_id}")
        await self.consumer.send_success(room_data)

    async def _get_or_create_janus_room(self, redis_key, audiobridge=False):
        if not self.consumer.user.profile.get("display_name"):
            raise ConsumerException("janus.join.missing_profile")

        cache_key = f"januscall:{redis_key}"
        user_secret_token = hashlib.sha256(
            f"januscall:usersecret:{settings.SECRET_KEY}:{self.consumer.user.pk}".encode()
        ).hexdigest()
        async with aredis() as redis:
            async with Lock(
                redis,
                name=f"januscall:lock:{redis_key}",
                timeout=90,
                blocking_timeout=90,
            ):
                room_data = await redis.get(cache_key)

                if room_data:
                    try:
                        room_data = json.loads(room_data.decode())
                        server = await database_sync_to_async(
                            JanusServer.objects.filter(active=True).get
                        )(url=room_data["server"])
                        if room_data.get("audiobridge", False) != audiobridge:
                            room_data = None
                        elif not await videoroom_add_token_if_exists(
                            server,
                            room_data,
                            user_secret_token,
                            audiobridge=room_data.get("audiobridge", False),
                        ):
                            room_data = None
                    except (JanusServer.DoesNotExist, KeyError, json.JSONDecodeError):
                        await redis.delete(cache_key)
                        room_data = None
                    except JanusError as e:
                        await redis.delete(cache_key)
                        room_data = None
                        if settings.SENTRY_DSN:
                            capture_exception(e)

                    if room_data is None:
                        await redis.delete(cache_key)

                if not room_data:
                    janus_server, turn_server = await self._servers()
                    room_data = await self._create_janus_room(
                        janus_server, audiobridge, user_secret_token
                    )
                    await redis.setex(cache_key, 3600 * 24, json.dumps(room_data))
                else:
                    await redis.expire(cache_key, 3600 * 24)
                    turn_server = await database_sync_to_async(turn.choose_server)(
                        self.consumer.event
                    )

            user_id = self._new_janus_room_id()
            screenshare_user_id = self._new_janus_room_id()
            await redis.setex(
                f"januscall:user:{user_id}",
                3600 * 24,
                str(self.consumer.user.pk),
            )
            await redis.setex(
                f"januscall:user:{screenshare_user_id}",
                3600 * 24,
                str(self.consumer.user.pk),
            )

        iceServers = turn_server.get_ice_servers() if turn_server else []
        return {
            "token": user_secret_token,
            "sessionId": user_id,
            "screenShareSessionId": screenshare_user_id,
            "server": room_data["server"],
            "roomId": room_data["roomId"],
            "iceServers": iceServers,
        }

    async def _create_janus_room(self, janus_server, audiobridge, user_secret_token):
        for attempt in range(3):
            try:
                return await create_videoroom(
                    janus_server,
                    room_id=self._new_janus_room_id(),
                    audiobridge=audiobridge,
                    init_token=user_secret_token,
                )
            except JanusPluginError as e:
                if "already exists" in str(e).lower() and attempt < 2:
                    continue
                self._capture_janus_exception(e)
                raise ConsumerException("janus.failed", "Could not create a video session")
            except JanusError as e:
                self._capture_janus_exception(e)
                raise ConsumerException("janus.failed", "Could not create a video session")

        raise ConsumerException("janus.failed", "Could not create a video session")

    @staticmethod
    def _new_janus_room_id():
        return secrets.randbelow(2_147_483_647) + 1

    @staticmethod
    def _capture_janus_exception(exception):
        if settings.SENTRY_DSN:
            capture_exception(exception)

    @command("identify")
    @require_event_permission(Permission.EVENT_VIEW)
    async def identify(self, body):
        async with aredis() as redis:
            sessionid = str(body.get("id", "")).split("_")[0]
            userid = await redis.get(f"januscall:user:{sessionid}")
            if userid:
                user = await get_public_user(
                    self.consumer.event.id,
                    userid.decode(),
                    include_admin_info=await self.consumer.event.has_permission_async(
                        user=self.consumer.user,
                        permission=Permission.EVENT_USERS_MANAGE,
                    ),
                    trait_badges_map=self.consumer.event.config.get("trait_badges_map"),
                )
                if user:
                    await self.consumer.send_success(user)
                    return
        await self.consumer.send_error(code="user.not_found")

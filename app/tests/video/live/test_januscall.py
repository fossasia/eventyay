import json
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from tests.utils import get_token
from venueless.core.models import JanusServer, Room
from venueless.core.utils.redis import aredis
from venueless.routing import application


@asynccontextmanager
async def world_communicator(client_id=None, token=None, room=None, first=True):
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    if token:
        await communicator.send_json_to(["authenticate", {"token": token}])
    else:
        await communicator.send_json_to(
            ["authenticate", {"client_id": client_id or str(uuid.uuid4())}]
        )
    response = await communicator.receive_json_from()
    assert response[0] == "authenticated", response
    communicator.context = response[1]
    assert "world.config" in response[1], response
    if room:
        await communicator.send_json_to(["room.enter", 123, {"room": str(room.pk)}])
        response = await communicator.receive_json_from()
        assert response[0] == "success"
        if first:
            await communicator.receive_json_from()  # world.user_count_change
    try:
        yield communicator
    finally:
        await communicator.disconnect()


@pytest.fixture
async def janus_room(world):
    return await database_sync_to_async(Room.objects.create)(
        event=world,
        name="Janus room",
        module_config=[{"type": "call.janus", "config": {}}],
    )


@pytest.fixture
async def janus_server(world):
    return await database_sync_to_async(JanusServer.objects.create)(
        url="wss://janus.example.test/ws",
        room_create_key="room-secret",
        active=True,
    )


async def store_janus_room(room, janus_server, target_user_id="target-user"):
    async with aredis() as redis:
        await redis.set(
            f"januscall:room:{room.pk}",
            json.dumps(
                {
                    "server": janus_server.url,
                    "roomId": 987654,
                    "seed": "seed123",
                    "audiobridge": True,
                }
            ),
        )
        await redis.set(f"januscall:room:{room.pk}:feed:111", target_user_id)
        await redis.sadd(f"januscall:room:{room.pk}:user:{target_user_id}:feeds", "111")
        await redis.sadd(f"januscall:room:{room.pk}:feeds", "111")


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_room_url_exposes_moderator_role(janus_room, world, monkeypatch):
    async def fake_room_data(self, redis_key, audiobridge=False):
        return {
            "token": "token",
            "sessionId": 1,
            "audioSessionId": 1,
            "videoSessionId": 2,
            "screenShareSessionId": 3,
            "server": "wss://janus.example.test/ws",
            "roomId": 4,
            "iceServers": [],
        }

    monkeypatch.setattr(
        "eventyay.features.live.modules.januscall.JanusCallModule._get_or_create_janus_room",
        fake_room_data,
    )

    async with world_communicator(token=get_token(world, ["moderator"])) as c:
        await c.send_json_to(["januscall.room_url", 124, {"room": str(janus_room.pk)}])
        response = await c.receive_json_from()
        assert response[0] == "success"
        assert response[2]["isModerator"] is True

    async with world_communicator(token=get_token(world, ["admin"])) as c:
        await c.send_json_to(["januscall.room_url", 125, {"room": str(janus_room.pk)}])
        response = await c.receive_json_from()
        assert response[0] == "success"
        assert response[2]["isModerator"] is True

    await database_sync_to_async(world.refresh_from_db)()
    old_roles = world.roles
    old_roles["moderator"] = [
        permission
        for permission in old_roles["moderator"]
        if getattr(permission, "value", permission) != "room:januscall.moderate"
    ]
    await database_sync_to_async(world.save)(update_fields=["roles"])

    async with world_communicator(token=get_token(world, ["moderator"])) as c:
        await c.send_json_to(["januscall.room_url", 126, {"room": str(janus_room.pk)}])
        response = await c.receive_json_from()
        assert response[0] == "success"
        assert response[2]["isModerator"] is True

    old_roles["moderator"] = [
        permission
        for permission in old_roles["moderator"]
        if getattr(permission, "value", permission) != "room:bbb.moderate"
    ]
    old_roles["moderator"].append("room:update")
    await database_sync_to_async(world.save)(update_fields=["roles"])

    async with world_communicator(token=get_token(world, ["moderator"])) as c:
        await c.send_json_to(["januscall.room_url", 127, {"room": str(janus_room.pk)}])
        response = await c.receive_json_from()
        assert response[0] == "success"
        assert response[2]["isModerator"] is True

    async with world_communicator() as c:
        await c.send_json_to(["januscall.room_url", 128, {"room": str(janus_room.pk)}])
        response = await c.receive_json_from()
        assert response[0] == "success"
        assert response[2]["isModerator"] is False


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_moderator_can_mute_participant(janus_room, janus_server, world, monkeypatch):
    await store_janus_room(janus_room, janus_server)
    moderate_mock = AsyncMock()
    monkeypatch.setattr(
        "eventyay.features.live.modules.januscall.videoroom_moderate",
        moderate_mock,
    )

    async with world_communicator(room=janus_room, first=True) as target:
        async with world_communicator(
            room=janus_room,
            token=get_token(world, ["moderator"]),
            first=False,
        ) as moderator:
            await target.receive_json_from()  # world.user_count_change for moderator
            await moderator.send_json_to(
                [
                    "januscall.mute_participant",
                    126,
                    {"room": str(janus_room.pk), "target_feed_id": "111"},
                ]
            )
            response = await moderator.receive_json_from()
            assert response == [
                "success",
                126,
                {
                    "action": "mute_participant",
                    "target_user": "target-user",
                    "target_feed_id": "111",
                },
            ]
            event = await target.receive_json_from()
            assert event[0] == "januscall.moderation_action"
            assert event[1]["action"] == "mute_participant"
            assert event[1]["target_user"] == "target-user"

    moderate_mock.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_moderator_can_end_meeting_for_all(
    janus_room, janus_server, world, monkeypatch
):
    await store_janus_room(janus_room, janus_server)
    kick_mock = AsyncMock()
    monkeypatch.setattr(
        "eventyay.features.live.modules.januscall.videoroom_kick",
        kick_mock,
    )

    async with world_communicator(room=janus_room, first=True) as target:
        async with world_communicator(
            room=janus_room,
            token=get_token(world, ["moderator"]),
            first=False,
        ) as moderator:
            await target.receive_json_from()  # world.user_count_change for moderator
            await moderator.send_json_to(
                ["januscall.end_meeting", 129, {"room": str(janus_room.pk)}]
            )
            response = await moderator.receive_json_from()
            assert response == ["success", 129, {"action": "end_meeting"}]
            event = await target.receive_json_from()
            assert event[0] == "januscall.moderation_action"
            assert event[1]["action"] == "end_meeting"
            assert event[1]["moderator"] == str(moderator.context["user.config"]["id"])
            assert "target_user" not in event[1]

    kick_mock.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_moderator_action_uses_existing_feed_mapping_without_janus_admin_data(
    janus_room, world, monkeypatch
):
    async with aredis() as redis:
        await redis.set("januscall:user:222", "target-user")
    moderate_mock = AsyncMock()
    monkeypatch.setattr(
        "eventyay.features.live.modules.januscall.videoroom_moderate",
        moderate_mock,
    )

    async with world_communicator(room=janus_room, first=True) as target:
        async with world_communicator(
            room=janus_room,
            token=get_token(world, ["moderator"]),
            first=False,
        ) as moderator:
            await target.receive_json_from()  # world.user_count_change for moderator
            await moderator.send_json_to(
                [
                    "januscall.mute_participant",
                    128,
                    {"room": str(janus_room.pk), "target_feed_id": "222"},
                ]
            )
            response = await moderator.receive_json_from()
            assert response == [
                "success",
                128,
                {
                    "action": "mute_participant",
                    "target_user": "target-user",
                    "target_feed_id": "222",
                },
            ]
            event = await target.receive_json_from()
            assert event[0] == "januscall.moderation_action"
            assert event[1]["target_user"] == "target-user"

    moderate_mock.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_non_moderator_cannot_mute_participant(
    janus_room, janus_server, monkeypatch
):
    await store_janus_room(janus_room, janus_server)
    moderate_mock = AsyncMock()
    monkeypatch.setattr(
        "eventyay.features.live.modules.januscall.videoroom_moderate",
        moderate_mock,
    )

    async with world_communicator(room=janus_room) as c:
        await c.send_json_to(
            [
                "januscall.mute_participant",
                127,
                {"room": str(janus_room.pk), "target_feed_id": "111"},
            ]
        )
        response = await c.receive_json_from()
        assert response == [
            "error",
            127,
            {"code": "protocol.denied", "message": "Permission denied."},
        ]

    moderate_mock.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_non_moderator_cannot_end_meeting(janus_room, janus_server, monkeypatch):
    await store_janus_room(janus_room, janus_server)
    kick_mock = AsyncMock()
    monkeypatch.setattr(
        "eventyay.features.live.modules.januscall.videoroom_kick",
        kick_mock,
    )

    async with world_communicator(room=janus_room) as c:
        await c.send_json_to(
            ["januscall.end_meeting", 130, {"room": str(janus_room.pk)}]
        )
        response = await c.receive_json_from()
        assert response == [
            "error",
            130,
            {"code": "protocol.denied", "message": "Permission denied."},
        ]

    kick_mock.assert_not_awaited()

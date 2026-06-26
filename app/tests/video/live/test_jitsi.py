import uuid
from contextlib import asynccontextmanager

import jwt
import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from venueless.core.models import Room, User
from venueless.routing import application


@asynccontextmanager
async def world_communicator(named=True):
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    await communicator.send_json_to(["authenticate", {"client_id": str(uuid.uuid4())}])
    response = await communicator.receive_json_from()
    assert response[0] == "authenticated", response
    communicator.context = response[1]
    if named:
        await communicator.send_json_to(
            ["user.update", 123, {"profile": {"display_name": "Foo Fighter"}}]
        )
        await communicator.receive_json_from()
    try:
        yield communicator
    finally:
        await communicator.disconnect()


@database_sync_to_async
def create_jitsi_room(world, *, trait_grants=None, jwt_enabled=True):
    return Room.objects.create(
        event=world,
        name="Jitsi Room",
        sorting_priority=100,
        trait_grants=trait_grants or {"viewer": [], "participant": []},
        module_config=[
            {
                "type": "call.jitsi",
                "config": {
                    "domain": "https://meet.example.org/",
                    "room_name": "eventyay-test-room",
                    "jwt_enabled": jwt_enabled,
                    "app_id": "eventyay",
                    "app_secret": "test-secret",
                    "key_id": "eventyay-key",
                    "start_with_audio_muted": True,
                    "start_with_video_muted": False,
                },
            }
        ],
    )


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_login_required(world):
    jitsi_room = await create_jitsi_room(world)
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    try:
        await communicator.send_json_to(
            ["jitsi.room_config", 123, {"room": str(jitsi_room.pk)}]
        )
        response = await communicator.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "protocol.unauthenticated"
    finally:
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_wrong_room(chat_room):
    async with world_communicator() as c:
        await c.send_json_to(["jitsi.room_config", 123, {"room": str(chat_room.pk)}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "room.unknown"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_unnamed_user_denied(world):
    jitsi_room = await create_jitsi_room(world)
    async with world_communicator(named=False) as c:
        await c.send_json_to(["jitsi.room_config", 123, {"room": str(jitsi_room.pk)}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "jitsi.join.missing_profile"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_missing_permission(world):
    jitsi_room = await create_jitsi_room(world, trait_grants={"participant": ["foo"]})
    async with world_communicator() as c:
        await c.send_json_to(["jitsi.room_config", 123, {"room": str(jitsi_room.pk)}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "protocol.denied"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_attendee_room_config(world):
    jitsi_room = await create_jitsi_room(world)
    async with world_communicator() as c:
        await c.send_json_to(["jitsi.room_config", 123, {"room": str(jitsi_room.pk)}])
        response = await c.receive_json_from()

    assert response[0] == "success"
    data = response[2]
    assert data["domain"] == "meet.example.org"
    assert data["roomName"] == "eventyay-test-room"
    assert data["userInfo"]["displayName"] == "Foo Fighter"
    assert data["moderator"] is False
    assert data["configOverwrite"] == {
        "startWithAudioMuted": True,
        "startWithVideoMuted": False,
    }
    claims = jwt.decode(
        data["jwt"],
        "test-secret",
        algorithms=["HS256"],
        audience="jitsi",
    )
    assert claims["iss"] == "eventyay"
    assert claims["sub"] == "meet.example.org"
    assert claims["room"] == "eventyay-test-room"
    assert claims["context"]["user"]["moderator"] is False
    assert jwt.get_unverified_header(data["jwt"])["kid"] == "eventyay-key"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_moderator_room_config(world):
    jitsi_room = await create_jitsi_room(
        world, trait_grants={"viewer": [], "participant": [], "speaker": []}
    )
    async with world_communicator() as c:
        await c.send_json_to(["jitsi.room_config", 123, {"room": str(jitsi_room.pk)}])
        response = await c.receive_json_from()

    assert response[0] == "success"
    data = response[2]
    claims = jwt.decode(
        data["jwt"],
        "test-secret",
        algorithms=["HS256"],
        audience="jitsi",
    )
    assert data["moderator"] is True
    assert claims["context"]["user"]["moderator"] is True


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_silenced_user_denied(world):
    jitsi_room = await create_jitsi_room(world)
    async with world_communicator() as c:
        user = await database_sync_to_async(User.objects.get)()
        user.moderation_state = User.ModerationState.SILENCED
        await database_sync_to_async(user.save)()
        await c.send_json_to(["jitsi.room_config", 123, {"room": str(jitsi_room.pk)}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "protocol.denied"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_jitsi_secret_not_disclosed(world):
    jitsi_room = await create_jitsi_room(world)
    async with world_communicator() as c:
        room = next(
            room
            for room in c.context["world.config"]["rooms"]
            if room["id"] == str(jitsi_room.id)
        )

    assert room["modules"][0]["type"] == "call.jitsi"
    assert "app_secret" not in room["modules"][0]["config"]

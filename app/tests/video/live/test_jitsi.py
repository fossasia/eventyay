import uuid
from contextlib import asynccontextmanager

import jwt
import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from eventyay.base.models import JitsiServer
from eventyay.base.services.jitsi import choose_server
from tests.utils import get_token
from venueless.core.models import Room, User
from venueless.routing import application


@asynccontextmanager
async def world_communicator(named=True, token=None):
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    if token:
        await communicator.send_json_to(["authenticate", {"token": token}])
    else:
        await communicator.send_json_to(
            ["authenticate", {"client_id": str(uuid.uuid4())}]
        )
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
def create_jitsi_room(
    world,
    *,
    trait_grants=None,
    with_server=True,
    prefer_server="",
    server_url="https://meet.example.org/",
):
    if with_server:
        JitsiServer.objects.create(
            url=server_url,
            app_id="eventyay",
            app_secret="test-secret",
            key_id="eventyay-key",
        )
    return Room.objects.create(
        event=world,
        name="Jitsi Room",
        sorting_priority=100,
        trait_grants=trait_grants or {"viewer": [], "participant": []},
        module_config=[
            {
                "type": "call.jitsi",
                "config": {
                    "room_name": "eventyay-test-room",
                    "prefer_server": prefer_server,
                    "start_with_audio_muted": True,
                    "start_with_video_muted": False,
                },
            }
        ],
    )


@pytest.mark.django_db
def test_preferred_server_url_is_normalized(world):
    preferred = JitsiServer.objects.create(
        url="https://meet.example.org",
        app_id="eventyay",
        app_secret="test-secret",
    )
    JitsiServer.objects.create(
        url="https://other.example.org",
        app_id="eventyay",
        app_secret="test-secret",
    )

    assert choose_server(world, prefer_server="https://meet.example.org/") == preferred


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
    assert data["url"] == "https://meet.example.org"
    assert data["protocol"] == "https:"
    assert data["roomName"] == "eventyay-test-room"
    assert data["userInfo"]["displayName"] == "Foo Fighter"
    assert data["moderator"] is False
    assert data["configOverwrite"] == {
        "startWithAudioMuted": True,
        "startWithVideoMuted": False,
        "enableUserRolesBasedOnToken": True,
        "remoteVideoMenu": {
            "disableKick": True,
            "disableGrantModerator": True,
        },
        "disableRemoteMute": True,
        "disableInviteFunctions": True,
        "toolbarButtons": [
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
        ],
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
    assert claims["context"]["user"]["affiliation"] == "member"
    assert jwt.get_unverified_header(data["jwt"])["kid"] == "eventyay-key"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_speaker_room_config_is_not_moderator(world):
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
    assert data["moderator"] is False
    assert data["configOverwrite"]["remoteVideoMenu"] == {
        "disableKick": True,
        "disableGrantModerator": True,
    }
    assert data["configOverwrite"]["disableRemoteMute"] is True
    assert data["configOverwrite"]["disableInviteFunctions"] is True
    assert "toolbarButtons" in data["configOverwrite"]
    assert claims["context"]["user"]["moderator"] is False
    assert claims["context"]["user"]["affiliation"] == "member"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_moderator_room_config(world):
    jitsi_room = await create_jitsi_room(
        world, trait_grants={"viewer": [], "participant": [], "moderator": []}
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
    assert data["configOverwrite"]["remoteVideoMenu"] == {
        "disableKick": False,
        "disableGrantModerator": False,
    }
    assert "toolbarButtons" not in data["configOverwrite"]
    assert "disableRemoteMute" not in data["configOverwrite"]
    assert claims["context"]["user"]["moderator"] is True
    assert claims["context"]["user"]["affiliation"] == "owner"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_jitsi_server_required(world):
    jitsi_room = await create_jitsi_room(world, with_server=False)
    async with world_communicator() as c:
        await c.send_json_to(["jitsi.room_config", 123, {"room": str(jitsi_room.pk)}])
        response = await c.receive_json_from()

    assert response[0] == "error"
    assert response[2]["code"] == "jitsi.server_unavailable"


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
    assert "domain" not in room["modules"][0]["config"]
    assert "jwt_enabled" not in room["modules"][0]["config"]
    assert "app_id" not in room["modules"][0]["config"]
    assert "key_id" not in room["modules"][0]["config"]
    assert "app_secret" not in room["modules"][0]["config"]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_jitsi_secret_not_disclosed_in_admin_config(world):
    jitsi_room = await create_jitsi_room(world)
    async with world_communicator(token=get_token(world, ["admin"])) as c:
        await c.send_json_to(["room.config.get", 123, {"room": str(jitsi_room.pk)}])
        response = await c.receive_json_from()

    assert response[0] == "success"
    assert response[2]["module_config"][0]["type"] == "call.jitsi"
    assert "domain" not in response[2]["module_config"][0]["config"]
    assert "jwt_enabled" not in response[2]["module_config"][0]["config"]
    assert "app_id" not in response[2]["module_config"][0]["config"]
    assert "key_id" not in response[2]["module_config"][0]["config"]
    assert "app_secret" not in response[2]["module_config"][0]["config"]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_jitsi_room_create_uses_video_channel_permission(world):
    async with world_communicator(
        token=get_token(world, ["video_channel_manager"])
    ) as c:
        await c.send_json_to(
            [
                "room.create",
                123,
                {
                    "name": "Created Jitsi Room",
                    "description": "",
                    "modules": [
                        {
                            "type": "call.jitsi",
                            "config": {
                                "room_name": "created-jitsi-room",
                                "prefer_server": "https://meet.example.org",
                            },
                        }
                    ],
                },
            ]
        )
        response = await c.receive_json_from()

    assert response[0] == "success"
    assert response[2]["room"]

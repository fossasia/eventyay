import os
from types import SimpleNamespace

import jwt
import pytest
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from django.core.exceptions import ValidationError
from django.utils import timezone

from eventyay.base.models import Event, JitsiServer, Organizer, Room, User
from eventyay.base.models.cache import VersionedModel
from eventyay.base.services import event as event_service
from eventyay.base.services.jitsi import (
    choose_server,
    choose_server_for_room,
    normalize_server_url,
)
from eventyay.core.permissions import Permission
from eventyay.features.live.exceptions import ConsumerException
from eventyay.features.live.modules.jitsi import (
    JITSI_JWT_LIFETIME_SECONDS,
    JitsiModule,
    normalize_jitsi_room_name,
)


@pytest.fixture(autouse=True)
def use_real_redis_for_versioned_model_saves(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(
        VersionedModel,
        "_set_cache_version_sync",
        lambda self: None,
    )


class DummyConsumer:
    def __init__(self, event, room, user, *, moderator=False):
        async def has_permission_async(**kwargs):
            if kwargs["permission"] == Permission.ROOM_JITSI_JOIN:
                return True
            if kwargs["permission"] == Permission.ROOM_JITSI_MODERATE:
                return moderator
            return False

        self.event = SimpleNamespace(
            id=event.id,
            has_permission_async=has_permission_async,
        )
        self.room_cache = {str(room.pk): room}
        self.user = user
        self.content = ["jitsi.room_config", 123, {}]
        self.response = None

    async def send_success(self, data=None, close=False):
        self.response = data or {}


class ChannelLayer:
    async def group_send(self, *args, **kwargs):
        pass


def _patch_room_creation(monkeypatch):
    created = {}

    async def fake_create_room(data, with_channel=False, **kwargs):
        created["data"] = data
        created["with_channel"] = with_channel
        channel = SimpleNamespace(id="channel-id") if with_channel else None
        return SimpleNamespace(id="room-id"), channel

    monkeypatch.setattr(event_service, "_create_room", fake_create_room)
    monkeypatch.setattr(
        event_service, "get_channel_layer", lambda: ChannelLayer()
    )
    return created


def _event_with_allowed_permissions(*allowed_permissions):
    async def has_permission_async(**kwargs):
        return kwargs["permission"] in allowed_permissions

    return SimpleNamespace(
        id="event-id",
        config={"bbb_defaults": {"logoutUrl": "https://bbb.example/logout"}},
        has_permission_async=has_permission_async,
    )


def create_event(slug):
    organizer = Organizer.objects.create(
        name=f"Test Organizer {slug}",
        slug=f"testorg-{slug}",
    )
    return Event.objects.create(
        organizer=organizer,
        name="Test Event",
        slug=slug,
        date_from=timezone.now(),
        date_to=timezone.now(),
        currency="USD",
        locale="en",
        is_public=True,
        live=True,
        email="test@example.org",
    )


def create_jitsi_context(
    *,
    slug,
    profile,
    traits=None,
    room_config=None,
    role=None,
):
    os.environ.pop("PYTEST_CURRENT_TEST", None)
    event = create_event(slug)
    room = Room.objects.create(
        event=event,
        name="Jitsi room",
        module_config=[
            {
                "type": "call.jitsi",
                "config": room_config or {},
            }
        ],
    )
    server = JitsiServer.objects.create(
        url="https://meet.example.org",
        app_id="eventyay",
        app_secret="topsecret",
        key_id="key-1",
    )
    user = User.objects.create(
        event=event,
        email=f"{slug}@example.org",
        profile=profile,
        traits=traits or [],
    )
    if role:
        room.role_grants.create(event=event, user=user, role=role)
    return event, room, server, user


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "meet.example.org",
            {
                "domain": "meet.example.org",
                "url": "https://meet.example.org",
                "protocol": "https:",
            },
        ),
        (
            "HTTP://Meet.Example.Org/path?ignored=1",
            {
                "domain": "meet.example.org",
                "url": "http://meet.example.org",
                "protocol": "http:",
            },
        ),
        ("https://", None),
        ("", None),
    ],
)
def test_normalize_server_url(value, expected):
    assert normalize_server_url(value) == expected


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("Main Stage", "Main Stage"),
        ("", "room-42"),
        ("*", "room-42"),
        ("x" * 201, "room-42"),
    ],
)
def test_normalize_jitsi_room_name(configured, expected):
    assert normalize_jitsi_room_name(configured, 42) == expected


@pytest.mark.django_db
def test_choose_server_prefers_event_exclusive(event):
    shared = JitsiServer.objects.create(
        url="https://shared.example.org",
        app_id="app",
        app_secret="secret",
    )
    event_exclusive = JitsiServer.objects.create(
        url="https://event.example.org",
        app_id="app",
        app_secret="secret",
        event_exclusive=event,
    )

    assert choose_server(event) == event_exclusive
    assert choose_server(event, prefer_server=shared.url) == shared


@pytest.mark.django_db
def test_choose_server_for_room_persists_selected_server(event):
    room = Room.objects.create(
        event=event,
        name="Jitsi room",
        module_config=[{"type": "call.jitsi", "config": {}}],
    )
    server = JitsiServer.objects.create(
        url="https://meet.example.org",
        app_id="app",
        app_secret="secret",
    )

    assert choose_server_for_room(room) == server

    room.refresh_from_db()
    assert room.module_config[0]["config"]["selected_server_url"] == server.url


@pytest.mark.django_db
def test_choose_server_for_room_without_jitsi_module_skips_sticky_write(event):
    room = Room.objects.create(
        event=event,
        name="Plain room",
        module_config=[{"type": "chat.native", "config": {}}],
    )
    server = JitsiServer.objects.create(
        url="https://meet.example.org",
        app_id="app",
        app_secret="secret",
    )

    assert choose_server_for_room(room) == server

    room.refresh_from_db()
    assert room.module_config == [{"type": "chat.native", "config": {}}]


def test_create_jitsi_room_requires_jitsi_create_permission(monkeypatch):
    _patch_room_creation(monkeypatch)
    event = _event_with_allowed_permissions(Permission.EVENT_ROOMS_CREATE_BBB)

    with pytest.raises(ValidationError) as excinfo:
        async_to_sync(event_service.create_room)(
            event,
            {
                "name": "Jitsi room",
                "description": "",
                "modules": [{"type": "call.jitsi", "config": {}}],
            },
            object(),
        )

    assert excinfo.value.code == "denied"


def test_create_jitsi_room_sanitizes_client_config(monkeypatch):
    created = _patch_room_creation(monkeypatch)
    event = _event_with_allowed_permissions(
        Permission.EVENT_ROOMS_CREATE_JITSI
    )

    result = async_to_sync(event_service.create_room)(
        event,
        {
            "name": "Jitsi room",
            "description": "",
            "modules": [
                {
                    "type": "call.jitsi",
                    "config": {
                        "room_name": "Main Stage",
                        "prefer_server": "https://meet.example.org",
                        "start_with_audio_muted": True,
                        "start_with_video_muted": True,
                        "domain": "evil.example.org",
                        "app_id": "client-app",
                        "app_secret": "client-secret",
                        "key_id": "client-key",
                    },
                }
            ],
        },
        object(),
    )

    assert result == {"room": "room-id", "channel": None}
    assert created["with_channel"] is False
    assert created["data"]["module_config"] == [
        {
            "type": "call.jitsi",
            "config": {
                "room_name": "Main Stage",
                "prefer_server": "https://meet.example.org",
                "start_with_audio_muted": True,
                "start_with_video_muted": True,
            },
        }
    ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_room_config_returns_participant_jwt():
    event, room, server, user = await database_sync_to_async(
        create_jitsi_context
    )(
        slug="jitsi-participant",
        profile={"display_name": "Viewer", "email": "viewer@example.org"},
        room_config={
            "room_name": "Main Stage",
            "start_with_audio_muted": True,
            "start_with_video_muted": True,
        },
    )
    consumer = DummyConsumer(event, room, user)

    await JitsiModule(consumer).room_config({"room": str(room.pk)})

    payload = jwt.decode(
        consumer.response["jwt"],
        server.app_secret,
        algorithms=["HS256"],
        audience="jitsi",
        issuer=server.app_id,
    )
    assert consumer.response["domain"] == "meet.example.org"
    assert consumer.response["roomName"] == "Main Stage"
    assert consumer.response["moderator"] is False
    assert consumer.response["configOverwrite"]["toolbarButtons"]
    assert payload["sub"] == "meet.example.org"
    assert payload["room"] == "Main Stage"
    assert payload["exp"] - payload["nbf"] == JITSI_JWT_LIFETIME_SECONDS + 10
    assert payload["context"]["user"]["affiliation"] == "member"
    assert payload["context"]["user"]["moderator"] is False


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_room_config_returns_moderator_jwt():
    event, room, server, user = await database_sync_to_async(
        create_jitsi_context
    )(
        slug="jitsi-moderator",
        profile={"display_name": "Speaker"},
        role="speaker",
    )
    consumer = DummyConsumer(event, room, user, moderator=True)

    await JitsiModule(consumer).room_config({"room": str(room.pk)})

    payload = jwt.decode(
        consumer.response["jwt"],
        server.app_secret,
        algorithms=["HS256"],
        audience="jitsi",
        issuer=server.app_id,
    )
    assert consumer.response["moderator"] is True
    assert "toolbarButtons" not in consumer.response["configOverwrite"]
    assert payload["room"] == f"room-{room.pk}"
    assert payload["context"]["user"]["affiliation"] == "owner"
    assert payload["context"]["user"]["moderator"] is True


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_room_config_requires_display_name():
    event, room, _server, user = await database_sync_to_async(
        create_jitsi_context
    )(
        slug="jitsi-missing-name",
        profile={},
    )

    with pytest.raises(ConsumerException) as excinfo:
        await JitsiModule(DummyConsumer(event, room, user)).room_config(
            {"room": str(room.pk)}
        )

    assert excinfo.value.code == "jitsi.join.missing_profile"

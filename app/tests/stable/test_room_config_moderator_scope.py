import copy
from unittest.mock import AsyncMock, MagicMock

import pytest

from eventyay.base.models.room import Room
from eventyay.base.services.room import redact_unmoderated_modules, restrict_module_config_patch
from eventyay.core.permissions import Permission
from eventyay.features.live.modules import room as room_module
from eventyay.features.live.modules.room import RoomModule

CHAT = {
    "type": "chat.native",
    "config": {"webhook_url": "https://hooks.example.invalid/in", "webhook_hmac_secret": "s3cret"},
}
JITSI = {"type": "call.jitsi", "config": {"start_with_audio_muted": False}}
ZOOM = {
    "type": "call.zoom",
    "config": {"meeting_number": "123456789", "password": "zoompass", "client_secret": "zoomsecret"},
}


def test_redact_unmoderated_modules_empties_other_modules():
    """Other modules keep their type and position but lose their settings; the input is untouched."""
    config = {"id": "1", "module_config": [CHAT, JITSI, ZOOM]}
    redacted = redact_unmoderated_modules(config, {"call.jitsi"})
    assert redacted["module_config"] == [
        {"type": "chat.native", "config": {}},
        JITSI,
        {"type": "call.zoom", "config": {}},
    ]
    assert config["module_config"] == [CHAT, JITSI, ZOOM]


def test_restrict_patch_keeps_stored_config_of_other_modules():
    """Only moderated modules take the client's config."""
    new_jitsi = {"type": "call.jitsi", "config": {"start_with_audio_muted": True}}
    evil_chat = {"type": "chat.native", "config": {"webhook_url": "https://attacker.example.invalid"}}
    result = restrict_module_config_patch([JITSI, CHAT], [new_jitsi, evil_chat], {"call.jitsi"})
    assert result == [new_jitsi, CHAT]


@pytest.mark.parametrize(
    "new_modules",
    [
        [JITSI],
        [JITSI, CHAT, {"type": "poll", "config": {}}],
        [JITSI, {"type": "question", "config": {}}],
        [JITSI, {"type": [], "config": {}}],
        "not-a-list",
        None,
    ],
)
def test_restrict_patch_rejects_module_changes(new_modules):
    """Adding, removing, swapping, or malformed modules are not a moderator action."""
    assert restrict_module_config_patch([JITSI, CHAT], new_modules, {"call.jitsi"}) is None


def test_restrict_patch_keeps_each_duplicate_module():
    """Stored modules sharing a type are restored in order, not collapsed."""
    first = {"type": "poll", "config": {"active": True}}
    second = {"type": "poll", "config": {"active": False}}
    stub = {"type": "poll", "config": {}}
    assert restrict_module_config_patch([first, second], [stub, stub], set()) == [first, second]


def test_restrict_patch_cannot_reorder_modules():
    """Submitted order is ignored; the stored order is kept."""
    new_jitsi = {"type": "call.jitsi", "config": {"start_with_audio_muted": True}}
    result = restrict_module_config_patch([JITSI, CHAT], [CHAT, new_jitsi], {"call.jitsi"})
    assert result == [new_jitsi, CHAT]


def make_moderator_module(room, allowed=frozenset({Permission.ROOM_JITSI_MODERATE})):
    """RoomModule for a user holding only the ``allowed`` permissions (Jitsi moderate by default)."""

    async def has_permission(*, user, permission, room=None):
        if isinstance(permission, (list, tuple)):
            return any(p in allowed for p in permission)
        return permission in allowed

    consumer = MagicMock()
    consumer.event.has_permission_async = AsyncMock(side_effect=has_permission)
    consumer.room_cache = {str(room.pk): room}
    consumer.send_success = AsyncMock()
    consumer.send_error = AsyncMock()
    return RoomModule(consumer), consumer


@pytest.fixture
def jitsi_chat_room(monkeypatch):
    """An in-memory room with Jitsi and a webhook-enabled chat; DB helpers are stubbed."""
    room = Room(pk=1, name="Call", module_config=copy.deepcopy([JITSI, CHAT]))
    room.refresh_from_db_if_outdated = AsyncMock()
    monkeypatch.setattr(
        room_module,
        "serialize_room_config",
        lambda r: {"id": str(r.pk), "name": r.name, "module_config": copy.deepcopy(r.module_config)},
    )
    monkeypatch.setattr(
        room_module, "check_video_entitlements", lambda event, modules: MagicMock(allowed=True)
    )
    validate = MagicMock(return_value=(None, None))
    monkeypatch.setattr(room_module, "validate_room_config_patch", validate)
    room.validate_mock = validate
    return room


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_moderator_config_get_only_returns_moderated_module_settings(jitsi_chat_room):
    """Call moderators get their call module's settings, not the Zoom or chat settings."""
    jitsi_chat_room.module_config = copy.deepcopy([JITSI, CHAT, ZOOM])
    module, consumer = make_moderator_module(jitsi_chat_room)
    await module.config_get({"room": str(jitsi_chat_room.pk)})
    sent = consumer.send_success.call_args[0][0]
    assert sent["module_config"] == [
        JITSI,
        {"type": "chat.native", "config": {}},
        {"type": "call.zoom", "config": {}},
    ]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_room_editor_config_get_returns_all_settings(jitsi_chat_room):
    """People who can edit the room still receive every module's settings."""
    jitsi_chat_room.module_config = copy.deepcopy([JITSI, CHAT, ZOOM])
    module, consumer = make_moderator_module(jitsi_chat_room, allowed={Permission.ROOM_UPDATE})
    await module.config_get({"room": str(jitsi_chat_room.pk)})
    sent = consumer.send_success.call_args[0][0]
    assert sent["module_config"] == [JITSI, CHAT, ZOOM]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "patch",
    [
        {"name": "Renamed"},
        {"trait_grants": {"admin": []}},
        {"module_config": [JITSI]},
    ],
)
async def test_moderator_config_patch_denied_outside_call_settings(jitsi_chat_room, patch):
    """Call moderators cannot rename the room, change grants, or remove modules."""
    module, consumer = make_moderator_module(jitsi_chat_room)
    await module.config_patch({"room": str(jitsi_chat_room.pk), **patch})
    consumer.send_error.assert_awaited_once_with(code="protocol.denied")
    jitsi_chat_room.validate_mock.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_moderator_config_patch_only_applies_call_settings(jitsi_chat_room, monkeypatch):
    """A moderator's Jitsi change is saved on top of the refreshed room; chat config and grants stay."""
    jitsi_chat_room.trait_grants = {"viewer": []}
    module, consumer = make_moderator_module(jitsi_chat_room)
    new_jitsi = {"type": "call.jitsi", "config": {"start_with_audio_muted": True}}
    evil_chat = {"type": "chat.native", "config": {"webhook_url": "https://attacker.example.invalid"}}
    newer_chat = {"type": "chat.native", "config": {"webhook_url": "https://hooks.example.invalid/new", "webhook_hmac_secret": "n3w"}}

    async def refresh(*args, **kwargs):
        jitsi_chat_room.module_config = copy.deepcopy([JITSI, newer_chat])

    jitsi_chat_room.refresh_from_db_if_outdated = AsyncMock(side_effect=refresh)

    jitsi_chat_room.validate_mock.side_effect = lambda room, body, **kw: (
        {"module_config": body["module_config"]},
        {"module_config"},
    )
    save_room = AsyncMock(side_effect=lambda event, room, fields, **kw: {"module_config": copy.deepcopy(room.module_config)})
    monkeypatch.setattr(room_module, "save_room", save_room)
    monkeypatch.setattr(room_module, "notify_event_change", AsyncMock())
    module._verify_webhook_challenges = AsyncMock()

    await module.config_patch({"room": str(jitsi_chat_room.pk), "module_config": [new_jitsi, evil_chat]})

    jitsi_chat_room.refresh_from_db_if_outdated.assert_awaited_with()
    _, body = jitsi_chat_room.validate_mock.call_args[0]
    assert body == {"module_config": [new_jitsi, newer_chat]}
    assert jitsi_chat_room.validate_mock.call_args[1] == {"sanitize_interaction_modules": False}
    _, saved_room, saved_fields = save_room.call_args[0]
    assert saved_fields == ["module_config"]
    assert saved_room.module_config == [new_jitsi, newer_chat]
    assert saved_room.trait_grants == {"viewer": []}
    module._verify_webhook_challenges.assert_not_awaited()
    sent = consumer.send_success.call_args[0][0]
    assert sent["module_config"] == [new_jitsi, {"type": "chat.native", "config": {}}]


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_config", [[], "x", None])
async def test_moderator_config_patch_rejects_non_object_module_config(jitsi_chat_room, bad_config):
    """A moderated module's config must be an object, or later .get() calls would fail."""
    module, consumer = make_moderator_module(jitsi_chat_room)
    bad_jitsi = {"type": "call.jitsi", "config": bad_config}
    await module.config_patch({"room": str(jitsi_chat_room.pk), "module_config": [bad_jitsi, CHAT]})
    consumer.send_error.assert_awaited_once_with(code="config.invalid")
    jitsi_chat_room.validate_mock.assert_not_called()

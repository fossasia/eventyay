import copy
from unittest.mock import AsyncMock, MagicMock

import pytest

from eventyay.base.models.room import Room
from eventyay.base.services.room import restrict_module_config_patch, strip_webhook_secrets
from eventyay.core.permissions import Permission
from eventyay.features.live.modules import room as room_module
from eventyay.features.live.modules.room import RoomModule

CHAT = {
    "type": "chat.native",
    "config": {"webhook_url": "https://hooks.example.invalid/in", "webhook_hmac_secret": "s3cret"},
}
JITSI = {"type": "call.jitsi", "config": {"start_with_audio_muted": False}}


def test_strip_webhook_secrets_copies_and_strips():
    """The secret is removed from the returned copy only."""
    config = {"module_config": [CHAT]}
    stripped = strip_webhook_secrets(config)
    assert "webhook_hmac_secret" not in stripped["module_config"][0]["config"]
    assert config["module_config"][0]["config"]["webhook_hmac_secret"] == "s3cret"


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
        "not-a-list",
        None,
    ],
)
def test_restrict_patch_rejects_module_changes(new_modules):
    """Adding, removing, or swapping modules is not a moderator action."""
    assert restrict_module_config_patch([JITSI, CHAT], new_modules, {"call.jitsi"}) is None


def make_moderator_module(room):
    """RoomModule for a user with only Jitsi moderate rights on ``room``."""
    allowed = {Permission.ROOM_JITSI_MODERATE}

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
async def test_moderator_config_get_hides_webhook_secret(jitsi_chat_room):
    """Call moderators do not receive the chat webhook secret."""
    module, consumer = make_moderator_module(jitsi_chat_room)
    await module.config_get({"room": str(jitsi_chat_room.pk)})
    sent = consumer.send_success.call_args[0][0]
    chat = next(m for m in sent["module_config"] if m["type"] == "chat.native")
    assert "webhook_hmac_secret" not in chat["config"]


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
async def test_moderator_config_patch_only_applies_call_settings(jitsi_chat_room):
    """A moderator's Jitsi change goes through; their chat webhook change is dropped."""
    module, _ = make_moderator_module(jitsi_chat_room)
    new_jitsi = {"type": "call.jitsi", "config": {"start_with_audio_muted": True}}
    evil_chat = {"type": "chat.native", "config": {"webhook_url": "https://attacker.example.invalid"}}
    await module.config_patch({"room": str(jitsi_chat_room.pk), "module_config": [new_jitsi, evil_chat]})
    _, body = jitsi_chat_room.validate_mock.call_args[0]
    assert body == {"module_config": [new_jitsi, CHAT]}

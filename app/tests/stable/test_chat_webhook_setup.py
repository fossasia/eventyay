import copy
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from requests import RequestException

from eventyay.base.models.room import Room
from eventyay.core.permissions import Permission
from eventyay.features.live import tasks as live_tasks
from eventyay.features.live.exceptions import ConsumerException
from eventyay.features.live.modules import room as room_module
from eventyay.features.live.modules.room import RoomModule


URL = "https://hooks.example.invalid/webhook/channel/abc"
SECRET = "s3cret"


def chat_module(url=URL, secret=SECRET):
    return {"type": "chat.native", "config": {"webhook_url": url, "webhook_hmac_secret": secret}}


def expected_signature(body, secret=SECRET):
    if isinstance(body, str):
        body = body.encode()
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class FakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data

    def json(self):
        if self._data is None:
            raise ValueError("no json")
        return self._data


class CallList(list):
    """Recorded calls, plus the fake receiver's behaviour."""


@pytest.fixture
def challenge_get(monkeypatch):
    """Record challenge GETs; the receiver echoes the token unless told otherwise."""
    calls = CallList()
    behaviour = {"status": 200, "echo": True}

    def fake_get(url, params=None, headers=None, **kwargs):
        calls.append({"url": url, "params": params, "headers": headers or {}})
        data = {"challenge": params["challenge"]} if behaviour["echo"] else {}
        return FakeResponse(behaviour["status"], data)

    monkeypatch.setattr(room_module.http_requests, "get", fake_get)
    calls.behaviour = behaviour
    return calls


@pytest.fixture
def module(settings):
    settings.DEBUG = True  # skip DNS lookups for the example URLs
    return RoomModule(MagicMock())


@pytest.mark.asyncio
async def test_challenge_is_signed_with_the_secret(module, challenge_get):
    """The challenge GET carries an HMAC of the token, so receivers can check the secret."""
    await module._verify_webhook_challenges([], [chat_module()])
    assert len(challenge_get) == 1
    token = challenge_get[0]["params"]["challenge"]
    assert challenge_get[0]["headers"]["X-Eventyay-Signature"] == expected_signature(token)


@pytest.mark.asyncio
async def test_challenge_runs_when_only_the_secret_changes(module, challenge_get):
    """A new secret on the same URL is verified again."""
    await module._verify_webhook_challenges([chat_module()], [chat_module(secret="n3w")])
    assert len(challenge_get) == 1
    token = challenge_get[0]["params"]["challenge"]
    assert challenge_get[0]["headers"]["X-Eventyay-Signature"] == expected_signature(token, "n3w")


@pytest.mark.asyncio
async def test_challenge_skipped_when_nothing_changed(module, challenge_get):
    """Saving unrelated room settings does not call the receiver."""
    await module._verify_webhook_challenges([chat_module()], [chat_module()])
    assert challenge_get == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,hint",
    [(403, "HMAC secret"), (404, "channel is active"), (500, "HTTP 500")],
)
async def test_challenge_failure_explains_status(module, challenge_get, status, hint):
    """A rejected challenge fails the save with a hint for the likely cause."""
    challenge_get.behaviour["status"] = status
    with pytest.raises(ConsumerException) as exc:
        await module._verify_webhook_challenges([], [chat_module()])
    assert exc.value.code == "webhook.verification_failed"
    assert hint in exc.value.message


def test_deliver_chat_webhook_signs_body_and_returns_status(monkeypatch):
    """Delivery signs the exact body sent and reports the receiver's status."""
    sent = {}

    def fake_post(url, data=None, headers=None, **kwargs):
        sent.update(url=url, data=data, headers=headers)
        return FakeResponse(403)

    monkeypatch.setattr(live_tasks.requests, "post", fake_post)
    status = live_tasks.deliver_chat_webhook({"b": 1, "a": 2}, URL, SECRET)
    assert status == 403
    assert sent["url"] == URL
    assert sent["headers"]["X-Eventyay-Signature"] == expected_signature(sent["data"])
    assert json.loads(sent["data"]) == {"a": 2, "b": 1}


def test_deliver_chat_webhook_returns_none_when_unreachable(monkeypatch):
    def fake_post(*args, **kwargs):
        raise RequestException("boom")

    monkeypatch.setattr(live_tasks.requests, "post", fake_post)
    assert live_tasks.deliver_chat_webhook({}, URL, SECRET) is None


def test_system_message_shape():
    """System messages are marked twice and name the room; sender fields stay empty."""
    room = Room(pk=7, name="Main Hall")
    payload = live_tasks.build_system_message(room, "test", "Test event", channel_id="c-1")
    assert payload["message_id"].startswith("system-")
    assert payload["message_type"] == "system"
    assert payload["meta"] == {"kind": "test", "room": {"id": "7", "name": "Main Hall"}}
    assert payload["channel"] == "c-1"
    assert payload["timestamp"]
    assert payload["screen_name"] == ""
    assert payload["sender_id"] == ""
    assert payload["centralauth_id"] is None


def make_editor_module(room, allowed=(Permission.ROOM_UPDATE,)):
    allowed = set(allowed)

    async def has_permission(*, user, permission, room=None):
        if isinstance(permission, (list, tuple)):
            return any(p in allowed for p in permission)
        return permission in allowed

    consumer = MagicMock()
    consumer.event.has_permission_async = AsyncMock(side_effect=has_permission)
    consumer.room_cache = {str(room.pk): room}
    consumer.send_success = AsyncMock()
    consumer.send_error = AsyncMock()
    module = RoomModule(consumer)
    module._chat_channel_id = lambda: "chan-1"
    return module, consumer


@pytest.fixture
def chat_room():
    room = Room(pk=3, name="Main Hall", module_config=[copy.deepcopy(chat_module())])
    room.refresh_from_db_if_outdated = AsyncMock()
    return room


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_webhook_test_sends_system_message(chat_room, settings, monkeypatch):
    """The test command posts a signed ``test`` system message and returns the status."""
    settings.DEBUG = True
    delivered = []

    def fake_deliver(payload, url, secret):
        delivered.append((payload, url, secret))
        return 200

    monkeypatch.setattr(room_module, "deliver_chat_webhook", fake_deliver)
    module, consumer = make_editor_module(chat_room)
    await module.webhook_test({"room": str(chat_room.pk)})

    consumer.send_success.assert_awaited_once_with({"status": 200, "ok": True})
    payload, url, secret = delivered[0]
    assert (url, secret) == (URL, SECRET)
    assert payload["meta"]["kind"] == "test"
    assert payload["meta"]["room"] == {"id": "3", "name": "Main Hall"}
    assert payload["channel"] == "chan-1"
    assert "Main Hall" in payload["message"]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_webhook_test_reports_receiver_status(chat_room, settings, monkeypatch):
    settings.DEBUG = True
    monkeypatch.setattr(room_module, "deliver_chat_webhook", lambda *a: 403)
    module, consumer = make_editor_module(chat_room)
    await module.webhook_test({"room": str(chat_room.pk)})
    consumer.send_success.assert_awaited_once_with({"status": 403, "ok": False})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "modules",
    [
        42,
        [{"type": "chat.native", "config": {}}],
        [{"type": "chat.native", "config": ["unexpected"]}],
        [chat_module(url=42)],
        [chat_module(secret=["unexpected"])],
    ],
)
async def test_webhook_test_needs_saved_webhook(modules, settings, monkeypatch):
    settings.DEBUG = True
    room = Room(pk=4, name="Invalid webhook", module_config=modules)
    room.refresh_from_db_if_outdated = AsyncMock()
    deliver = MagicMock()
    monkeypatch.setattr(room_module, "deliver_chat_webhook", deliver)
    module, consumer = make_editor_module(room)
    await module.webhook_test({"room": str(room.pk)})
    consumer.send_error.assert_awaited_once()
    assert consumer.send_error.call_args.kwargs["code"] == "webhook.not_configured"
    deliver.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_test_denied_for_call_moderators(chat_room, monkeypatch):
    """Moderating a call is not enough to send webhook tests."""
    deliver = MagicMock()
    monkeypatch.setattr(room_module, "deliver_chat_webhook", deliver)
    module, consumer = make_editor_module(chat_room, allowed={Permission.ROOM_JITSI_MODERATE})
    with pytest.raises(ConsumerException) as exc:
        await module.webhook_test({"room": str(chat_room.pk)})
    assert exc.value.code == "protocol.denied"
    deliver.assert_not_called()
    consumer.send_success.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_test_blocks_private_address(chat_room, settings, monkeypatch):
    settings.DEBUG = False
    deliver = MagicMock()
    monkeypatch.setattr(room_module, "deliver_chat_webhook", deliver)
    monkeypatch.setattr(RoomModule, "_is_private_url", staticmethod(lambda url: True))
    module, consumer = make_editor_module(chat_room)
    await module.webhook_test({"room": str(chat_room.pk)})
    assert consumer.send_error.call_args.kwargs["code"] == "webhook.invalid_url"
    deliver.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.django_db
@pytest.mark.parametrize("cached_secret", [SECRET, "wrong"])
async def test_rejected_secret_does_not_stay_on_cached_room(
    chat_room, challenge_get, settings, monkeypatch, cached_secret
):
    """A failed challenge leaves the cached room with its previous webhook settings."""
    settings.DEBUG = True
    challenge_get.behaviour["status"] = 403
    chat_room.module_config = [chat_module(secret=cached_secret)]

    async def refresh(allowed_age=0):
        if allowed_age == 0:
            chat_room.module_config = [chat_module()]

    chat_room.refresh_from_db_if_outdated.side_effect = refresh
    monkeypatch.setattr(
        room_module,
        "serialize_room_config",
        lambda r: {"id": str(r.pk), "module_config": copy.deepcopy(r.module_config)},
    )
    monkeypatch.setattr(
        room_module, "check_video_entitlements", lambda event, modules: MagicMock(allowed=True)
    )
    new_modules = [chat_module(secret="wrong")]
    monkeypatch.setattr(
        room_module,
        "validate_room_config_patch",
        lambda room, body, **kw: ({"module_config": new_modules}, {"module_config"}),
    )
    module, consumer = make_editor_module(chat_room)
    with pytest.raises(ConsumerException) as exc:
        await module.config_patch({"room": str(chat_room.pk), "module_config": new_modules})
    assert exc.value.code == "webhook.verification_failed"
    assert len(challenge_get) == 1
    assert chat_room.module_config == [chat_module()]

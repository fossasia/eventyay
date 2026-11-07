import hashlib
import hmac
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch


# Mock heavy external services so unit tests run cleanly and fast in isolation
for _mod in [
    'eventyay.base.services.chat',
    'eventyay.base.services.event',
    'eventyay.base.services.user',
    'eventyay.storage.tasks',
    'eventyay.base.models.room',
    'eventyay.base.services.poll',
    'eventyay.base.services.reactions',
    'eventyay.base.services.room',
    'eventyay.base.services.room_creation_gate',
    'eventyay.base.settings',
    'eventyay.base.services.video_entitlements',
    'eventyay.eventyay_common.utils',
    'sentry_sdk',
]:
    sys.modules[_mod] = MagicMock()

import django  # noqa: E402
from django.conf import settings  # noqa: E402


if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={},
        SECRET_KEY='test-secret-key',
    )
    django.setup()

import pytest  # noqa: E402

from eventyay.features.live.exceptions import ConsumerException  # noqa: E402
from eventyay.features.live.modules.chat import ChatModule  # noqa: E402
from eventyay.features.live.modules.room import RoomModule  # noqa: E402
from eventyay.features.live.tasks import (  # noqa: E402
    post_chat_webhook,
    send_room_system_message,
)


class DummyRoom:
    def __init__(self, room_id='room-123', name='Main Hall', module_config=None, channel=None):
        self.id = room_id
        self.name = name
        self.module_config = module_config or []
        self.channel = channel


class DummyChannel:
    def __init__(self, channel_id='chan-456', room=None):
        self.id = channel_id
        self.room = room


class DummyUser:
    def __init__(self, user_id='user-789', display_name='Test User', locale='en'):
        self.id = user_id
        self.profile = {'display_name': display_name}
        self.locale = locale


@pytest.mark.asyncio
async def test_verify_webhook_challenges_signs_challenge():
    """Test that challenge GET includes X-Eventyay-Signature header with HMAC-SHA256."""
    room_module = RoomModule(MagicMock())

    old_config = []
    new_config = [
        {
            'type': 'chat.native',
            'config': {
                'webhook_url': 'https://example.com/chat-webhook',
                'webhook_hmac_secret': 'my-secret-key',
            },
        }
    ]

    captured_requests = []

    def mock_get(url, params=None, headers=None, timeout=None, allow_redirects=None):
        captured_requests.append(
            {
                'url': url,
                'params': params,
                'headers': headers,
            }
        )
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {'challenge': params.get('challenge')}
        return resp

    with patch('eventyay.features.live.modules.room.http_requests.get', side_effect=mock_get):
        await room_module._verify_webhook_challenges(old_config, new_config)

    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req['url'] == 'https://example.com/chat-webhook'
    challenge = req['params']['challenge']
    expected_sig = hmac.new(b'my-secret-key', challenge.encode('utf-8'), hashlib.sha256).hexdigest()
    assert req['headers'] == {'X-Eventyay-Signature': f'sha256={expected_sig}'}


@pytest.mark.asyncio
async def test_verify_webhook_challenges_runs_when_secret_changes():
    """Test that changing only the HMAC secret re-runs the signed challenge."""
    room_module = RoomModule(MagicMock())

    old_config = [
        {
            'type': 'chat.native',
            'config': {
                'webhook_url': 'https://example.com/chat-webhook',
                'webhook_hmac_secret': 'old-secret',
            },
        }
    ]
    new_config = [
        {
            'type': 'chat.native',
            'config': {
                'webhook_url': 'https://example.com/chat-webhook',
                'webhook_hmac_secret': 'new-secret',
            },
        }
    ]

    captured_requests = []

    def mock_get(url, params=None, headers=None, timeout=None, allow_redirects=None):
        captured_requests.append({'params': params, 'headers': headers})
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {'challenge': params.get('challenge')}
        return resp

    with patch('eventyay.features.live.modules.room.http_requests.get', side_effect=mock_get):
        await room_module._verify_webhook_challenges(old_config, new_config)

    assert len(captured_requests) == 1
    challenge = captured_requests[0]['params']['challenge']
    expected_sig = hmac.new(b'new-secret', challenge.encode('utf-8'), hashlib.sha256).hexdigest()
    assert captured_requests[0]['headers'] == {'X-Eventyay-Signature': f'sha256={expected_sig}'}


@pytest.mark.asyncio
async def test_verify_webhook_challenges_skips_when_unchanged():
    """Test that identical URL and secret skips challenge verification."""
    room_module = RoomModule(MagicMock())

    config = [
        {
            'type': 'chat.native',
            'config': {
                'webhook_url': 'https://example.com/chat-webhook',
                'webhook_hmac_secret': 'same-secret',
            },
        }
    ]

    with patch('eventyay.features.live.modules.room.http_requests.get') as mock_get:
        await room_module._verify_webhook_challenges(config, config)
        mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_verify_webhook_challenges_rejects_on_http_error():
    """Test that a receiver returning HTTP 403 on invalid secret fails verification."""
    room_module = RoomModule(MagicMock())

    new_config = [
        {
            'type': 'chat.native',
            'config': {
                'webhook_url': 'https://example.com/chat-webhook',
                'webhook_hmac_secret': 'wrong-secret',
            },
        }
    ]

    def mock_get(url, params=None, headers=None, timeout=None, allow_redirects=None):
        resp = MagicMock()
        resp.status_code = 403
        return resp

    with patch('eventyay.features.live.modules.room.http_requests.get', side_effect=mock_get):
        with pytest.raises(ConsumerException) as exc_info:
            await room_module._verify_webhook_challenges([], new_config)
        assert exc_info.value.code == 'webhook.verification_failed'
        assert '403' in exc_info.value.message


def test_post_chat_webhook_success():
    """Test that post_chat_webhook serializes JSON and adds X-Eventyay-Signature header."""
    payload = {'hello': 'world'}
    url = 'https://example.com/webhook'
    secret = 'secret123'

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch('eventyay.features.live.tasks.requests.post', return_value=mock_resp) as mock_post:
        status = post_chat_webhook(payload, url, secret)

    assert status == 200
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == url
    expected_body = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    expected_sig = hmac.new(b'secret123', expected_body.encode('utf-8'), hashlib.sha256).hexdigest()
    assert call_args[1]['data'] == expected_body
    assert call_args[1]['headers']['X-Eventyay-Signature'] == f'sha256={expected_sig}'


def test_send_room_system_message():
    """Test that send_room_system_message formats the test system message correctly."""
    channel = DummyChannel('chan-999')
    room = DummyRoom(
        room_id='room-abc',
        name='Keynote Stage',
        module_config=[
            {
                'type': 'chat.native',
                'config': {
                    'webhook_url': 'https://example.com/webhook',
                    'webhook_hmac_secret': 'hmac-secret-xyz',
                },
            }
        ],
        channel=channel,
    )

    captured_payload = None

    def mock_post(payload, url, secret):
        nonlocal captured_payload
        captured_payload = payload
        return 200

    with patch('eventyay.features.live.tasks.post_chat_webhook', side_effect=mock_post):
        status = send_room_system_message(room, kind='test')

    assert status == 200
    assert captured_payload is not None
    assert captured_payload['message_id'].startswith('system-')
    assert captured_payload['message_type'] == 'system'
    assert captured_payload['channel'] == 'chan-999'
    assert captured_payload['screen_name'] == ''
    assert captured_payload['sender_id'] == ''
    assert captured_payload['centralauth_id'] is None
    assert captured_payload['centralauth_username'] is None
    assert captured_payload['meta']['kind'] == 'test'
    assert captured_payload['meta']['room'] == {'id': 'room-abc', 'name': 'Keynote Stage'}
    assert captured_payload['message'] == 'Test event from Eventyay room Keynote Stage'


def test_send_room_system_message_missing_config():
    """Test that send_room_system_message raises ValueError if no webhook is configured."""
    room = DummyRoom(room_id='room-abc', name='Room Without Webhook', module_config=[])
    with pytest.raises(ValueError, match='Room has no chat webhook configured'):
        send_room_system_message(room)


@pytest.mark.asyncio
async def test_chat_webhook_test_command_success():
    """Test that chat_webhook_test command on RoomModule returns status_code."""
    consumer = MagicMock()
    consumer.send_success = AsyncMock()
    consumer.send_error = AsyncMock()
    consumer.user = DummyUser()
    consumer.event.has_permission_async = AsyncMock(return_value=True)

    room_module = RoomModule(consumer)
    room = DummyRoom(
        room_id='room-123',
        name='Workshop Room',
        module_config=[
            {
                'type': 'chat.native',
                'config': {
                    'webhook_url': 'https://example.com/webhook',
                    'webhook_hmac_secret': 'secret',
                },
            }
        ],
    )
    consumer.room_cache = {'room-123': room}
    room.refresh_from_db_if_outdated = AsyncMock()

    with patch('eventyay.features.live.modules.room.send_room_system_message', return_value=200):
        await room_module.chat_webhook_test({'room': 'room-123'})

    consumer.send_success.assert_called_once_with({'status_code': 200})
    consumer.send_error.assert_not_called()


@pytest.mark.asyncio
async def test_chat_webhook_test_command_not_configured():
    """Test that chat_webhook_test command returns error if webhook is not configured."""
    consumer = MagicMock()
    consumer.send_success = AsyncMock()
    consumer.send_error = AsyncMock()
    consumer.user = DummyUser()
    consumer.event.has_permission_async = AsyncMock(return_value=True)

    room_module = RoomModule(consumer)
    room = DummyRoom(room_id='room-123', name='Workshop Room', module_config=[])
    consumer.room_cache = {'room-123': room}
    room.refresh_from_db_if_outdated = AsyncMock()

    await room_module.chat_webhook_test({'room': 'room-123'})

    consumer.send_error.assert_called_once_with(
        code='webhook.not_configured',
        message='No chat webhook is configured for this room.',
    )
    consumer.send_success.assert_not_called()


@pytest.mark.asyncio
async def test_chat_webhook_payload_includes_meta_room():
    """Test that ChatModule._dispatch_chat_webhook includes meta.room in payload."""
    consumer = MagicMock()
    consumer.user = DummyUser()
    chat_module = ChatModule(consumer)

    room = DummyRoom(room_id='room-xyz', name='Track A')
    channel = DummyChannel('chan-789', room=room)
    chat_module.channel = channel
    chat_module.module_config = {
        'webhook_url': 'https://example.com/chat-webhook',
        'webhook_hmac_secret': 'my-secret',
    }

    event_data = {
        'event_id': 'msg-001',
        'channel': 'chan-789',
        'timestamp': '2026-11-07T10:00:00Z',
        'content': {'body': 'Hello world!'},
    }

    with patch('eventyay.features.live.modules.chat._get_centralauth_info', return_value=(None, None)):
        with patch('eventyay.features.live.modules.chat.send_chat_webhook.apply_async') as mock_apply_async:
            await chat_module._dispatch_chat_webhook(event_data, message_type='text')

    mock_apply_async.assert_called_once()
    kwargs = mock_apply_async.call_args[1]['kwargs']
    payload = kwargs['payload']
    assert payload['meta']['room'] == {'id': 'room-xyz', 'name': 'Track A'}
    assert payload['message'] == 'Hello world!'
    assert payload['message_type'] == 'text'

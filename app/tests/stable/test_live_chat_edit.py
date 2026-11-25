"""A rejected chat edit must leave the stored message unchanged (issue #7697)."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from asgiref.sync import async_to_sync
from channels import db as channels_db
from django.contrib.auth import get_user_model
from django_scopes import scope

from eventyay.base.models import AuditLog, ChatEvent
from eventyay.base.models.chat import Channel, Membership
from eventyay.features.live.exceptions import ConsumerException
from eventyay.features.live.modules import chat as chat_module
from eventyay.features.live.modules.chat import ChatModule


User = get_user_model()

ORIGINAL = {'type': 'text', 'body': 'Meet at 5pm'}

# `send` without the `command` and `channel_action` wrappers; the tests set the channel themselves
send_unwrapped = ChatModule.send.__wrapped__.__wrapped__


@pytest.fixture
def dm(event):
    """A direct message between Alice and Bob with one message from Bob."""
    with scope(event=event):
        alice = User.objects.create_user(email='alice@example.com', password='x', fullname='Alice', event=event)
        bob = User.objects.create_user(email='bob@example.com', password='x', fullname='Bob', event=event)
        channel = Channel.objects.create(event=event)
        Membership.objects.create(channel=channel, user=alice)
        Membership.objects.create(channel=channel, user=bob)
        message = ChatEvent.objects.create(
            id=1,
            channel=channel,
            event_type='channel.message',
            sender=bob,
            content=ORIGINAL,
        )
    return {'alice': alice, 'bob': bob, 'channel': channel, 'message': message}


@asynccontextmanager
async def fake_redis():
    redis = AsyncMock()
    redis.exists.return_value = True
    redis.smembers.return_value = set()
    redis.spop.return_value = []
    yield redis


def make_module(event, channel, user, monkeypatch):
    # channels closes the connection around each ORM call, which would end the test transaction
    monkeypatch.setattr(channels_db, 'close_old_connections', lambda: None)
    user.clear_caches()
    consumer = MagicMock()
    consumer.event = event
    consumer.user = user
    consumer.send_success = AsyncMock()
    consumer.send_json = AsyncMock()
    consumer.channel_layer.group_send = AsyncMock()
    monkeypatch.setattr(chat_module, 'aredis', fake_redis)
    module = ChatModule(consumer)
    module.channel = channel
    module.channel_id = str(channel.id)
    module.module_config = {}
    return module, consumer


def edit_body(dm, content):
    return {
        'channel': str(dm['channel'].id),
        'event_type': 'channel.message',
        'replaces': dm['message'].id,
        'content': content,
    }


def stored_message(dm):
    message = ChatEvent.objects.get(pk=dm['message'].pk)
    return message.content, message.edited


def edit_audit_logs(event):
    return AuditLog.objects.filter(event=event, type='chat.event.updated').count()


def send(module, body):
    # async_to_sync keeps the ORM calls on this thread, inside the test transaction
    async_to_sync(send_unwrapped)(module, body)


def assert_rejected_and_unchanged(module, consumer, dm, event, body, code):
    with pytest.raises(ConsumerException) as excinfo:
        send(module, body)

    assert excinfo.value.code == code
    assert stored_message(dm) == (ORIGINAL, None)
    assert edit_audit_logs(event) == 0
    consumer.send_success.assert_not_awaited()
    consumer.channel_layer.group_send.assert_not_awaited()


@pytest.mark.django_db
@pytest.mark.parametrize(
    'content',
    [{'type': 'text', 'body': ''}, {'type': 'files', 'files': []}],
)
def test_empty_edit_is_rejected_and_not_saved(event, dm, content, monkeypatch):
    module, consumer = make_module(event, dm['channel'], dm['bob'], monkeypatch)

    assert_rejected_and_unchanged(module, consumer, dm, event, edit_body(dm, content), 'chat.empty')


@pytest.mark.django_db
def test_edit_by_blocked_user_is_rejected_and_not_saved(event, dm, monkeypatch):
    dm['alice'].blocked_users.add(dm['bob'])
    module, consumer = make_module(event, dm['channel'], dm['bob'], monkeypatch)
    body = edit_body(dm, {'type': 'text', 'body': 'Meet at 6pm'})

    assert_rejected_and_unchanged(module, consumer, dm, event, body, 'chat.denied')


@pytest.mark.django_db
def test_edit_by_silenced_user_is_rejected_and_not_saved(event, dm, monkeypatch):
    bob = dm['bob']
    bob.moderation_state = User.ModerationState.SILENCED
    bob.save(update_fields=['moderation_state'])
    module, consumer = make_module(event, dm['channel'], bob, monkeypatch)
    body = edit_body(dm, {'type': 'text', 'body': 'Meet at 6pm'})

    assert_rejected_and_unchanged(module, consumer, dm, event, body, 'chat.denied')


@pytest.mark.django_db
def test_edit_of_other_users_message_is_rejected_and_not_saved(event, dm, monkeypatch):
    module, consumer = make_module(event, dm['channel'], dm['alice'], monkeypatch)
    body = edit_body(dm, {'type': 'text', 'body': 'Meet at 6pm'})

    assert_rejected_and_unchanged(module, consumer, dm, event, body, 'chat.denied')


@pytest.mark.django_db
def test_valid_edit_is_saved_and_broadcast(event, dm, monkeypatch):
    module, consumer = make_module(event, dm['channel'], dm['bob'], monkeypatch)
    edit_event = {'type': 'chat.event', 'event_id': 2, 'replaces': dm['message'].id}
    module.service.create_event = AsyncMock(return_value=edit_event)
    new_content = {'type': 'text', 'body': 'Meet at 6pm'}

    send(module, edit_body(dm, new_content))

    content, edited = stored_message(dm)
    assert content == new_content
    assert edited is not None
    assert edit_audit_logs(event) == 1
    assert module.service.create_event.await_args.kwargs['replaces'] == dm['message'].id
    consumer.send_success.assert_awaited_once()
    consumer.channel_layer.group_send.assert_any_await(f'chat.{dm["channel"].id}', edit_event)

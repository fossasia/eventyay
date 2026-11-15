from unittest.mock import AsyncMock, MagicMock

import pytest
from asgiref.sync import sync_to_async
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import ChatEvent
from eventyay.base.models.chat import Channel
from eventyay.base.models.storage_model import StoredFile
from eventyay.base.services.chat import ChatService
from eventyay.storage import external, tasks
from eventyay.storage.tasks import retrieve_preview_information


PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32


@pytest.fixture
def chat_event(event):
    with scope(event=event):
        channel = Channel.objects.create(event=event)
        return ChatEvent.objects.create(
            id=4242,
            channel=channel,
            event_type='channel.message',
            content={'type': 'text', 'body': 'look https://public.example/cat.png'},
        )


@pytest.fixture
def broadcast(monkeypatch):
    create_event = AsyncMock(return_value={'type': 'chat.event'})
    monkeypatch.setattr(ChatService, 'create_event', create_event)
    layer = MagicMock(group_send=AsyncMock())
    monkeypatch.setattr(tasks.channels.layers, 'get_channel_layer', lambda: layer)
    return create_event, layer


@pytest.mark.django_db
def test_preview_is_stored_for_the_message(event, chat_event, broadcast, monkeypatch, settings, tmp_path):
    """The task gets the kwargs the chat module sends and stores the image under the Event."""
    settings.MEDIA_ROOT = tmp_path
    image = MagicMock(headers={'Content-Type': 'image/png'}, content=PNG, url='https://public.example/cat.png')
    monkeypatch.setattr(external, 'retrieve_url', lambda url: image)

    retrieve_preview_information.apply(kwargs={'event': str(event.id), 'chat_event_id': chat_event.id}).get()

    with scope(event=event):
        chat_event.refresh_from_db()
        stored = StoredFile.objects.get()
    assert stored.event == event
    assert chat_event.content['preview_card']['image'] == stored.file.url
    create_event, layer = broadcast
    assert create_event.call_args.kwargs['replaces'] == chat_event.id
    layer.group_send.assert_called_once()


@pytest.mark.django_db
def test_message_of_another_event_is_ignored(event, chat_event, broadcast, monkeypatch):
    other = event.organizer.events.create(
        name='Other', slug='other', date_from=event.date_from, currency='USD', locale='en'
    )
    fetch = MagicMock()
    monkeypatch.setattr(tasks, 'fetch_preview_data', fetch)

    retrieve_preview_information.apply(kwargs={'event': str(other.id), 'chat_event_id': chat_event.id}).get()

    fetch.assert_not_called()


@pytest.mark.django_db
def test_failed_preview_is_logged_and_skipped(event, chat_event, broadcast, monkeypatch, caplog):
    monkeypatch.setattr(tasks, 'fetch_preview_data', MagicMock(side_effect=UnicodeDecodeError('utf-8', b'', 0, 1, 'x')))

    retrieve_preview_information.apply(kwargs={'event': str(event.id), 'chat_event_id': chat_event.id}).get()

    assert 'Could not build a link preview' in caplog.text
    with scope(event=event):
        chat_event.refresh_from_db()
    assert 'preview_card' not in chat_event.content
    broadcast[0].assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    'content',
    [{'type': 'deleted'}, {'type': 'text'}, {'type': 'text', 'body': None}, {'type': 'call', 'body': {}}],
)
def test_non_text_message_is_skipped(event, chat_event, broadcast, monkeypatch, content):
    """The message may be deleted or changed before the queued task loads it."""
    with scope(event=event):
        ChatEvent.objects.filter(pk=chat_event.pk).update(content=content)
    fetch = MagicMock()
    monkeypatch.setattr(tasks, 'fetch_preview_data', fetch)

    retrieve_preview_information.apply(kwargs={'event': str(event.id), 'chat_event_id': chat_event.id}).get()

    fetch.assert_not_called()
    broadcast[0].assert_not_called()


@pytest.mark.django_db
def test_edit_during_retrieval_is_not_overwritten(event, chat_event, broadcast, monkeypatch):
    """A message deleted while the preview is fetched stays deleted and is not re-broadcast."""

    def fetch_and_delete(url, event):
        with scope(event=event):
            ChatEvent.objects.filter(pk=chat_event.pk).update(content={'type': 'deleted'}, edited=now())
        return {'title': 'Cat', 'url': url}

    monkeypatch.setattr(tasks, 'fetch_preview_data', fetch_and_delete)

    retrieve_preview_information.apply(kwargs={'event': str(event.id), 'chat_event_id': chat_event.id}).get()

    with scope(event=event):
        chat_event.refresh_from_db()
    assert chat_event.content == {'type': 'deleted'}
    broadcast[0].assert_not_called()
    broadcast[1].group_send.assert_not_called()


@pytest.mark.django_db
def test_deleted_original_of_an_edit_is_not_overwritten(event, chat_event, broadcast, monkeypatch):
    """The preview of an edit is skipped if the original message was deleted meanwhile."""
    with scope(event=event):
        edit = ChatEvent.objects.create(
            id=4243,
            channel=chat_event.channel,
            event_type='channel.message',
            content=chat_event.content,
            replaces=chat_event,
        )

    def fetch_and_delete_original(url, event):
        with scope(event=event):
            ChatEvent.objects.filter(pk=chat_event.pk).update(content={'type': 'deleted'}, edited=now())
        return {'title': 'Cat', 'url': url}

    monkeypatch.setattr(tasks, 'fetch_preview_data', fetch_and_delete_original)

    retrieve_preview_information.apply(kwargs={'event': str(event.id), 'chat_event_id': edit.id}).get()

    with scope(event=event):
        edit.refresh_from_db()
    assert 'preview_card' not in edit.content
    broadcast[0].assert_not_called()


@pytest.mark.django_db
def test_deletion_before_broadcast_is_sent_again(event, chat_event, broadcast, monkeypatch):
    """If the message is deleted between saving the preview and broadcasting it, the deletion is re-sent last."""
    create_event, layer = broadcast
    monkeypatch.setattr(tasks, 'fetch_preview_data', lambda url, event: {'title': 'Cat', 'url': url})

    async def create_and_delete(**kwargs):
        if create_event.await_count == 1:
            await sync_to_async(
                lambda: ChatEvent.objects.filter(pk=chat_event.pk).update(content={'type': 'deleted'}, edited=now())
            )()
        return {'type': 'chat.event', 'content': kwargs['content']}

    create_event.side_effect = create_and_delete

    retrieve_preview_information.apply(kwargs={'event': str(event.id), 'chat_event_id': chat_event.id}).get()

    assert create_event.await_count == 2
    assert create_event.call_args.kwargs['replaces'] == chat_event.id
    assert create_event.call_args.kwargs['content'] == {'type': 'deleted'}
    assert layer.group_send.call_args.args[1]['content'] == {'type': 'deleted'}

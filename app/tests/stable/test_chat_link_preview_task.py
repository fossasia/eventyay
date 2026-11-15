from unittest.mock import AsyncMock, MagicMock

import pytest
from django_scopes import scopes_disabled

from eventyay.base.models import ChatEvent
from eventyay.base.models.chat import Channel
from eventyay.base.models.storage_model import StoredFile
from eventyay.base.services.chat import ChatService
from eventyay.storage import external, tasks
from eventyay.storage.tasks import retrieve_preview_information


PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32


@pytest.fixture
def chat_event(event):
    with scopes_disabled():
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

    with scopes_disabled():
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
    with scopes_disabled():
        chat_event.refresh_from_db()
    assert 'preview_card' not in chat_event.content
    broadcast[0].assert_not_called()

from types import SimpleNamespace

import pytest
from asgiref.sync import async_to_sync

from eventyay.base.models import BBBServer
from eventyay.base.services import event as event_service
from eventyay.base.services.bbb import event_has_active_bbb_server


async def _allow_permission(**kwargs):
    return True


class ChannelLayer:
    async def group_send(self, *args, **kwargs):
        pass


def _patch_room_creation(monkeypatch):
    created = {}

    async def fake_create_room(data, with_channel=False, **kwargs):
        created['data'] = data
        created['with_channel'] = with_channel
        return SimpleNamespace(id='room-id'), None

    monkeypatch.setattr(event_service, '_create_room', fake_create_room)
    monkeypatch.setattr(event_service, 'get_channel_layer', lambda: ChannelLayer())
    return created


def _bbb_event():
    return SimpleNamespace(
        id='event-id',
        has_permission_async=_allow_permission,
        config={'bbb_defaults': {'record': True, 'secret': 'legacy', 'video_chat': True}},
    )


def test_create_video_chat_keeps_marker_and_bbb_defaults(monkeypatch):
    created = _patch_room_creation(monkeypatch)

    async_to_sync(event_service.create_room)(
        _bbb_event(),
        {
            'name': 'Lounge',
            'description': 'video chat',
            'modules': [{'type': 'call.bigbluebutton', 'config': {'video_chat': True}}],
        },
        object(),
    )

    module = created['data']['module_config'][0]
    assert module['type'] == 'call.bigbluebutton'
    assert module['config']['record'] is True
    assert module['config']['video_chat'] is True
    assert 'secret' not in module['config']


def test_create_video_channel_does_not_inherit_video_chat_marker(monkeypatch):
    created = _patch_room_creation(monkeypatch)

    async_to_sync(event_service.create_room)(
        _bbb_event(),
        {
            'name': 'Workshop',
            'description': 'video channel',
            'modules': [{'type': 'call.bigbluebutton', 'config': {}}],
        },
        object(),
    )

    module = created['data']['module_config'][0]
    assert module['type'] == 'call.bigbluebutton'
    assert module['config']['record'] is True
    assert 'video_chat' not in module['config']
    assert 'secret' not in module['config']


@pytest.mark.django_db
def test_event_has_active_bbb_server(event):
    assert event_has_active_bbb_server(event) is False

    BBBServer.objects.create(
        url='https://inactive.example.com/bigbluebutton/',
        secret='secret',
        active=False,
    )
    assert event_has_active_bbb_server(event) is False

    BBBServer.objects.create(
        url='https://shared.example.com/bigbluebutton/',
        secret='secret',
        active=True,
    )
    assert event_has_active_bbb_server(event) is True

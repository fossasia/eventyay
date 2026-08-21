from types import SimpleNamespace

import pytest
from asgiref.sync import async_to_sync
from django.core.exceptions import ValidationError
from django_scopes import scope

from eventyay.base.meetup import (
    VIDEO_TYPE_IFRAME,
    get_video_config_from_modules,
    get_video_module_config,
)
from eventyay.base.models import Room
from eventyay.base.services import event as event_service
from eventyay.base.services.room import (
    UNSUPPORTED_CREATE_MODULE_TYPES,
    contains_unsupported_room_module_types,
    validate_room_config_patch,
)


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
        channel = SimpleNamespace(id='channel-id') if with_channel else None
        return SimpleNamespace(id='room-id'), channel

    monkeypatch.setattr(event_service, '_create_room', fake_create_room)
    monkeypatch.setattr(event_service, 'get_channel_layer', lambda: ChannelLayer())
    return created


@pytest.mark.parametrize(
    'module_type',
    sorted(UNSUPPORTED_CREATE_MODULE_TYPES),
)
def test_create_room_rejects_removed_room_types(monkeypatch, module_type):
    _patch_room_creation(monkeypatch)
    event = SimpleNamespace(id='event-id', has_permission_async=_allow_permission)

    with pytest.raises(ValidationError) as exc:
        async_to_sync(event_service.create_room)(
            event,
            {
                'name': 'Removed Room',
                'description': 'should not be created',
                'modules': [{'type': module_type}],
            },
            object(),
        )

    assert exc.value.code == 'unsupported_type'


def test_create_room_still_allows_text_channels(monkeypatch):
    created = _patch_room_creation(monkeypatch)
    event = SimpleNamespace(id='event-id', has_permission_async=_allow_permission)

    result = async_to_sync(event_service.create_room)(
        event,
        {
            'name': 'Chat',
            'description': 'a description',
            'modules': [{'type': 'chat.native'}],
        },
        object(),
    )

    assert result == {'room': 'room-id', 'channel': 'channel-id'}
    assert created['data']['module_config'][0]['type'] == 'chat.native'


@pytest.mark.django_db
@pytest.mark.parametrize(
    'module_type',
    sorted(UNSUPPORTED_CREATE_MODULE_TYPES),
)
def test_config_patch_rejects_removed_room_types(event, module_type):
    with scope(event=event):
        room = Room.objects.create(
            event=event,
            name='Removed',
            module_config=[{'type': module_type, 'config': {}}],
        )
        with pytest.raises(ValidationError) as exc:
            validate_room_config_patch(
                room,
                {'module_config': [{'type': module_type, 'config': {'updated': True}}]},
            )
    assert exc.value.code == 'unsupported_type'


def test_contains_unsupported_room_module_types():
    assert contains_unsupported_room_module_types(
        [{'type': 'exhibition.native', 'config': {}}]
    ) == frozenset({'exhibition.native'})
    assert contains_unsupported_room_module_types(
        [{'type': 'chat.native', 'config': {}}]
    ) == frozenset()


def test_meetup_iframe_uses_stage_livestream_module():
    modules = get_video_module_config(VIDEO_TYPE_IFRAME, 'https://example.com/embed')
    assert modules == [
        {'type': 'livestream.iframe', 'config': {'url': 'https://example.com/embed'}}
    ]
    assert get_video_config_from_modules(modules) == {
        'video_type': 'iframe',
        'video_url': 'https://example.com/embed',
    }

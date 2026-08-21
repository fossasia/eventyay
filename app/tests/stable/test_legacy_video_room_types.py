from types import SimpleNamespace

import pytest
from asgiref.sync import async_to_sync
from django.core.exceptions import ValidationError
from django_scopes import scope

from eventyay.base.meetup import (
    VIDEO_TYPE_HLS,
    VIDEO_TYPE_IFRAME,
    VIDEO_TYPE_YOUTUBE,
    get_video_config_from_modules,
    get_video_module_config,
)
from eventyay.base.models import Room
from eventyay.base.services import event as event_service
from eventyay.base.services.room import (
    SUPPORTED_ROOM_MODULE_TYPES,
    unsupported_room_module_types,
    validate_room_config_patch,
)
from eventyay.core.permissions import Permission, default_roles


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


def test_create_room_rejects_unknown_module_types(monkeypatch):
    _patch_room_creation(monkeypatch)
    event = SimpleNamespace(id='event-id', has_permission_async=_allow_permission)

    with pytest.raises(ValidationError) as exc:
        async_to_sync(event_service.create_room)(
            event,
            {
                'name': 'Unknown Room',
                'description': 'should not be created',
                'modules': [{'type': 'unknown.module'}],
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


def test_create_room_still_allows_stage_iframe(monkeypatch):
    created = _patch_room_creation(monkeypatch)
    event = SimpleNamespace(id='event-id', has_permission_async=_allow_permission)

    result = async_to_sync(event_service.create_room)(
        event,
        {
            'name': 'Stage',
            'description': 'embed',
            'modules': [
                {
                    'type': 'livestream.iframe',
                    'config': {'url': 'https://example.com/embed', 'playback_mode': 'always_on'},
                }
            ],
        },
        object(),
    )

    assert result == {'room': 'room-id', 'channel': None}
    assert created['data']['module_config'][0]['type'] == 'livestream.iframe'
    assert created['data']['module_config'][0]['config']['url'] == 'https://example.com/embed'


def test_create_room_still_allows_empty_modules_for_admin_create(monkeypatch):
    created = _patch_room_creation(monkeypatch)
    event = SimpleNamespace(id='event-id', has_permission_async=_allow_permission)

    result = async_to_sync(event_service.create_room)(
        event,
        {'name': 'New', 'description': '', 'modules': []},
        object(),
    )

    assert result == {'room': 'room-id', 'channel': None}
    assert created['data']['module_config'] == []


@pytest.mark.django_db
def test_config_patch_rejects_unknown_module_types(event):
    with scope(event=event):
        room = Room.objects.create(
            event=event,
            name='Unknown',
            module_config=[{'type': 'unknown.module', 'config': {}}],
        )
        with pytest.raises(ValidationError) as exc:
            validate_room_config_patch(
                room,
                {'module_config': [{'type': 'unknown.module', 'config': {'updated': True}}]},
            )
    assert exc.value.code == 'unsupported_type'


def test_unsupported_room_module_types():
    assert unsupported_room_module_types(
        [{'type': 'unknown.module', 'config': {}}]
    ) == frozenset({'unknown.module'})
    assert unsupported_room_module_types(
        [{'type': 'chat.native', 'config': {}}]
    ) == frozenset()
    for module_type in SUPPORTED_ROOM_MODULE_TYPES:
        assert unsupported_room_module_types(
            [{'type': module_type, 'config': {}}]
        ) == frozenset()


@pytest.mark.django_db
@pytest.mark.parametrize('module_type', sorted(SUPPORTED_ROOM_MODULE_TYPES))
def test_config_patch_allows_supported_room_types(event, module_type):
    with scope(event=event):
        room = Room.objects.create(
            event=event,
            name='Kept',
            module_config=[{'type': 'chat.native', 'config': {}}],
        )
        validated, fields = validate_room_config_patch(
            room,
            {'module_config': [{'type': module_type, 'config': {}}]},
        )
    assert 'module_config' in fields
    assert validated['module_config'][0]['type'] == module_type


@pytest.mark.django_db
def test_leftover_unknown_room_can_be_renamed_or_converted(event):
    with scope(event=event):
        room = Room.objects.create(
            event=event,
            name='Old room',
            module_config=[{'type': 'unknown.module', 'config': {}}],
        )
        renamed, rename_fields = validate_room_config_patch(
            room,
            {'name': 'Renamed leftover room'},
        )
        assert 'name' in rename_fields
        assert renamed['name'] == 'Renamed leftover room'

        reset, reset_fields = validate_room_config_patch(
            room,
            {'module_config': []},
        )
        assert 'module_config' in reset_fields
        assert reset['module_config'] == []

        converted, convert_fields = validate_room_config_patch(
            room,
            {
                'module_config': [
                    {'type': 'livestream.iframe', 'config': {'url': 'https://example.com/embed'}}
                ]
            },
        )
        assert 'module_config' in convert_fields
        assert converted['module_config'][0]['type'] == 'livestream.iframe'


def test_default_roles_only_use_current_permissions():
    known = {permission.value for permission in Permission}
    flattened = {
        permission.value if isinstance(permission, Permission) else permission
        for perms in default_roles().values()
        for permission in perms
    }
    assert flattened <= known


def test_meetup_iframe_uses_stage_livestream_module():
    modules = get_video_module_config(VIDEO_TYPE_IFRAME, 'https://example.com/embed')
    assert modules == [
        {'type': 'livestream.iframe', 'config': {'url': 'https://example.com/embed'}}
    ]
    assert get_video_config_from_modules(modules) == {
        'video_type': 'iframe',
        'video_url': 'https://example.com/embed',
    }


def test_meetup_youtube_and_hls_streams_are_unchanged():
    youtube = get_video_module_config(VIDEO_TYPE_YOUTUBE, 'dQw4w9WgXcQ')
    assert youtube == [{'type': 'livestream.youtube', 'config': {'ytid': 'dQw4w9WgXcQ'}}]
    assert get_video_config_from_modules(youtube) == {
        'video_type': 'youtube',
        'video_url': 'dQw4w9WgXcQ',
    }

    hls = get_video_module_config(VIDEO_TYPE_HLS, 'https://example.com/live.m3u8')
    assert hls == [{'type': 'livestream.native', 'config': {'hls_url': 'https://example.com/live.m3u8'}}]
    assert get_video_config_from_modules(hls) == {
        'video_type': 'hls',
        'video_url': 'https://example.com/live.m3u8',
    }

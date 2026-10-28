from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from asgiref.sync import async_to_sync
from django.core.exceptions import ValidationError
from django.dispatch import Signal

from eventyay.api.auth.api_auth import RoomPermissions
from eventyay.base import entitlements
from eventyay.base.services.event import _create_room
from eventyay.base.services.video_entitlements import (
    VIDEO_MODULE_CAPABILITIES,
    check_video_entitlements,
    filter_stream_by_entitlement,
)
from eventyay.base.settings import is_room_visible_for_attendee
from eventyay.features.live.decorators import room_action
from eventyay.features.live.exceptions import ConsumerException
from eventyay.features.live.modules.room import RoomModule


pytestmark = pytest.mark.django_db


@pytest.fixture
def video_policy(monkeypatch):
    signal = Signal()
    monkeypatch.setattr(entitlements, 'entitlement_check', signal)
    denied = set()
    calls = []

    def receiver(sender, capability, event, **kwargs):
        calls.append((sender, capability, event))
        return capability not in denied

    signal.connect(receiver, weak=False)
    return denied, calls


@pytest.fixture
def video_event():
    return SimpleNamespace(organizer=object(), has_permission_implicit=Mock(return_value=True))


@pytest.mark.parametrize('module_type,capability', VIDEO_MODULE_CAPABILITIES.items())
def test_video_creation_update_and_visibility_use_organizer_policy(video_policy, video_event, module_type, capability):
    denied, calls = video_policy
    modules = [{'type': module_type}]
    room = SimpleNamespace(event=video_event, module_config=modules)
    request = SimpleNamespace(
        method='POST', event=video_event, auth={'traits': ['admin']}, data={'module_config': modules}
    )
    assert RoomPermissions().has_permission(request, None)
    assert check_video_entitlements(video_event, modules).allowed

    denied.add(capability)
    assert not RoomPermissions().has_permission(request, None)
    request.method = 'PATCH'
    assert not RoomPermissions().has_object_permission(request, None, room)
    assert not is_room_visible_for_attendee(room)
    assert calls[-1] == (video_event.organizer, capability, video_event)

    # Removing a disabled feature must remain possible.
    request.data['module_config'] = []
    assert RoomPermissions().has_object_permission(request, None, room)


def test_video_without_business_or_other_receiver_is_allowed(monkeypatch, video_event):
    monkeypatch.setattr(entitlements, 'entitlement_check', Signal())
    assert check_video_entitlements(video_event, [{'type': 'call.jitsi'}]).allowed


def test_other_video_providers_do_not_consume_jitsi_entitlement(video_policy, video_event):
    denied, calls = video_policy
    denied.update(VIDEO_MODULE_CAPABILITIES.values())
    assert check_video_entitlements(video_event, [{'type': 'livestream.native'}, {'type': 'call.zoom'}]).allowed
    assert not calls


@pytest.mark.django_db
def test_live_room_creation_denied_before_writing(video_policy, video_event):
    video_policy[0].add('video.youtube')
    with pytest.raises(ValidationError, match='plan does not include'):
        async_to_sync(_create_room)(
            {'event': video_event, 'name': 'Stage', 'module_config': [{'type': 'livestream.youtube'}]}
        )


def test_live_room_update_denied_before_writing(video_policy, video_event):
    video_policy[0].add('video.youtube')
    consumer = SimpleNamespace(event=video_event, send_error=AsyncMock())
    module = SimpleNamespace(consumer=consumer)
    # Invoke the command body; room_action itself is exercised below.
    async_to_sync(RoomModule.config_patch.__wrapped__.__wrapped__)(
        module, {'module_config': [{'type': 'livestream.youtube'}]}
    )
    assert consumer.send_error.call_args.kwargs['code'] == 'config.entitlement_denied'


@pytest.mark.parametrize('module_type', ['call.jitsi', 'call.loungemesh', 'channel.loungemesh'])
def test_join_commands_recheck_entitlement_on_existing_connection(video_policy, video_event, module_type):
    video_event.has_permission_async = AsyncMock(return_value=True)
    room = SimpleNamespace(module_config=[{'type': module_type, 'config': {}}], refresh_from_db_if_outdated=AsyncMock())
    consumer = SimpleNamespace(event=video_event, room_cache={'room-id': room}, user=object())
    module = SimpleNamespace(consumer=consumer)
    handler = AsyncMock()
    wrapped = room_action(module_required=module_type)(handler)
    async_to_sync(wrapped)(module, {'room': 'room-id'})
    assert handler.await_count == 1
    video_policy[0].add(VIDEO_MODULE_CAPABILITIES[module_type])
    with pytest.raises(ConsumerException):
        async_to_sync(wrapped)(module, {'room': 'room-id'})
    assert handler.await_count == 1


def test_cached_youtube_payload_is_filtered_after_plan_change(video_policy, video_event):
    stream = {'stream_type': 'youtube', 'url': 'https://youtube.com/example'}
    assert filter_stream_by_entitlement(video_event, stream) == stream
    video_policy[0].add('video.youtube')
    assert filter_stream_by_entitlement(video_event, stream) is None
    assert filter_stream_by_entitlement(video_event, {'stream_type': 'hls'}) == {'stream_type': 'hls'}

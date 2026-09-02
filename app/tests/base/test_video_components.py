import pytest
from django.core.exceptions import ValidationError
from django_scopes import scope

from eventyay.base.models import Room
from eventyay.base.settings import GlobalSettingsObject
from eventyay.base.video_components import (
    get_global_video_component_flags,
    is_module_type_enabled,
)
from eventyay.base.services.event import create_room

pytestmark = pytest.mark.django_db


@pytest.fixture
def gs():
    return GlobalSettingsObject()


@pytest.fixture(autouse=True)
def reset_video_settings(gs):
    for key in (
        'video_jitsi_enabled',
        'video_bbb_enabled',
        'video_janus_enabled',
        'video_streaming_enabled',
        'video_chat_channels_enabled',
        'video_qna_enabled',
        'video_polls_enabled',
    ):
        gs.settings.set(key, True)
    yield
    for key in (
        'video_jitsi_enabled',
        'video_bbb_enabled',
        'video_janus_enabled',
        'video_streaming_enabled',
        'video_chat_channels_enabled',
        'video_qna_enabled',
        'video_polls_enabled',
    ):
        gs.settings.set(key, True)


def test_global_flags_default_enabled(gs):
    flags = get_global_video_component_flags(gs)
    assert flags['jitsi'] is True
    assert flags['chat'] is True
    assert flags['bbb'] is True


def test_global_flags_respect_disabled_setting(gs):
    gs.settings.set('video_jitsi_enabled', False)
    flags = get_global_video_component_flags(gs)
    assert flags['jitsi'] is False
    assert flags['bbb'] is True


def test_apply_global_video_component_flags_enables_platform_components(event):
    event.feature_flags = {}
    flags = event.get_active_feature_flags()
    assert flags['jitsi'] is True
    assert flags['bbb'] is True
    assert flags['chat'] is True
    assert flags['stream'] is True


def test_apply_global_video_component_flags_disables_components(event, gs):
    gs.settings.set('video_jitsi_enabled', False)
    gs.settings.set('video_chat_channels_enabled', False)
    flags = event.get_active_feature_flags()
    assert flags['jitsi'] is False
    assert flags['chat'] is False
    assert flags['question'] is False
    assert flags['polls'] is False


def test_apply_global_video_component_flags_preserves_unrelated_flags(event):
    event.feature_flags = {'schedule-control': True, 'show_schedule': False}
    flags = event.get_active_feature_flags()
    assert flags['schedule-control'] is True
    assert flags['show_schedule'] is False


def test_is_module_type_enabled_for_streaming_variants(gs):
    gs.settings.set('video_streaming_enabled', False)
    assert is_module_type_enabled('livestream.native', gs=gs) is False
    assert is_module_type_enabled('livestream.youtube', gs=gs) is False


@pytest.mark.asyncio
async def test_create_room_rejects_disabled_chat(event, user, gs):
    gs.settings.set('video_chat_channels_enabled', False)
    with pytest.raises(ValidationError) as exc:
        await create_room(
            event,
            {'modules': [{'type': 'chat.native'}]},
            user,
        )
    assert 'Chat channels is currently disabled' in str(exc.value)


@pytest.mark.asyncio
async def test_create_room_allows_enabled_jitsi(event, user, gs, monkeypatch):
    monkeypatch.setattr(
        'eventyay.base.services.event.user_can_create_server_backed_room_during_development',
        lambda creator: True,
    )
    gs.settings.set('video_jitsi_enabled', True)
    gs.settings.set('video_bbb_enabled', False)
    gs.settings.set('video_janus_enabled', False)
    gs.settings.set('video_streaming_enabled', False)
    gs.settings.set('video_chat_channels_enabled', False)

    with scope(event=event):
        room = await create_room(
            event,
            {'modules': [{'type': 'call.jitsi', 'config': {}}]},
            user,
        )
    assert room is not None


def test_get_video_component_usage_counts(event, gs):
    with scope(event=event):
        Room.objects.create(
            event=event,
            name='Jitsi room',
            module_config=[{'type': 'call.jitsi'}],
        )
        Room.objects.create(
            event=event,
            name='Chat room',
            module_config=[{'type': 'chat.native'}],
        )

    from eventyay.base.video_components import get_video_component_usage

    usage = get_video_component_usage()
    assert usage['video_jitsi_enabled']['rooms'] == 1
    assert usage['video_chat_channels_enabled']['rooms'] == 1

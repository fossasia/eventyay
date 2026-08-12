from types import SimpleNamespace

import pytest
from asgiref.sync import async_to_sync
from django.core.exceptions import ValidationError
from django_scopes import scope
from rest_framework import serializers

from eventyay.api.serializers.room import RoomOrgaSerializer
from eventyay.base.models import Room
from eventyay.base.models.room import room_has_linked_submissions
from eventyay.base.models.slot import TalkSlot
from eventyay.base.services import event as event_service
from eventyay.core.permissions import (
    SYSTEM_ROLES,
    Permission,
)


async def _allow_permission(**kwargs):
    return True


class ChannelLayer:
    async def group_send(self, *args, **kwargs):
        pass


def _channel_layer():
    return ChannelLayer()


def test_video_content_manager_grants_room_create_and_edit_permissions():
    perms = set(SYSTEM_ROLES['video_content_manager'])
    assert Permission.EVENT_ROOMS_CREATE_STAGE.value in perms
    assert Permission.EVENT_ROOMS_CREATE_CHAT.value in perms
    assert Permission.EVENT_ROOMS_CREATE_BBB.value in perms
    assert Permission.EVENT_ROOMS_CREATE_JITSI.value in perms
    assert Permission.EVENT_ROOMS_CREATE_EXHIBITION.value in perms
    assert Permission.EVENT_ROOMS_CREATE_POSTER.value in perms
    assert Permission.ROOM_UPDATE.value in perms
    assert Permission.ROOM_DELETE.value in perms


def test_video_moderator_grants_engagement_without_admin_role():
    """Organizers with moderate video permission can moderate chat/users/polls
    without needing the staff admin trait/session."""
    perms = set(SYSTEM_ROLES['video_moderator'])
    assert Permission.EVENT_USERS_LIST.value in perms
    assert Permission.EVENT_USERS_MANAGE.value in perms
    assert Permission.ROOM_CHAT_MODERATE.value in perms
    assert Permission.ROOM_ANNOUNCE.value in perms
    assert Permission.ROOM_VIEWERS.value in perms
    assert Permission.ROOM_QUESTION_MODERATE.value in perms
    assert Permission.ROOM_POLL_MANAGE.value in perms
    # Must remain a scoped organizer role — not the full admin role set
    assert Permission.EVENT_UPDATE.value not in perms
    assert Permission.ROOM_UPDATE.value not in perms
    assert Permission.EVENT_CHAT_DIRECT.value not in perms


def test_video_analyst_and_config_are_split():
    assert SYSTEM_ROLES['video_analyst'] == [Permission.EVENT_GRAPHS.value]
    assert SYSTEM_ROLES['video_config_manager'] == [Permission.EVENT_UPDATE.value]
    assert Permission.EVENT_GRAPHS.value not in SYSTEM_ROLES['video_config_manager']


@pytest.mark.django_db
def test_event_grants_chat_moderate_via_organizer_video_trait(event):
    """Organizer JWT traits (without admin) must unlock room:chat.moderate."""
    trait = f'eventyay-video-event-{event.slug}-video-moderator'
    assert event.has_permission_implicit(
        traits=['attendee', trait],
        permissions=[Permission.ROOM_CHAT_MODERATE],
    )
    assert not event.has_permission_implicit(
        traits=['attendee'],
        permissions=[Permission.ROOM_CHAT_MODERATE],
    )


@pytest.mark.django_db
def test_room_has_linked_submissions(event):
    with scope(event=event):
        room = Room.objects.create(event=event, name='Empty')
        assert room_has_linked_submissions(room) is False


@pytest.mark.django_db
def test_room_queryset_annotation_for_linked_submissions(event):
    from eventyay.base.models import Submission

    with scope(event=event):
        room = Room.objects.create(event=event, name='Scheduled')
        submission = Submission.objects.create(
            event=event,
            title='Talk',
            submission_type=event.submission_types.first(),
        )
        TalkSlot.objects.create(
            room=room,
            schedule=event.wip_schedule,
            submission=submission,
        )
        annotated = event.rooms.with_has_linked_sessions().get(pk=room.pk)
        assert annotated.has_linked_sessions is True


@pytest.mark.django_db
def test_room_cannot_be_marked_unscheduled_with_linked_sessions(event):
    from eventyay.base.models import Submission

    with scope(event=event):
        room = Room.objects.create(event=event, name='Scheduled')
        submission = Submission.objects.create(
            event=event,
            title='Talk',
            submission_type=event.submission_types.first(),
        )
        TalkSlot.objects.create(
            room=room,
            schedule=event.wip_schedule,
            submission=submission,
        )
        room.is_unscheduled = True
        with pytest.raises(ValidationError) as excinfo:
            room.full_clean()
        assert 'is_unscheduled' in excinfo.value.message_dict


@pytest.mark.django_db
def test_room_orga_serializer_rejects_unscheduled_with_linked_sessions(event):
    from eventyay.base.models import Submission

    with scope(event=event):
        room = Room.objects.create(event=event, name='Scheduled')
        submission = Submission.objects.create(
            event=event,
            title='Talk',
            submission_type=event.submission_types.first(),
        )
        TalkSlot.objects.create(
            room=room,
            schedule=event.wip_schedule,
            submission=submission,
        )
        serializer = RoomOrgaSerializer(
            room,
            data={'is_unscheduled': True},
            partial=True,
        )
        with pytest.raises(serializers.ValidationError) as excinfo:
            serializer.is_valid(raise_exception=True)
        assert 'is_unscheduled' in excinfo.value.detail


@pytest.mark.django_db
def test_talk_slot_cannot_use_unscheduled_room(event):
    from eventyay.base.models import Submission
    from eventyay.base.models.room import validate_talk_slot_room

    with scope(event=event):
        room = Room.objects.create(event=event, name='Unscheduled', is_unscheduled=True)
        submission = Submission.objects.create(
            event=event,
            title='Talk',
            submission_type=event.submission_types.first(),
        )
        with pytest.raises(ValidationError) as excinfo:
            validate_talk_slot_room(room)
        assert 'room' in excinfo.value.message_dict
        slot = TalkSlot(
            room=room,
            schedule=event.wip_schedule,
            submission=submission,
        )
        with pytest.raises(ValidationError):
            slot.save()


@pytest.mark.django_db
def test_validate_room_config_patch_ignores_read_only_body_fields(event):
    from eventyay.base.services.room import validate_room_config_patch

    with scope(event=event):
        room = Room.objects.create(event=event, name='Stage')
        validated_data, update_fields = validate_room_config_patch(
            room,
            {'id': 99999, 'has_linked_sessions': True, 'name': 'Updated'},
        )
    assert validated_data == {'name': 'Updated'}
    assert update_fields == {'name'}


@pytest.mark.django_db
def test_validate_room_config_patch_ignores_malformed_jitsi_modules(event):
    from eventyay.base.services.room import validate_room_config_patch

    module_config = [
        None,
        'invalid',
        {
            'type': 'call.jitsi',
            'config': {
                'room_name': 'Main Stage',
                'app_secret': 'client-submitted-secret',
            },
        },
        {
            'type': 'call.jitsi',
            'config': 'invalid',
        },
    ]

    with scope(event=event):
        room = Room.objects.create(event=event, name='Stage')
        validated_data, update_fields = validate_room_config_patch(
            room,
            {'module_config': module_config},
        )

    assert validated_data == {
        'module_config': [
            None,
            'invalid',
            {
                'type': 'call.jitsi',
                'config': {
                    'room_name': 'Main Stage',
                },
            },
            {
                'type': 'call.jitsi',
                'config': {},
            },
        ],
    }
    assert update_fields == {'module_config'}
    assert module_config[2]['config'] == {'room_name': 'Main Stage'}


def test_get_jitsi_config_ignores_malformed_modules():
    from eventyay.base.services.jitsi import _get_jitsi_config

    module_config = [
        None,
        'invalid',
        {
            'type': 'call.jitsi',
            'config': 'invalid',
        },
    ]
    room = SimpleNamespace(module_config=module_config)

    assert _get_jitsi_config(room) == {}
    assert module_config[2]['config'] == {}


def test_normalize_jitsi_server_url_canonicalizes_host_only():
    from eventyay.base.services.jitsi import normalize_server_url

    assert normalize_server_url('meet.example.org') == {
        'domain': 'meet.example.org',
        'url': 'https://meet.example.org',
        'protocol': 'https:',
    }
    assert normalize_server_url('HTTPS://Meet.Example.Org/some/path?x=1') == {
        'domain': 'meet.example.org',
        'url': 'https://meet.example.org',
        'protocol': 'https:',
    }
    assert normalize_server_url('https:///missing-host') is None


def test_create_jitsi_room_does_not_persist_implicit_room_name(monkeypatch):
    created = {}

    async def fake_create_room(data, with_channel=False, **kwargs):
        created['data'] = data
        created['with_channel'] = with_channel
        return SimpleNamespace(id='room-id'), None

    monkeypatch.setattr(event_service, '_create_room', fake_create_room)
    monkeypatch.setattr(event_service, 'get_channel_layer', _channel_layer)
    event = SimpleNamespace(id='event-id', has_permission_async=_allow_permission)

    result = async_to_sync(event_service.create_room)(
        event,
        {
            'name': 'Main Stage',
            'description': 'a description',
            'modules': [
                {
                    'type': 'call.jitsi',
                    'config': {
                        'prefer_server': 'https://meet.example.org',
                        'start_with_audio_muted': True,
                    },
                },
            ],
        },
        object(),
    )

    jitsi = created['data']['module_config'][0]
    assert result == {'room': 'room-id', 'channel': None}
    assert created['with_channel'] is False
    assert jitsi['config'] == {
        'prefer_server': 'https://meet.example.org',
        'start_with_audio_muted': True,
        'start_with_video_muted': False,
    }


def test_jitsi_config_keeps_self_view_visible_for_moderators_and_participants():
    from eventyay.features.live.modules.jitsi import build_jitsi_config_overwrite

    module_config = {
        'start_with_audio_muted': True,
        'start_with_video_muted': False,
    }

    moderator_config = build_jitsi_config_overwrite(module_config, True)
    participant_config = build_jitsi_config_overwrite(module_config, False)

    assert moderator_config['disableSelfView'] is False
    assert participant_config['disableSelfView'] is False
    assert moderator_config['readOnlyName'] is True
    assert participant_config['readOnlyName'] is True
    assert moderator_config['enableClosePage'] is False
    assert participant_config['enableClosePage'] is False
    assert moderator_config['disableInviteFunctions'] is True
    assert participant_config['disableInviteFunctions'] is True
    assert moderator_config['hiddenPremeetingButtons'] == ['invite']
    assert participant_config['hiddenPremeetingButtons'] == ['invite']
    assert participant_config['participantsPane'] == {
        'hideModeratorSettingsTab': True,
        'hideMoreActionsButton': True,
        'hideMuteAllButton': True,
    }
    assert participant_config['breakoutRooms'] == {
        'hideModeratorSettingsTab': True,
        'hideMoreActionsButton': True,
        'hideMuteAllButton': True,
    }
    assert moderator_config['toolbarButtons']
    assert participant_config['toolbarButtons']
    assert 'invite' not in moderator_config['toolbarButtons']
    assert 'invite' not in participant_config['toolbarButtons']
    assert 'settings' in moderator_config['toolbarButtons']
    assert 'participants-pane' in moderator_config['toolbarButtons']
    assert 'polls' in moderator_config['toolbarButtons']
    assert 'shareaudio' in moderator_config['toolbarButtons']
    assert 'stats' in moderator_config['toolbarButtons']
    assert 'participantsPane' not in moderator_config


def test_jitsi_config_uses_actual_room_name_as_subject():
    from eventyay.features.live.modules.jitsi import build_jitsi_config_overwrite

    config = build_jitsi_config_overwrite({}, False, 'Main Hall')

    assert config['subject'] == 'Main Hall'

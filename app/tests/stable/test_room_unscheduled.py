import pytest
from django.core.exceptions import ValidationError
from django_scopes import scope
from rest_framework import serializers

from eventyay.api.serializers.room import RoomOrgaSerializer
from eventyay.base.models import Room, Submission
from eventyay.base.models.room import (
    ROOM_DELETE_LINKED_SESSIONS_MESSAGE,
    room_has_linked_submissions,
    validate_room_can_be_deleted,
    validate_talk_slot_room,
)
from eventyay.base.models.slot import TalkSlot
from eventyay.base.services.room import soft_delete_room
from eventyay.core.permissions import Permission, SYSTEM_ROLES


def test_video_content_manager_grants_room_create_and_edit_permissions():
    perms = set(SYSTEM_ROLES['video_content_manager'])
    assert Permission.EVENT_ROOMS_CREATE_STAGE.value in perms
    assert Permission.EVENT_ROOMS_CREATE_CHAT.value in perms
    assert Permission.EVENT_ROOMS_CREATE_BBB.value in perms
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
def test_talk_slot_cannot_use_deleted_room(event):
    with scope(event=event):
        room = Room.objects.create(event=event, name='Gone', deleted=True)
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
def test_quick_schedule_form_rejects_deleted_room(event):
    from eventyay.schedule.forms import QuickScheduleForm

    with scope(event=event):
        room = Room.objects.create(event=event, name='Stage')
        submission = Submission.objects.create(
            event=event,
            title='Talk',
            submission_type=event.submission_types.first(),
        )
        slot = TalkSlot.objects.create(
            schedule=event.wip_schedule,
            submission=submission,
        )
        form = QuickScheduleForm(
            event=event,
            instance=slot,
            data={
                'room': room.pk,
                'start_date': event.date_from.date().isoformat(),
                'start_time': '10:00',
            },
        )
        assert form.is_valid(), form.errors
        room.deleted = True
        room.save(update_fields=['deleted'])
        with pytest.raises(Room.DoesNotExist):
            form.save()


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
def test_room_cannot_be_deleted_with_linked_sessions(event):
    with scope(event=event):
        room = Room.objects.create(event=event, name='Scheduled')
        empty_room = Room.objects.create(event=event, name='Empty')
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
        validate_room_can_be_deleted(empty_room)
        with pytest.raises(ValidationError) as excinfo:
            validate_room_can_be_deleted(room)
        assert str(ROOM_DELETE_LINKED_SESSIONS_MESSAGE) in excinfo.value.messages

        with pytest.raises(ValidationError):
            soft_delete_room(event, room, by_user=None)
        room.refresh_from_db()
        assert not room.deleted

        soft_delete_room(event, empty_room, by_user=None)
        empty_room.refresh_from_db()
        assert empty_room.deleted

import pytest
from django.core.exceptions import ValidationError
from django_scopes import scope
from rest_framework import serializers

from eventyay.api.serializers.room import RoomOrgaSerializer
from eventyay.base.models import Room
from eventyay.base.models.room import room_has_linked_submissions
from eventyay.base.models.slot import TalkSlot
from eventyay.core.permissions import Permission, SYSTEM_ROLES


def test_video_poll_question_manager_grants_read_and_moderate_permissions():
    perms = set(SYSTEM_ROLES['video_poll_question_manager'])
    assert Permission.ROOM_QUESTION_READ.value in perms
    assert Permission.ROOM_QUESTION_MODERATE.value in perms
    assert Permission.ROOM_POLL_READ.value in perms
    assert Permission.ROOM_POLL_MANAGE.value in perms


def test_video_user_moderator_grants_chat_moderate_without_admin_role():
    """Organizers with manage-users video permission can delete chat messages
    without needing the staff admin trait/session."""
    perms = set(SYSTEM_ROLES['video_user_moderator'])
    assert Permission.EVENT_USERS_MANAGE.value in perms
    assert Permission.ROOM_CHAT_MODERATE.value in perms
    # Must remain a scoped organizer role — not the full admin role set
    assert Permission.EVENT_UPDATE.value not in perms
    assert Permission.ROOM_UPDATE.value not in perms


@pytest.mark.django_db
def test_event_grants_chat_moderate_via_organizer_video_trait(event):
    """Organizer JWT traits (without admin) must unlock room:chat.moderate."""
    trait = f'eventyay-video-event-{event.slug}-video-user-moderator'
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

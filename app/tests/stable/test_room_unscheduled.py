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

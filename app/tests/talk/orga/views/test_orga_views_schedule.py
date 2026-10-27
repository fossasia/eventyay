import datetime as dt
import json
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import Room, Schedule
from eventyay.common.text.phrases import phrases


@pytest.mark.django_db
@pytest.mark.usefixtures("accepted_submission")
def test_talk_list(orga_client, event, break_slot):
    response = orga_client.get(
        reverse("orga:schedule.api.talks", kwargs={"event": event.slug}), follow=True
    )
    content = json.loads(response.text)
    assert response.status_code == 200
    assert len(content["talks"]) == 2
    assert len([talk for talk in content["talks"] if talk["title"]])


@pytest.mark.django_db
def test_talk_schedule_api_create_break(orga_client, event, schedule, room):
    with scope(event=event):
        slot_count = event.wip_schedule.talks.count()
    response = orga_client.post(
        reverse("orga:schedule.api.talks", kwargs={"event": event.slug}),
        json.dumps({"room": room.pk, "duration": 50, "title": "Break"}),
        content_type="application/json",
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        assert event.wip_schedule.talks.count() == slot_count + 1
        slot = event.wip_schedule.talks.filter(submission__isnull=True).first()
        assert slot
        assert slot.description == "Break"
        assert slot.room == room
        assert slot.duration == 50


@pytest.mark.parametrize("with_room", (True, False))
@pytest.mark.django_db
def test_talk_schedule_api_update(orga_client, event, schedule, slot, room, with_room):
    with scope(event=event):
        slot = event.wip_schedule.talks.first()
        start = now()
        assert slot.start != start
    response = orga_client.patch(
        reverse(
            "orga:schedule.api.update", kwargs={"event": event.slug, "pk": slot.pk}
        ),
        data=json.dumps(
            {"room": room.pk if with_room else None, "start": start.isoformat()}
        ),
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        slot.refresh_from_db()
        content = json.loads(response.text)
        assert content["title"] == slot.submission.title
        assert slot.start == start
        assert slot.room == room


@pytest.mark.django_db
def test_talk_schedule_api_update_wrong_slot(orga_client, event, schedule, slot):
    with scope(event=event):
        slot = event.wip_schedule.talks.first()
        start = now()
        assert slot.start != start
    response = orga_client.patch(
        reverse(
            "orga:schedule.api.update",
            kwargs={"event": event.slug, "pk": slot.pk + 100},
        ),
        data=json.dumps({"room": 100, "start": start.isoformat()}),
        follow=True,
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_talk_schedule_api_update_break_slot(
    orga_client, event, schedule, break_slot, room
):
    with scope(event=event):
        slot = event.wip_schedule.talks.first()
        start = now()
        assert slot.start != start
    response = orga_client.patch(
        reverse(
            "orga:schedule.api.update", kwargs={"event": event.slug, "pk": slot.pk}
        ),
        data=json.dumps(
            {
                "room": room.pk,
                "start": start.isoformat(),
                "duration": 90,
                "title": "New break",
            }
        ),
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        slot.refresh_from_db()
        assert slot.duration == 90
        assert str(slot.description) == "New break"
        assert slot.start == start
        assert slot.room == room


@pytest.mark.django_db
def test_talk_schedule_api_update_break_slot_explicit_end(
    orga_client, event, schedule, break_slot, room
):
    with scope(event=event):
        slot = event.wip_schedule.talks.first()
        start = now()
        assert slot.start != start
    response = orga_client.patch(
        reverse(
            "orga:schedule.api.update", kwargs={"event": event.slug, "pk": slot.pk}
        ),
        data=json.dumps(
            {
                "room": room.pk,
                "start": start.isoformat(),
                "end": (start + dt.timedelta(minutes=90)).isoformat(),
                "title": "New break",
            }
        ),
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        slot.refresh_from_db()
        assert slot.duration == 90
        assert str(slot.description) == "New break"
        assert slot.start == start
        assert slot.room == room


@pytest.mark.django_db
def test_talk_schedule_api_update_break_slot_no_duration(
    orga_client, event, schedule, break_slot, room
):
    with scope(event=event):
        slot = event.wip_schedule.talks.first()
        start = now()
        assert slot.start != start
        previous_duration = slot.duration
    response = orga_client.patch(
        reverse(
            "orga:schedule.api.update", kwargs={"event": event.slug, "pk": slot.pk}
        ),
        data=json.dumps({"room": room.pk, "start": start.isoformat()}),
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        slot.refresh_from_db()
        assert slot.duration == previous_duration
        assert slot.start == start
        assert slot.room == room


@pytest.mark.django_db
def test_talk_schedule_api_delete_slot(orga_client, event, schedule, break_slot):
    with scope(event=event):
        slot = event.wip_schedule.talks.first()
        slot_count = event.wip_schedule.talks.count()
    response = orga_client.delete(
        reverse(
            "orga:schedule.api.update", kwargs={"event": event.slug, "pk": slot.pk}
        ),
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        assert event.wip_schedule.talks.count() == slot_count - 1


@pytest.mark.django_db
def test_talk_schedule_api_do_not_delete_slot_with_submission(
    orga_client, event, schedule, slot
):
    with scope(event=event):
        slot = event.wip_schedule.talks.first()
        slot_count = event.wip_schedule.talks.count()
    response = orga_client.delete(
        reverse(
            "orga:schedule.api.update", kwargs={"event": event.slug, "pk": slot.pk}
        ),
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        assert event.wip_schedule.talks.count() == slot_count


@pytest.mark.django_db
def test_talk_schedule_api_delete_bogus_slot(orga_client, event, schedule):
    response = orga_client.delete(
        reverse("orga:schedule.api.update", kwargs={"event": event.slug, "pk": 100}),
        follow=True,
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_talk_schedule_api_update_reset(orga_client, event, schedule, slot, room):
    with scope(event=event):
        slot = event.wip_schedule.talks.first()
        slot.start = now()
        slot.room = room
        slot.save()
        assert slot.start
    response = orga_client.patch(
        reverse(
            "orga:schedule.api.update", kwargs={"event": event.slug, "pk": slot.pk}
        ),
        data=json.dumps({}),
        follow=True,
    )
    with scope(event=event):
        slot.refresh_from_db()
        content = json.loads(response.text)
        assert content["title"] == slot.submission.title
        assert not slot.start
        assert not slot.room


@pytest.mark.django_db
def test_orga_can_quick_schedule_submission(
    orga_client, event, room, accepted_submission
):
    with scope(event=event):
        slot = accepted_submission.slots.get(schedule=event.wip_schedule)
        assert not slot.room
    response = orga_client.get(
        accepted_submission.orga_urls.quick_schedule, follow=True
    )
    assert response.status_code == 200
    response = orga_client.post(
        accepted_submission.orga_urls.quick_schedule,
        data={
            "start_date": event.date_from.strftime("%Y-%m-%d"),
            "start_time": "10:00:00",
            "room": room.pk,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        slot.refresh_from_db()
        assert slot.room == room, response.text
        assert slot.start.date() == event.date_from


@pytest.mark.django_db
@pytest.mark.usefixtures("accepted_submission")
@pytest.mark.usefixtures("room")
def test_orga_can_see_schedule(orga_client, event):
    response = orga_client.get(event.orga_urls.schedule, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.usefixtures("accepted_submission")
@pytest.mark.usefixtures("room")
def test_orga_can_see_schedule_release_view(orga_client, event):
    response = orga_client.get(event.orga_urls.release_schedule, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_orga_release_breaks_only_schedule_shows_warning(orga_client, event, break_slot):
    """Keep the release warning visible and allow a breaks-only schedule."""
    with scope(event=event):
        event.talks_published = True
        event.save(update_fields=['talks_published'])
        event.wip_schedule.talks.filter(submission__isnull=False).delete()
        assert Schedule.objects.count() == 2
    response = orga_client.get(event.orga_urls.release_schedule, follow=True)
    assert response.status_code == 200
    content = response.content.decode().lower()
    assert 'only breaks' in content
    assert 'please review the following before proceeding.' in content
    response = orga_client.post(
        event.orga_urls.release_schedule,
        follow=True,
        data={'version': 'breaks only'},
    )
    assert response.status_code == 200
    with scope(event=event):
        assert Schedule.objects.count() == 3
        assert event.schedules.filter(version='breaks only').exists()


@pytest.mark.django_db
@pytest.mark.usefixtures('accepted_submission')
def test_orga_release_breaks_only_with_unscheduled_submissions_shows_warning(
    orga_client, event, break_slot
):
    with scope(event=event):
        assert event.wip_schedule.talks.filter(submission__isnull=False, start__isnull=True).exists()
    response = orga_client.get(event.orga_urls.release_schedule, follow=True)
    assert response.status_code == 200
    assert 'only breaks' in response.content.decode().lower()


@pytest.mark.django_db
def test_orga_cannot_reset_to_wrong_version(orga_client, event):
    with scope(event=event):
        assert Schedule.objects.count() == 1
    response = orga_client.get(
        event.orga_urls.reset_schedule, follow=True, data={"version": "Test version 2"}
    )
    assert response.status_code == 200
    with scope(event=event):
        assert Schedule.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.usefixtures("accepted_submission")
@pytest.mark.usefixtures("room")
def test_orga_can_release_and_reset_schedule(orga_client, event):
    """Release a schedule and reset its draft without creating another release."""
    with scope(event=event):
        assert Schedule.objects.count() == 1
        event.talks_published = True
        event.save(update_fields=['talks_published'])
    response = orga_client.post(
        event.orga_urls.release_schedule,
        follow=True,
        data={"version": "Test version 2"},
    )
    assert response.status_code == 200
    with scope(event=event):
        assert Schedule.objects.count() == 2
    response = orga_client.get(
        event.orga_urls.reset_schedule, follow=True, data={"version": "Test version 2"}
    )
    assert response.status_code == 200
    with scope(event=event):
        assert Schedule.objects.count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    'version', ('wip', 'latest', ' wip ', ' latest ', 'WIP', 'Wip', 'LATEST', 'Latest', ' wIp ', ' LaTeSt '),
)
@pytest.mark.parametrize('has_wip', (True, False))
def test_orga_cannot_release_reserved_schedule_version(orga_client, event, slot, version, has_wip):
    """Reject reserved names without changing schedules, even with no draft."""
    with scope(event=event):
        event.talks_published = True
        event.save(update_fields=['talks_published'])
        if not has_wip:
            draft = event.schedules.get(version__isnull=True)
            draft.talks.all().delete()
            draft.delete()
        schedules = list(event.schedules.order_by('pk').values_list('pk', 'version', 'published'))
        original_slot = (slot.schedule_id, slot.start, slot.end, slot.room_id)
        mail_count = event.queued_mails.count()

    response = orga_client.post(event.orga_urls.release_schedule, data={'version': version})

    assert response.status_code == 200
    assert response.text.count('This schedule version is reserved. Please choose a different name.') == 1
    assert str(phrases.base.error_saving_changes) not in response.text
    with scope(event=event):
        assert list(event.schedules.order_by('pk').values_list('pk', 'version', 'published')) == schedules
        slot.refresh_from_db()
        assert (slot.schedule_id, slot.start, slot.end, slot.room_id) == original_slot
        assert event.queued_mails.count() == mail_count


@pytest.mark.django_db
def test_orga_release_preserves_non_field_error(orga_client, event):
    """Keep the publication error visible without an additional generic banner."""
    event.talks_published = False
    event.private_testmode = False
    event.save(update_fields=['talks_published', 'private_testmode'])

    response = orga_client.post(event.orga_urls.release_schedule, data={'version': '0.2'})

    assert response.status_code == 400
    assert response.text.count('Talks must be published or in private test mode to release a schedule.') == 1
    assert str(phrases.base.error_saving_changes) not in response.text


@pytest.mark.django_db
@pytest.mark.usefixtures("accepted_submission")
@pytest.mark.usefixtures("room")
def test_orga_cannot_reuse_schedule_name(orga_client, event):
    """Show only the version-field error when a release name is reused."""
    with scope(event=event):
        assert Schedule.objects.count() == 1
        event.talks_published = True
        event.save(update_fields=['talks_published'])
    response = orga_client.post(
        event.orga_urls.release_schedule,
        follow=True,
        data={"version": "Test version 2"},
    )
    assert response.status_code == 200
    with scope(event=event):
        assert Schedule.objects.count() == 2
        assert Schedule.objects.get(version="Test version 2")
    response = orga_client.post(
        event.orga_urls.release_schedule,
        follow=True,
        data={"version": "Test version 2"},
    )
    assert response.status_code == 200
    assert response.text.count('This schedule version was used already, please choose a different one.') == 1
    assert 'You have to provide a new, unique schedule version!' not in response.text
    assert str(phrases.base.error_saving_changes) not in response.text
    with scope(event=event):
        assert Schedule.objects.count() == 2


@pytest.mark.django_db
def test_orga_can_toggle_schedule_visibility(orga_client, event):
    from eventyay.base.models import Event

    assert event.feature_flags["show_schedule"] is True
    response = orga_client.get(event.orga_urls.toggle_schedule)
    assert response.status_code == 405
    event = Event.objects.get(pk=event.pk)
    assert event.feature_flags["show_schedule"] is True

    page = orga_client.get(event.orga_urls.schedule)
    assert page.status_code == 200
    assert page.text.count("Unpublish schedule") == 1
    assert "Make schedule public" not in page.text
    assert "Visitors will see sessions as coming soon until you publish it again." in page.text

    response = orga_client.post(event.orga_urls.toggle_schedule, follow=True)
    assert response.status_code == 200
    assert response.text.count("Make schedule public") == 1
    assert "Unpublish schedule" not in response.text
    assert "Visitors will be able to see the released schedule." in response.text
    event = Event.objects.get(pk=event.pk)
    assert event.feature_flags["show_schedule"] is False

    response = orga_client.post(event.orga_urls.toggle_schedule)
    assert response.status_code == 302
    event = Event.objects.get(pk=event.pk)
    with scope(event=event):
        assert event.feature_flags["show_schedule"] is True


@pytest.mark.django_db
def test_toggle_schedule_visibility_rejects_get(orga_client, event):
    from eventyay.base.models import Event

    assert event.feature_flags["show_schedule"] is True
    response = orga_client.get(event.orga_urls.toggle_schedule)
    assert response.status_code == 405
    event = Event.objects.get(pk=event.pk)
    assert event.feature_flags["show_schedule"] is True


@pytest.mark.django_db
def test_create_room(orga_client, event, availability):
    with scope(event=event):
        assert event.rooms.count() == 0
    response = orga_client.post(
        event.orga_urls.new_room,
        follow=True,
        data={
            "name_0": "A room",
            "guid": uuid4(),
            "availabilities": json.dumps(
                {
                    "availabilities": [
                        {
                            "start": availability.start.strftime("%Y-%m-%d %H:%M:00Z"),
                            "end": availability.end.strftime("%Y-%m-%d %H:%M:00Z"),
                        }
                    ]
                }
            ),
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        assert event.rooms.count() == 1
        assert str(event.rooms.first().name) == "A room"
        assert event.rooms.first().availabilities.count() == 1
        assert event.rooms.first().availabilities.first().start == availability.start


@pytest.mark.django_db
@pytest.mark.usefixtures("room_availability")
def test_edit_room(orga_client, event, room):
    with scope(event=event):
        assert event.rooms.count() == 1
        assert event.rooms.first().availabilities.count() == 1
        assert str(event.rooms.first().name) != "A room"
    response = orga_client.post(
        room.urls.edit,
        follow=True,
        data={
            "name_0": "A room",
            "guid": uuid4(),
            "availabilities": '{"availabilities": []}',
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        assert event.rooms.count() == 1
        assert str(event.rooms.first().name) == "A room"
        assert event.rooms.first().availabilities.count() == 0


@pytest.mark.django_db
def test_delete_room(orga_client, event, room):
    with scope(event=event):
        assert event.rooms.filter(deleted=False).count() == 1
    response = orga_client.get(room.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert event.rooms.filter(deleted=False).count() == 1
    response = orga_client.post(room.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        room.refresh_from_db()
        assert room.deleted
        assert event.rooms.filter(deleted=False).count() == 0


@pytest.mark.django_db
def test_delete_used_room(orga_client, event, room, slot):
    with scope(event=event):
        assert event.rooms.filter(deleted=False).count() == 1
        wip_slot = event.wip_schedule.talks.get(submission=slot.submission)
    assert slot.room == room
    response = orga_client.get(room.urls.delete, follow=True)
    assert response.status_code == 200
    assert b'linked schedules/sessions' in response.content
    assert f'?room={room.pk}'.encode() in response.content
    assert b'Unassign all sessions' in response.content
    assert b'Open room in schedule editor' in response.content
    assert b'Open in schedule' not in response.content
    assert b'1 linked session' in response.content
    with scope(event=event):
        assert event.rooms.filter(deleted=False).count() == 1
    response = orga_client.post(
        room.urls.delete,
        {'action': 'unassign_sessions'},
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        wip_slot.refresh_from_db()
        slot.refresh_from_db()
        assert wip_slot.room is None
        assert wip_slot.start is None
        assert wip_slot.end is None
        assert slot.room is None
        room.refresh_from_db()
        assert not room.deleted
    assert b'Unassigned 1 session from this room.' in response.content
    response = orga_client.post(room.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        room.refresh_from_db()
        assert room.deleted
        assert event.rooms.filter(deleted=False).count() == 0


@pytest.mark.django_db
def test_delete_room_with_released_only_linked_session(orga_client, event, room, slot):
    """Released-schedule links must still surface on the delete confirm page."""
    with scope(event=event):
        event.wip_schedule.talks.filter(submission=slot.submission).update(
            room=None,
            start=None,
            end=None,
        )
        slot.refresh_from_db()
        assert slot.room == room
        assert not event.wip_schedule.talks.filter(
            room=room, submission__isnull=False
        ).exists()

    response = orga_client.get(room.urls.delete, follow=True)
    assert response.status_code == 200
    assert b'linked schedules/sessions' in response.content
    assert b'Unassign all sessions' in response.content
    assert str(slot.submission.title).encode() in response.content

    response = orga_client.post(
        room.urls.delete,
        {'action': 'unassign_sessions'},
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        slot.refresh_from_db()
        assert slot.room is None
    assert b'Unassigned 1 session from this room.' in response.content

    response = orga_client.post(room.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        room.refresh_from_db()
        assert room.deleted


@pytest.mark.django_db
def test_regenerate_speaker_notifications(orga_client, event, slot):
    with scope(event=event):
        queue_count = event.queued_mails.count()
    response = orga_client.post(
        event.orga_urls.schedule + "resend_mails",
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        assert event.queued_mails.count() > queue_count
        mail = event.queued_mails.last()
        assert slot.submission.title in mail.text
        assert str(slot.room.name) in mail.text
        assert mail.submissions.count() == 1


@pytest.mark.django_db
def test_regenerate_speaker_notifications_before_schedule(orga_client, event):
    with scope(event=event):
        queue_count = event.queued_mails.count()
    response = orga_client.post(
        event.orga_urls.schedule + "resend_mails",
        follow=True,
    )
    assert response.status_code == 200
    assert (
        "You can only regenerate mails after the first schedule was released."
        in response.text
    )
    with scope(event=event):
        assert event.queued_mails.count() == queue_count


@pytest.mark.django_db
def test_orga_cant_export_answers_csv_empty(orga_client, speaker, event, submission):
    response = orga_client.post(
        event.orga_urls.schedule_export,
        data={
            "target": "rejected",
            "title": "on",
            "export_format": "csv",
        },
    )
    assert response.status_code == 200
    assert response.text.strip().startswith(
        "<!DOCTYPE"
    )  # HTML response instead of empty download


@pytest.mark.django_db
def test_orga_cant_export_answers_csv_without_delimiter(
    orga_client, speaker, event, submission, answered_choice_question
):
    with scope(event=event):
        answered_choice_question.target = "submission"
        answered_choice_question.save()
    response = orga_client.post(
        event.orga_urls.schedule_export,
        data={
            "target": "all",
            "title": "on",
            f"question_{answered_choice_question.id}": "on",
            "export_format": "csv",
        },
    )
    assert response.status_code == 200
    assert response.text.strip().startswith("<!DOCTYPE")


@pytest.mark.django_db
def test_orga_can_export_answers_csv(
    orga_client, speaker, event, submission, answered_choice_question
):
    with scope(event=event):
        answered_choice_question.target = "submission"
        answered_choice_question.save()
        answer = answered_choice_question.answers.all().first().answer_string
    response = orga_client.post(
        event.orga_urls.schedule_export,
        data={
            "target": "all",
            "title": "on",
            f"question_{answered_choice_question.id}": "on",
            "speaker_ids": "on",
            "export_format": "csv",
            "data_delimiter": "comma",
        },
    )
    assert response.status_code == 200
    assert (
        response.text
        == f"ID,Proposal title,Speaker IDs,{answered_choice_question.question}\r\n{submission.code},{submission.title},{speaker.code},{answer}\r\n"
    )


@pytest.mark.django_db
def test_orga_can_export_answers_json(
    orga_client, speaker, event, submission, answered_choice_question
):
    with scope(event=event):
        answered_choice_question.target = "submission"
        answered_choice_question.save()
        answer = answered_choice_question.answers.all().first().answer_string
    response = orga_client.post(
        event.orga_urls.schedule_export,
        data={
            "target": "all",
            "title": "on",
            f"question_{answered_choice_question.id}": "on",
            "speaker_ids": "on",
            "export_format": "json",
        },
    )
    assert response.status_code == 200
    assert json.loads(response.text) == [
        {
            "ID": submission.code,
            "Proposal title": submission.title,
            answered_choice_question.question: answer,
            "Speaker IDs": [speaker.code],
        }
    ]


@pytest.mark.django_db
def test_room_delete_view_shows_linked_shift_warning(orga_client, event, room):
    from teamshifts.models import Shift, ShiftLocation

    with scope(event=event):
        location = ShiftLocation.objects.create(
            event=event, name=room.name, linked_room=room
        )
        Shift.objects.create(
            event=event,
            location=location,
            start_time=now(),
            end_time=now() + dt.timedelta(hours=1),
        )
    response = orga_client.get(
        reverse(
            "orga:schedule.rooms.delete", kwargs={"organizer": event.organizer.slug, "event": event.slug, "pk": room.pk}
        )
    )
    assert response.status_code == 200
    assert response.context["has_linked_shifts"] is True
    assert response.context["linked_shift_count"] == 1


@pytest.mark.django_db
def test_room_delete_view_without_linked_shifts(orga_client, event, room):
    response = orga_client.get(
        reverse(
            "orga:schedule.rooms.delete", kwargs={"organizer": event.organizer.slug, "event": event.slug, "pk": room.pk}
        )
    )
    assert response.status_code == 200
    assert response.context["has_linked_shifts"] is False
    assert response.context["linked_shift_count"] == 0


@pytest.mark.django_db
def test_room_list_view_marks_rooms_with_linked_shifts(orga_client, event, room):
    from teamshifts.models import Shift, ShiftLocation

    with scope(event=event):
        location = ShiftLocation.objects.create(
            event=event, name=room.name, linked_room=room
        )
        Shift.objects.create(
            event=event,
            location=location,
            start_time=now(),
            end_time=now() + dt.timedelta(hours=1),
        )
    response = orga_client.get(
        reverse("orga:schedule.rooms.list", kwargs={"organizer": event.organizer.slug, "event": event.slug})
    )
    assert response.status_code == 200
    listed_room = next(
        r for r in response.context["room_list"] if r.pk == room.pk
    )
    assert listed_room.has_linked_shifts is True


@pytest.mark.django_db
def test_room_list_view_survives_missing_linked_room_column(
    orga_client, event, room, monkeypatch
):
    """The linked_room lookup must not break the Talks room list when
    teamshifts code is deployed ahead of its own migration (the column
    doesn't exist yet in the database)."""
    from django.db import DatabaseError
    from teamshifts.models import ShiftLocation

    def raise_missing_column(*args, **kwargs):
        raise DatabaseError(
            'column "teamshifts_shiftlocation"."linked_room_id" does not exist'
        )

    monkeypatch.setattr(ShiftLocation.objects, "filter", raise_missing_column)
    response = orga_client.get(
        reverse("orga:schedule.rooms.list", kwargs={"organizer": event.organizer.slug, "event": event.slug})
    )
    assert response.status_code == 200
    listed_room = next(
        r for r in response.context["room_list"] if r.pk == room.pk
    )
    assert listed_room.has_linked_shifts is False


@pytest.mark.django_db
def test_room_list_sorting(orga_client, event):
    url = reverse(
        "orga:schedule.rooms.list",
        kwargs={"organizer": event.organizer.slug, "event": event.slug},
    )
    with scope(event=event):
        r1 = Room.objects.create(event=event, name="Beta Room", capacity=100, position=2)
        r2 = Room.objects.create(event=event, name="Alpha Room", capacity=250, position=1)
        r3 = Room.objects.create(event=event, name="Gamma Room", capacity=50, position=3)

    # Default sort (no ?sort) preserves position order and enables reordering
    response = orga_client.get(url)
    assert response.status_code == 200
    assert response.context["can_reorder"] is True
    assert "dragsort-button" in response.text
    pks = [r.pk for r in response.context["room_list"]]
    assert pks == [r2.pk, r1.pk, r3.pk]

    # Sort by name ascending (a-z) disables manual reordering and shows caret-up
    response = orga_client.get(f"{url}?sort=name")
    assert response.status_code == 200
    assert response.context["can_reorder"] is False
    assert "dragsort-button" not in response.text
    assert "Reset to default order" in response.text
    pks = [r.pk for r in response.context["room_list"]]
    assert pks == [r2.pk, r1.pk, r3.pk]
    assert "fa-caret-up" in response.text
    assert "text-primary" in response.text

    # Reordering via POST while field sort is active must be rejected
    reorder_res = orga_client.post(f"{url}?sort=name", {"order": f"{r1.pk},{r2.pk},{r3.pk}"})
    assert reorder_res.status_code == 400

    # Sort by name descending (z-a)
    response = orga_client.get(f"{url}?sort=-name")
    assert response.status_code == 200
    assert response.context["can_reorder"] is False
    assert "dragsort-button" not in response.text
    pks = [r.pk for r in response.context["room_list"]]
    assert pks == [r3.pk, r1.pk, r2.pk]
    assert "fa-caret-down" in response.text

    # Sort by capacity ascending
    response = orga_client.get(f"{url}?sort=capacity")
    assert response.status_code == 200
    assert response.context["can_reorder"] is False
    pks = [r.pk for r in response.context["room_list"]]
    assert pks == [r3.pk, r1.pk, r2.pk]

    # Sort by capacity descending (high to low)
    response = orga_client.get(f"{url}?sort=-capacity")
    assert response.status_code == 200
    assert response.context["can_reorder"] is False
    pks = [r.pk for r in response.context["room_list"]]
    assert pks == [r2.pk, r1.pk, r3.pk]


@pytest.mark.django_db
def test_room_list_sorting_multilingual(orga_client, orga_user, event):
    url = reverse(
        "orga:schedule.rooms.list",
        kwargs={"organizer": event.organizer.slug, "event": event.slug},
    )
    with scope(event=event):
        event.locales = ["en", "de"]
        event.settings.locales = ["en", "de"]
        event.save()
        # r1 is Beta in English, Alpha in German
        r1 = Room.objects.create(event=event, name={"en": "Beta Room", "de": "Alpha Raum"}, position=1)
        # r2 is Alpha in English, Beta in German
        r2 = Room.objects.create(event=event, name={"en": "Alpha Room", "de": "Beta Raum"}, position=2)
        # r3 has only English, tests fallback in German
        r3 = Room.objects.create(event=event, name={"en": "Gamma Room"}, position=3)

    # In English: "Alpha Room" (r2) < "Beta Room" (r1) < "Gamma Room" (r3)
    orga_user.locale = "en"
    orga_user.save()
    response = orga_client.get(f"{url}?sort=name")
    assert response.status_code == 200
    pks = [r.pk for r in response.context["room_list"]]
    assert pks == [r2.pk, r1.pk, r3.pk]

    # In German: "Alpha Raum" (r1) < "Beta Raum" (r2) < "Gamma Room" (r3 fallback)
    orga_user.locale = "de"
    orga_user.save()
    response = orga_client.get(f"{url}?sort=name")
    assert response.status_code == 200
    pks = [r.pk for r in response.context["room_list"]]
    assert pks == [r1.pk, r2.pk, r3.pk]


@pytest.mark.django_db
def test_room_list_sorting_malformed_brace_text(orga_client, event):
    url = reverse(
        "orga:schedule.rooms.list",
        kwargs={"organizer": event.organizer.slug, "event": event.slug},
    )
    with scope(event=event):
        # Create rooms with malformed brace-prefixed strings and plain strings
        r1 = Room.objects.create(event=event, name="{Room", position=1)
        r2 = Room.objects.create(event=event, name="Alpha Room", position=2)
        r3 = Room.objects.create(event=event, name="{Room}", position=3)
        r4 = Room.objects.create(event=event, name={"en": "Beta Room"}, position=4)
        r5 = Room.objects.create(event=event, name='{"en": invalid}', position=5)

    # Must sort safely without raising database JSON syntax errors
    response = orga_client.get(f"{url}?sort=name")
    assert response.status_code == 200
    pks = [r.pk for r in response.context["room_list"]]
    assert set(pks) == {r1.pk, r2.pk, r3.pk, r4.pk, r5.pk}
    assert pks.index(r2.pk) < pks.index(r4.pk)


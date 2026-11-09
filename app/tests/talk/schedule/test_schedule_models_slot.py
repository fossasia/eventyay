import datetime as dt

import pytest
import vobject
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import TalkSlot


@pytest.mark.django_db
@pytest.mark.parametrize(
    "start,end,duration,has_submission",
    (
        (None, None, "sub", True),
        (0, None, "sub", True),
        (None, 0, "sub", True),
        (0, 1, 1, True),
        (None, None, None, False),
        (0, None, None, False),
        (None, 0, None, False),
        (0, 1, 1, False),
    ),
)
def test_slot_duration(submission, start, end, duration, has_submission):
    _now = now()
    if start is not None:
        start = _now + dt.timedelta(minutes=start)
    if end is not None:
        end = _now + dt.timedelta(minutes=end)
    slot = TalkSlot(
        start=start, end=end, submission=submission if has_submission else None
    )
    if duration == "sub":
        assert slot.duration == submission.get_duration()
    else:
        assert slot.duration == duration


@pytest.mark.django_db
def test_slot_string(slot, room):
    str(slot)
    str(room)


@pytest.mark.django_db
def test_slot_build_empty_ical(slot):
    slot.room = None
    assert not slot.build_ical(None)


@pytest.mark.django_db
def test_slot_build_ical_description_is_plain_text(slot):
    with scope(event=slot.submission.event):
        slot.submission.abstract = '<p>First paragraph &amp; more.</p><p>Second paragraph.</p>'
        calendar = vobject.iCalendar()
        slot.build_ical(calendar)

    description = calendar.vevent.description.value
    assert description == 'First paragraph & more.\n\nSecond paragraph.'
    assert '<' not in calendar.serialize()


@pytest.mark.django_db
def test_slot_warnings_without_room(slot):
    with scope(event=slot.event):
        slot.room = None
        slot.save()
        assert slot.start
        assert not slot.schedule.get_talk_warnings(slot)


@pytest.mark.django_db
def test_slot_warnings_when_room_unavailable(slot, room_availability):
    with scope(event=slot.event):
        slot.start = room_availability.end
        slot.end = slot.start + dt.timedelta(minutes=30)
        slot.save()
        warnings = slot.schedule.get_talk_warnings(slot)
        assert len(warnings) == 1
        assert warnings[0]["type"] == "room"


@pytest.mark.django_db
def test_slot_no_warnings_when_room_available(slot, room_availability):
    with scope(event=slot.event):
        warnings = slot.schedule.get_talk_warnings(slot)
        assert not warnings


@pytest.mark.django_db
def test_slot_warning_when_speaker_unavailable(slot, availability, room_availability):
    with scope(event=slot.event):
        availability.start -= dt.timedelta(days=7)
        availability.end -= dt.timedelta(days=7)
        availability.person = slot.submission.speakers.first().event_profile(slot.event)
        availability.pk = None
        availability.save()
        warnings = slot.schedule.get_talk_warnings(slot)
        assert len(warnings) == 1
        assert warnings[0]["type"] == "speaker"
        assert (
            warnings[0]["message"]
            == "Jane Speaker is not available at the scheduled time."
        )


@pytest.mark.django_db
def test_slot_warning_when_speaker_overbooked(
    slot, availability, other_slot, room_availability
):
    with scope(event=slot.event):
        availability.person = slot.submission.speakers.first().event_profile(slot.event)
        availability.pk = None
        availability.save()
        other_slot.start = slot.start + dt.timedelta(minutes=10)
        other_slot.end = slot.end - dt.timedelta(minutes=10)
        other_slot.submission.speakers.add(availability.person.user)
        other_slot.save()
        other_slot.submission.save()
        warnings = slot.schedule.get_talk_warnings(slot)
        assert len(warnings) == 2
        assert warnings[0]["type"] == "room_overlap"
        assert (
            warnings[0]["message"]
            == "Another session in the same room overlaps with this one."
        )
        assert warnings[1]["type"] == "speaker"
        assert (
            warnings[1]["message"]
            == "Jane Speaker is scheduled for another session at the same time."
        )


@pytest.mark.django_db
def test_speaker_overlap_warning_when_slot_contains_another(slot, other_slot):
    """A later slot that ends at the same time as an earlier one still conflicts.

    The earlier comparison missed this shape, so a session moved to before 9:00
    could contain another session and lose the speaker warning.
    """
    with scope(event=slot.event):
        start = slot.local_start.replace(hour=7, minute=0, second=0, microsecond=0)
        slot.start = start
        slot.end = start + dt.timedelta(hours=2)
        slot.save()
        other_slot.start = start + dt.timedelta(hours=1)
        other_slot.end = slot.end
        other_slot.submission.speakers.add(slot.submission.speakers.first())
        other_slot.save()

        for talk in (slot, other_slot):
            warnings = talk.schedule.get_talk_warnings(talk)
            assert any(
                warning["message"].endswith("at the same time.") for warning in warnings
            )

        by_pk = {
            talk.pk: warnings
            for talk, warnings in slot.schedule.get_all_talk_warnings().items()
        }
        for talk_pk in (slot.pk, other_slot.pk):
            assert any(
                warning["message"].endswith("at the same time.")
                for warning in by_pk[talk_pk]
            )

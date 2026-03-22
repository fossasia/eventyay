"""Test the alarm time computation.

Events can have alarms.
Alarms can be in this state:

- active - the user wants the alarm to pop up
- acknowledged - the user no longer wants the alarm
- snoozed - the user moved that alarm to another time

The alarms can only work on the properties of the event like
DTSTART, DTEND, and DURATION.

See https://github.com/collective/icalendar/issues/716
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from icalendar.alarms import Alarms
from icalendar.cal.alarm import Alarm
from icalendar.cal.event import Event
from icalendar.error import IncompleteAlarmInformation
from icalendar.prop import vDatetime
from icalendar.tools import normalize_pytz

UTC = timezone.utc
EXAMPLE_TRIGGER = datetime(1997, 3, 17, 13, 30, tzinfo=UTC)


def test_absolute_alarm_time_rfc_example(alarms):
    """Check that the absolute alarm is recognized.

    The following example is for a "VALARM" calendar component
    that specifies an audio alarm that will sound at a precise time
    and repeat 4 more times at 15-minute intervals:
    """
    a = Alarms(alarms.rfc_5545_absolute_alarm_example)
    times = a.times
    assert len(times) == 5
    for i, t in enumerate(times):
        assert t.trigger == EXAMPLE_TRIGGER + timedelta(minutes=15 * i)


alarm_1 = Alarm()
alarm_1.add("TRIGGER", EXAMPLE_TRIGGER)
alarm_2 = Alarm()
alarm_2["TRIGGER"] = vDatetime(EXAMPLE_TRIGGER)


@pytest.mark.parametrize("alarm", [alarm_1, alarm_2])
def test_absolute_alarm_time_with_vDatetime(alarm):
    """Check that the absolute alarm is recognized.

    The following example is for a "VALARM" calendar component
    that specifies an audio alarm that will sound at a precise time
    and repeat 4 more times at 15-minute intervals:
    """
    a = Alarms(alarm)
    times = a.times
    assert len(times) == 1
    assert times[0].trigger == EXAMPLE_TRIGGER


alarm_incomplete_1 = Alarm()
alarm_incomplete_1.TRIGGER = timedelta(hours=2)
alarm_incomplete_1.DURATION = timedelta(hours=1)
alarm_incomplete_2 = Alarm()
alarm_incomplete_2.TRIGGER = timedelta(hours=2)
alarm_incomplete_2.REPEAT = 100


@pytest.mark.parametrize("alarm", [alarm_incomplete_1, alarm_incomplete_2])
def test_alarm_has_only_one_of_repeat_or_duration(alarm):
    """This is an edge case and we should ignore the repetition."""
    a = Alarms(alarm)
    a.set_start(datetime(2027, 12, 2))
    assert len(a.times) == 1


@pytest.fixture(params=[(0, timedelta(minutes=-30)), (1, timedelta(minutes=-25))])
def alarm_before_start(calendars, request):
    """An example alarm relative to the start of a component."""
    index, td = request.param
    alarm = calendars.alarm_etar_future.subcomponents[-1].subcomponents[index]
    assert isinstance(alarm, Alarm)
    assert alarm.get("TRIGGER").dt == td
    alarm.test_td = td
    return alarm


def test_cannot_compute_relative_alarm_without_start(alarm_before_start):
    """We have an alarm without a start of a component."""
    with pytest.raises(IncompleteAlarmInformation) as e:
        Alarms(alarm_before_start).times  # noqa: B018, RUF100
    assert (
        e.value.args[0]
        == f"Use {Alarms.__name__}.{Alarms.set_start.__name__} because at least one alarm is relative to the start of a component."
    )


@pytest.mark.parametrize(
    ("dtstart", "timezone", "trigger"),
    [
        (
            datetime(2024, 10, 29, 13, 10),
            "UTC",
            datetime(2024, 10, 29, 13, 10, tzinfo=UTC),
        ),
        (date(2024, 11, 16), None, datetime(2024, 11, 16, 0, 0)),
        (
            datetime(2024, 10, 29, 13, 10),
            "Asia/Singapore",
            datetime(2024, 10, 29, 5, 10, tzinfo=UTC),
        ),
        (datetime(2024, 10, 29, 13, 20), None, datetime(2024, 10, 29, 13, 20)),
    ],
)
def test_can_complete_relative_calculation_if_a_start_is_given(
    alarm_before_start, dtstart, timezone, trigger, tzp
):
    """The start is given and required."""
    start = dtstart if timezone is None else tzp.localize(dtstart, timezone)
    alarms = Alarms(alarm_before_start)
    alarms.set_start(start)
    assert len(alarms.times) == 1
    time = alarms.times[0]
    expected_trigger = normalize_pytz(trigger + alarm_before_start.test_td)
    assert time.trigger == expected_trigger


@pytest.mark.parametrize("dtstart", [date(1998, 10, 1), date(2023, 12, 31)])
def test_start_as_date_with_delta_as_date_stays_date(alarms, dtstart):
    """If we have an alarm with a day delta and the event is a day event, we should stay as a date."""
    a = Alarms(alarms.start_date)
    a.set_start(dtstart)
    assert len(a.times) == 1
    assert a.times[0].trigger == dtstart - timedelta(days=2)


def test_cannot_compute_relative_alarm_without_end(alarms):
    """We have an alarm without an end of a component."""
    with pytest.raises(IncompleteAlarmInformation) as e:
        Alarms(alarms.rfc_5545_end).times  # noqa: B018, RUF100
    assert (
        e.value.args[0]
        == f"Use {Alarms.__name__}.{Alarms.set_end.__name__} because at least one alarm is relative to the end of a component."
    )


@pytest.mark.parametrize(
    ("dtend", "timezone", "trigger"),
    [
        (
            datetime(2024, 10, 29, 13, 10),
            "UTC",
            datetime(2024, 10, 29, 13, 10, tzinfo=UTC),
        ),
        (date(2024, 11, 16), None, date(2024, 11, 16)),
        (
            datetime(2024, 10, 29, 13, 10),
            "Asia/Singapore",
            datetime(2024, 10, 29, 5, 10, tzinfo=UTC),
        ),
        (datetime(2024, 10, 29, 13, 20), None, datetime(2024, 10, 29, 13, 20)),
    ],
)
def test_can_complete_relative_calculation(alarms, dtend, timezone, trigger, tzp):
    """The start is given and required."""
    start = dtend if timezone is None else tzp.localize(dtend, timezone)
    alarms = Alarms(alarms.rfc_5545_end)
    alarms.set_end(start)
    assert len(alarms.times) == 1
    time = alarms.times[0]
    expected_trigger = normalize_pytz(trigger - timedelta(days=2))
    assert time.trigger == expected_trigger


@pytest.mark.parametrize("dtend", [date(1998, 10, 1), date(2023, 12, 31)])
def test_end_as_date_with_delta_as_date_stays_date(alarms, dtend):
    """If we have an alarm with a day delta and the event is a day event, we should stay as a date."""
    a = Alarms(alarms.rfc_5545_end)
    a.set_end(dtend)
    assert len(a.times) == 1
    assert a.times[0].trigger == dtend - timedelta(days=2)


def test_add_multiple_alarms(alarms):
    """We can add multiple alarms."""
    a = Alarms()
    a.add_alarm(alarms.start_date)
    a.add_alarm(alarms.rfc_5545_end)
    a.add_alarm(alarms.rfc_5545_absolute_alarm_example)
    with pytest.raises(IncompleteAlarmInformation):
        a.times  # noqa: B018, RUF100
    a.set_start(datetime(2012, 3, 5))
    with pytest.raises(IncompleteAlarmInformation):
        a.times  # noqa: B018, RUF100
    a.set_end(datetime(2012, 3, 5))
    assert len(a.times) == 7


def test_alarms_from_event_have_right_times(calendars):
    """We can collect from an event."""
    event = calendars.alarm_etar_future.subcomponents[-1]
    a = Alarms(event)
    assert len(a.times) == 3
    assert a.times[0].parent == event


def test_cannot_set_the_event_twice(calendars):
    """We cannot set an event twice. This make the state ambiguous."""
    event = calendars.alarm_etar_future.subcomponents[-1]
    a = Alarms()
    a.add_component(event)
    a.add_component(event)  # same component is ok
    with pytest.raises(ValueError):
        a.add_component(calendars.alarm_google_future.subcomponents[-1])


@pytest.mark.parametrize(
    ("calendar", "index", "count", "message"),
    [
        ("alarm_etar_future", -1, 3, "Etar (1): we just created the alarm"),
        ("alarm_etar_notification", -1, 2, "Etar (2): the notification popped up"),
        (
            "alarm_etar_notification_clicked",
            -1,
            0,
            "Etar (3): the notification was dismissed",
        ),  # TODO: check that that is really true
        (
            "alarm_google_future",
            -1,
            4,
            "Google (1): we just created the event with alarms",
        ),
        (
            "alarm_google_acknowledged",
            -1,
            2,
            "Google (2): 2 alarms happened at the same time",
        ),
        ("alarm_thunderbird_future", -1, 2, "Thunderbird (1.1): 2 alarms are set"),
        (
            "alarm_thunderbird_snoozed_until_1457",
            -1,
            2,
            "Thunderbird (1.2): 2 alarms are snoozed to another time",
        ),
        (
            "alarm_thunderbird_closed",
            -1,
            0,
            "Thunderbird (1.3): all alarms are dismissed (closed)",
        ),
        ("alarm_thunderbird_2_future", -1, 2, "Thunderbird (2.1): 2 alarms active"),
        (
            "alarm_thunderbird_2_notification_popped_up",
            -1,
            2,
            "Thunderbird (2.2): one alarm popped up as a notification",
        ),
        (
            "alarm_thunderbird_2_notification_5_min_postponed",
            -1,
            2,
            "Thunderbird (2.3): 1 alarm active and one postponed by 5 minutes",
        ),
        (
            "alarm_thunderbird_2_notification_5_min_postponed_and_popped_up",
            -1,
            2,
            "Thunderbird (2.4): 1 alarm active and one postponed by 5 minutes and now popped up",
        ),
        (
            "alarm_thunderbird_2_notification_5_min_postponed_and_closed",
            -1,
            1,
            "Thunderbird (2.5): 1 alarm active and one postponed by 5 minutes and is now acknowledged",
        ),
    ],
)
def test_number_of_active_alarms_from_calendar_software(
    calendars, calendar, index, count, message
):
    """Check that we extract calculate the correct amount of active alarms."""
    event = calendars[calendar].subcomponents[index]
    a = Alarms(event)
    active_alarms = (
        a.active
    )  # We do not need to pass a timezone because the events have a timezone
    assert len(active_alarms) == count, (
        f"{message} - I expect {count} alarms active but got {len(active_alarms)}."
    )


three_alarms = Alarm()
three_alarms.REPEAT = 2
three_alarms.add("DURATION", timedelta(hours=1))  # 2 hours & 1 hour before
three_alarms.add("TRIGGER", -timedelta(hours=3))  # 3 hours before


@pytest.mark.parametrize(
    ("start", "acknowledged", "timezone", "count"),
    [
        (datetime(2024, 10, 10), datetime(2024, 10, 9), "UTC", 3),
        (datetime(2024, 10, 10, 12), datetime(2024, 10, 10, 9, 1), "UTC", 2),
        (datetime(2024, 10, 10, 12), datetime(2024, 10, 10, 10, 1), "UTC", 1),
        (datetime(2024, 10, 10, 12), datetime(2024, 10, 10, 11, 1), "UTC", 0),
        (
            datetime(2024, 10, 10, 12, tzinfo=timezone.utc),
            datetime(2024, 10, 10, 11, 1),
            None,
            0,
        ),
    ],
)
def test_number_of_active_alarms_with_moving_time(
    start, acknowledged, count, tzp, timezone
):
    """Check how many alarms are active after a time they are acknowledged."""
    a = Alarms()
    a.add_alarm(three_alarms)
    a.set_start(start)
    a.set_local_timezone(timezone)
    a.acknowledge_until(tzp.localize_utc(acknowledged))
    active = a.active
    assert len(active) == count


def test_incomplete_alarm_information_for_active_state(tzp):
    """Make sure we throw the right error."""
    a = Alarms()
    a.add_alarm(three_alarms)
    a.set_start(date(2017, 12, 1))
    a.acknowledge_until(tzp.localize_utc(datetime(2012, 10, 10, 12)))
    with pytest.raises(IncompleteAlarmInformation) as e:
        a.active  # noqa: B018, RUF100
    assert (
        e.value.args[0]
        == f"A local timezone is required to check if the alarm is still active. Use Alarms.{Alarms.set_local_timezone.__name__}()."
    )


@pytest.mark.parametrize(
    "calendar_name",
    [
        "alarm_etar_future",
        "alarm_google_acknowledged",
        "alarm_thunderbird_closed",
        "alarm_thunderbird_future",
        "alarm_thunderbird_snoozed_until_1457",
    ],
)
def test_thunderbird_recognition(calendars, calendar_name):
    """Check if we correctly discover Thunderbird's alarm algorithm."""
    calendar = calendars[calendar_name]
    event = calendar.subcomponents[-1]
    assert isinstance(event, Event)
    assert event.is_thunderbird() == ("thunderbird" in calendar_name)


@pytest.mark.parametrize(
    "snooze",
    [
        datetime(2012, 10, 10, 11, 1),  # before everything
        datetime(2017, 12, 1, 10, 1),
        datetime(2017, 12, 1, 11, 1),
        datetime(2017, 12, 1, 12, 1),
        datetime(2017, 12, 1, 13, 1),  # snooze until after the start of the event
    ],
)
def test_snoozed_alarm_has_trigger_at_snooze_time(tzp, snooze):
    """When an alarm is snoozed, it pops up after the snooze time."""
    a = Alarms()
    a.add_alarm(three_alarms)
    a.set_start(datetime(2017, 12, 1, 13))
    a.set_local_timezone("UTC")
    snooze_utc = tzp.localize_utc(snooze)
    a.snooze_until(snooze_utc)
    active = a.active
    assert len(active) == 3
    for alarm in active:
        assert alarm.trigger >= snooze_utc


@pytest.mark.parametrize(
    ("event_index", "alarm_times"),
    [
        # Assume that we have the following event with an alarm set to trigger 15 minutes before the meeting:
        (1, ("20210302T101500",)),
        # When the alarm is triggered, the user decides to "snooze" it for 5 minutes.
        # The client acknowledges the original alarm and creates a new "snooze"
        # alarm as a sibling of, and relates it to, the original alarm (note that
        # both occurrences of "VALARM" reside within the same "parent" VEVENT):
        (2, ("20210302T102000",)),
        # When the "snooze" alarm is triggered, the user decides to "snooze" it
        # again for an additional 5 minutes. The client once again acknowledges
        # the original alarm, removes the triggered "snooze" alarm, and creates another
        # new "snooze" alarm as a sibling of, and relates it to, the original alarm
        # (note the different UID for the new "snooze" alarm):
        (3, ("20210302T102500",)),
        # When the second "snooze" alarm is triggered, the user decides to dismiss it.
        # The client acknowledges both the original alarm and the second "snooze" alarm:
        (4, ()),
    ],
)
def test_rfc_9074_alarm_times(events, event_index, alarm_times):
    """Test the examples from the RFC and their timing.

    Add times use America/New_York as timezone.
    """
    a = events[f"rfc_9074_example_{event_index}"].alarms
    assert len(a.active) == len(alarm_times)
    expected_alarm_times = {
        vDatetime.from_ical(t, "America/New_York") for t in alarm_times
    }
    computed_alarm_times = {alarm.trigger for alarm in a.active}
    assert expected_alarm_times == computed_alarm_times


def test_set_to_None():
    """acknowledge_until, snooze_until, set_local_timezone."""
    a = Alarms()
    a.set_start(None)
    a.set_end(None)
    a.set_local_timezone(None)
    a.acknowledge_until(None)
    a.snooze_until(None)
    assert vars(a) == vars(Alarms())


def test_delete_TRIGGER():
    """Delete the TRIGGER property."""
    a = Alarm()
    a.TRIGGER = datetime(2017, 12, 1, 10, 1)
    del a.TRIGGER
    assert a.TRIGGER is None

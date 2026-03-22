"""This tests the properties of components and their types.

See https://github.com/collective/icalendar/issues/662
"""

from __future__ import annotations

import itertools
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from icalendar import (
    Alarm,
    Event,
    IncompleteComponent,
    InvalidCalendar,
    Journal,
    Todo,
    vDatetime,
    vDDDTypes,
    vDuration,
)


def prop(component: Event | Todo, prop: str) -> str:
    """Translate the end property.

    This allows us to run the same tests on Event and Todo.
    """
    if isinstance(component, Todo) and prop.upper() == "DTEND":
        return "DUE"
    return prop


@pytest.fixture(params=[Event, Todo])
def start_end_component(request):
    """The event to test."""
    return request.param()


@pytest.fixture(
    params=[
        datetime(2022, 7, 22, 12, 7),
        date(2022, 7, 22),
        datetime(2022, 7, 22, 13, 7, tzinfo=ZoneInfo("Europe/Paris")),
    ]
)
def dtstart(request, set_component_start, start_end_component):
    """Start of the event."""
    set_component_start(start_end_component, request.param)
    return request.param


def _set_component_start_init(component, start):
    """Create the event with the __init__ method."""
    d = dict(component)
    d["dtstart"] = vDDDTypes(start)
    component.clear()
    component.update(type(component)(d))


def _set_component_dtstart(component, start):
    """Create the event with the dtstart property."""
    component.DTSTART = start


def _set_component_start_attr(component, start):
    """Create the event with the dtstart property."""
    component.start = start


def _set_component_start_ics(component, start):
    """Create the event with the start property."""
    component.add("dtstart", start)
    ics = component.to_ical().decode()
    print(ics)
    component.clear()
    component.update(type(component).from_ical(ics))


@pytest.fixture(
    params=[
        _set_component_start_init,
        _set_component_start_ics,
        _set_component_dtstart,
        _set_component_start_attr,
    ]
)
def set_component_start(request):
    """Create a new event."""
    return request.param


def test_component_dtstart(dtstart, start_end_component):
    """Test the start of events."""
    assert dtstart == start_end_component.DTSTART


def test_event_start(dtstart, start_end_component):
    """Test the start of events."""
    assert start_end_component.start == dtstart


invalid_start_event_1 = Event()
invalid_start_event_1.add("dtstart", datetime(2022, 7, 22, 12, 7))
invalid_start_event_1.add("dtstart", datetime(2022, 7, 22, 12, 8))
invalid_start_event_2 = Event.from_ical(invalid_start_event_1.to_ical())
invalid_start_event_3 = Event()
invalid_start_event_3.add("DTSTART", (date(2018, 1, 1), date(2018, 2, 1)))
invalid_start_todo_1 = Todo(invalid_start_event_1)
invalid_start_todo_2 = Todo(invalid_start_event_2)
invalid_start_todo_3 = Todo(invalid_start_event_3)


@pytest.mark.parametrize(
    "invalid_event",
    [
        invalid_start_event_1,
        invalid_start_event_2,
        invalid_start_event_3,
        invalid_start_todo_1,
        invalid_start_todo_2,
        invalid_start_todo_3,
    ],
)
def test_multiple_dtstart(invalid_event):
    """Check that we get the right error."""
    with pytest.raises(InvalidCalendar):
        invalid_event.start  # noqa: B018, RUF100
    with pytest.raises(InvalidCalendar):
        invalid_event.DTSTART  # noqa: B018, RUF100


def test_no_dtstart(start_end_component):
    """DTSTART is optional.

    The following is REQUIRED if the component
    appears in an iCalendar object that doesn't
    specify the "METHOD" property; otherwise, it
    is OPTIONAL; in any case, it MUST NOT occur
    more than once.
    """
    assert start_end_component.DTSTART is None
    with pytest.raises(IncompleteComponent):
        start_end_component.start  # noqa: B018, RUF100


@pytest.fixture(
    params=[
        datetime(2022, 7, 22, 12, 8),
        date(2022, 7, 23),
        datetime(2022, 7, 22, 14, 7, tzinfo=ZoneInfo("Europe/Paris")),
    ]
)
def dtend(request, set_component_end, start_end_component):
    """end of the event."""
    set_component_end(start_end_component, request.param)
    return request.param


def _set_component_end_init(component, end):
    """Create the event with the __init__ method."""
    d = dict(component)
    d[prop(component, "dtend")] = vDDDTypes(end)
    component.clear()
    component.update(type(component)(d))


def _set_component_end_property(component, end):
    """Create the event with the dtend property."""
    setattr(component, prop(component, "DTEND"), end)


def _set_component_end_attr(component, end):
    """Create the event with the dtend property."""
    component.end = end


def _set_component_end_ics(component, end):
    """Create the event with the end property."""
    component.add(prop(component, "DTEND"), end)
    ics = component.to_ical().decode()
    print(ics)
    component.clear()
    component.update(type(component).from_ical(ics))


@pytest.fixture(
    params=[
        _set_component_end_init,
        _set_component_end_ics,
        _set_component_end_property,
        _set_component_end_attr,
    ]
)
def set_component_end(request):
    """Create a new event."""
    return request.param


def test_component_end_property(dtend, start_end_component):
    """Test the end of events."""
    attr = prop(start_end_component, "DTEND")
    assert getattr(start_end_component, attr) == dtend


def test_component_end(dtend, start_end_component):
    """Test the end of events."""
    assert start_end_component.end == dtend


@pytest.mark.parametrize("attr", ["DTSTART", "DTEND"])
def test_delete_attr(start_end_component, dtstart, dtend, attr):
    attr = prop(start_end_component, attr)
    delattr(start_end_component, attr)
    assert getattr(start_end_component, attr) is None
    delattr(start_end_component, attr)


def _set_duration_vdddtypes(event: Event, duration: timedelta):
    """Set the vDDDTypes value"""
    event["DURATION"] = vDDDTypes(duration)


def _set_duration_add(event: Event, duration: timedelta):
    """Set the vDDDTypes value"""
    event.add("DURATION", duration)


def _set_duration_vduration(event: Event, duration: timedelta):
    """Set the vDDDTypes value"""
    event["DURATION"] = vDuration(duration)


@pytest.fixture(
    params=[_set_duration_vdddtypes, _set_duration_add, _set_duration_vduration]
)
def duration(start_end_component, dtstart, request):
    """... events have a DATE value type for the "DTSTART" property ...
    If such a "VEVENT" has a "DURATION"
    property, it MUST be specified as a "dur-day" or "dur-week" value.
    """
    duration = (
        timedelta(hours=1) if isinstance(dtstart, datetime) else timedelta(days=2)
    )
    request.param(start_end_component, duration)
    return duration


def test_start_and_duration(start_end_component, dtstart, duration):
    """Check calculation of end with duration."""
    dur = start_end_component.end - start_end_component.start
    assert dur == duration
    assert start_end_component.duration == duration


# The "VEVENT" is also the calendar component used to specify an
# anniversary or daily reminder within a calendar.  These events
# have a DATE value type for the "DTSTART" property instead of the
# default value type of DATE-TIME.  If such a "VEVENT" has a "DTEND"
# property, it MUST be specified as a DATE value also.
invalid_event_end_1 = Event()
invalid_event_end_1.add("DTSTART", datetime(2024, 1, 1, 10, 20))
invalid_event_end_1.add("DTEND", date(2024, 1, 1))
invalid_event_end_2 = Event()
invalid_event_end_2.add("DTEND", datetime(2024, 1, 1, 10, 20))
invalid_event_end_2.add("DTSTART", date(2024, 1, 1))
invalid_event_end_3 = Event()
invalid_event_end_3.add("DTEND", datetime(2024, 1, 1, 10, 20))
invalid_event_end_3.add("DTSTART", datetime(2024, 1, 1, 10, 20))
invalid_event_end_3.add("DURATION", timedelta(days=1))
invalid_event_end_4 = Event()
invalid_event_end_4.add("DTSTART", date(2024, 1, 1))
invalid_event_end_4.add("DURATION", timedelta(hours=1))

invalid_todo_end_1 = Todo()
invalid_todo_end_1.add("DTSTART", datetime(2024, 1, 1, 10, 20))
invalid_todo_end_1.add("DUE", date(2024, 1, 1))
invalid_todo_end_2 = Todo()
invalid_todo_end_2.add("DUE", datetime(2024, 1, 1, 10, 20))
invalid_todo_end_2.add("DTSTART", date(2024, 1, 1))
invalid_todo_end_3 = Todo()
invalid_todo_end_3.add("DUE", datetime(2024, 1, 1, 10, 20))
invalid_todo_end_3.add("DTSTART", datetime(2024, 1, 1, 10, 20))
invalid_todo_end_3.add("DURATION", timedelta(days=1))
invalid_todo_end_4 = Todo()
invalid_todo_end_4.add("DTSTART", date(2024, 1, 1))
invalid_todo_end_4.add("DURATION", timedelta(hours=1))


@pytest.mark.parametrize(
    ("invalid_component", "message"),
    [
        (
            invalid_event_end_1,
            "DTSTART and DTEND must be of the same type, either date or datetime.",
        ),
        (
            invalid_event_end_2,
            "DTSTART and DTEND must be of the same type, either date or datetime.",
        ),
        (
            invalid_event_end_3,
            "Only one of DTEND and DURATION may be in a VEVENT, not both.",
        ),
        (
            invalid_event_end_4,
            "When DTSTART is a date, DURATION must be of days or weeks.",
        ),
        (
            invalid_todo_end_1,
            "DTSTART and DUE must be of the same type, either date or datetime.",
        ),
        (
            invalid_todo_end_2,
            "DTSTART and DUE must be of the same type, either date or datetime.",
        ),
        (
            invalid_todo_end_3,
            "Only one of DUE and DURATION may be in a VTODO, not both.",
        ),
        (
            invalid_todo_end_4,
            "When DTSTART is a date, DURATION must be of days or weeks.",
        ),
    ],
)
@pytest.mark.parametrize("attr", ["start", "end"])
def test_invalid_event(invalid_component, message, attr):
    """Test that the end and start throuw the right error."""
    with pytest.raises(InvalidCalendar) as e:
        getattr(invalid_component, attr)
    assert e.value.args[0] == message


def test_event_duration_zero():
    """
    For cases where a "VEVENT" calendar component
    specifies a "DTSTART" property with a DATE-TIME value type but no
    "DTEND" property, the event ends on the same calendar date and
    time of day specified by the "DTSTART" property.
    """
    event = Event()
    event.start = datetime(2024, 10, 11, 10, 20)
    assert event.end == event.start
    assert event.duration == timedelta(days=0)


def test_event_duration_one_day():
    """
    For cases where a "VEVENT" calendar component
    specifies a "DTSTART" property with a DATE value type but no
    "DTEND" nor "DURATION" property, the event's duration is taken to
    be one day
    """
    event = Event()
    event.start = date(2024, 10, 11)
    assert event.end == event.start + timedelta(days=1)
    assert event.duration == timedelta(days=1)


def test_todo_duration_zero():
    """We do not know about the duration of a todo really."""
    todo = Todo()
    todo.start = datetime(2024, 10, 11, 10, 20)
    assert todo.end == todo.start
    assert todo.duration == timedelta(days=0)


def test_todo_duration_one_day():
    """The end is at the end of the day, excluding midnight.

    RFC 5545:
    The following is an example of a "VTODO" calendar
    component that needs to be completed before May 1st, 2007.  On
    midnight May 1st, 2007 this to-do would be considered overdue.
    """
    event = Event()
    event.start = date(2024, 10, 11)
    assert event.end == event.start + timedelta(days=1)
    assert event.duration == timedelta(days=1)


incomplete_event_1 = Event()
incomplete_event_2 = Event()
incomplete_event_2.add("DURATION", timedelta(hours=1))
incomplete_todo_1 = Todo()
incomplete_todo_2 = Todo()
incomplete_todo_2.add("DURATION", timedelta(hours=1))


@pytest.mark.parametrize(
    "incomplete_event_end",
    [
        incomplete_event_1,
        incomplete_todo_1,
    ],
)
@pytest.mark.parametrize("attr", ["start", "end", "duration"])
def test_incomplete_event(incomplete_event_end, attr):
    """Test that components without required properties throw the right error."""
    with pytest.raises(IncompleteComponent):
        getattr(incomplete_event_end, attr)


@pytest.mark.parametrize(
    "component_with_duration",
    [
        incomplete_event_2,  # Event with DURATION property
        incomplete_todo_2,  # Todo with DURATION property
    ],
)
def test_duration_property_accessible_without_dtstart(component_with_duration):
    """Test that DURATION property is accessible even without DTSTART (fixes issue #867)."""
    # DURATION property should be accessible directly
    assert component_with_duration.duration == timedelta(hours=1)

    # But start and end should still raise errors for incomplete components
    with pytest.raises(IncompleteComponent):
        _ = component_with_duration.start
    with pytest.raises(IncompleteComponent):
        _ = component_with_duration.end


@pytest.mark.parametrize(
    "invalid_value",
    [
        object(),
        timedelta(days=1),
        (datetime(2024, 10, 11, 10, 20), timedelta(days=1)),
    ],
)
@pytest.mark.parametrize(
    ("Component", "attr"),
    [
        (Event, "start"),
        (Event, "end"),
        (Event, "DTSTART"),
        (Event, "DTEND"),
        (Journal, "start"),
        (Journal, "end"),
        (Journal, "DTSTART"),
        (Todo, "start"),
        (Todo, "end"),
        (Todo, "DTSTART"),
        (Todo, "DUE"),
    ],
)
def test_set_invalid_start(invalid_value, attr, Component):
    """Check that we get the right error.

    - other types that vDDDTypes accepts
    - object
    """
    component = Component()
    with pytest.raises(TypeError) as e:
        setattr(component, attr, invalid_value)
    assert (
        e.value.args[0] == f"Use datetime or date, not {type(invalid_value).__name__}."
    )


def setitem(d: dict, key, value):
    d[key] = value


@pytest.mark.parametrize(
    "invalid_value",
    [
        object(),
        None,
        (datetime(2024, 10, 11, 10, 20), timedelta(days=1)),
        date(2012, 2, 2),
        datetime(2022, 2, 2),
    ],
)
def test_check_invalid_duration(start_end_component, invalid_value):
    """Check that we get the right error."""
    start_end_component["DURATION"] = invalid_value
    with pytest.raises(InvalidCalendar) as e:
        start_end_component.DURATION  # noqa: B018, RUF100
    assert (
        e.value.args[0]
        == f"DURATION must be a timedelta, not {type(invalid_value).__name__}."
    )


def test_setting_the_end_deletes_the_duration(start_end_component):
    """Setting the end should not break the event."""
    DTEND = prop(start_end_component, "DTEND")
    start_end_component.DTSTART = datetime(2024, 10, 11, 10, 20)
    start_end_component.DURATION = timedelta(days=1)
    setattr(start_end_component, DTEND, datetime(2024, 10, 11, 10, 21))
    assert "DURATION" not in start_end_component
    assert start_end_component.DURATION is None
    end = getattr(start_end_component, DTEND)
    assert end == datetime(2024, 10, 11, 10, 21)


def test_setting_duration_deletes_the_end(start_end_component):
    """Setting the duration should not break the event."""
    DTEND = prop(start_end_component, "DTEND")
    start_end_component.DTSTART = datetime(2024, 10, 11, 10, 20)
    setattr(start_end_component, DTEND, datetime(2024, 10, 11, 10, 21))
    start_end_component.DURATION = timedelta(days=1)
    assert DTEND not in start_end_component
    assert getattr(start_end_component, DTEND) is None
    assert timedelta(days=1) == start_end_component.DURATION


valid_values = pytest.mark.parametrize(
    ("attr", "value"),
    [
        ("DTSTART", datetime(2024, 10, 11, 10, 20)),
        ("DTEND", datetime(2024, 10, 11, 10, 20)),
        ("DURATION", timedelta(days=1)),
    ],
)


@valid_values
def test_setting_to_none_deletes_value(start_end_component, attr, value):
    """Setting attributes to None deletes them."""
    attr = prop(start_end_component, attr)
    setattr(start_end_component, attr, value)
    assert attr in start_end_component
    assert getattr(start_end_component, attr) == value
    setattr(start_end_component, attr, None)
    assert attr not in start_end_component


@valid_values
def test_setting_a_value_twice(start_end_component, attr, value):
    """Setting attributes twice replaces them."""
    attr = prop(start_end_component, attr)
    setattr(start_end_component, attr, value + timedelta(days=1))
    setattr(start_end_component, attr, value)
    assert getattr(start_end_component, attr) == value


@pytest.mark.parametrize("attr", ["DTSTART", "DTEND", "DURATION"])
def test_invalid_none(start_end_component, attr):
    """Special case for None."""
    attr = prop(start_end_component, attr)
    start_end_component[attr] = None
    with pytest.raises(InvalidCalendar):
        getattr(start_end_component, attr)


def test_delete_duration(start_end_component):
    """Test the del command."""
    start_end_component.DURATION = timedelta(days=1)
    del start_end_component.DURATION
    assert start_end_component.DURATION is None


@pytest.mark.parametrize("attr", ["DTSTART", "end", "start"])
@pytest.mark.parametrize(
    "start",
    [
        datetime(2024, 10, 11, 10, 20),
        date(2024, 10, 11),
        datetime(2024, 10, 11, 10, 20, tzinfo=ZoneInfo("Europe/Paris")),
    ],
)
def test_journal_start(start, attr):
    """Test that we can set the start of a journal."""
    j = Journal()
    setattr(j, attr, start)
    assert start == j.DTSTART
    assert j.start == start
    assert j.end == start
    assert j.duration == timedelta(0)


@pytest.mark.parametrize("attr", ["start", "end"])
def test_delete_journal_start(attr):
    """Delete the start of the journal."""
    j = Journal()
    j.start = datetime(2010, 11, 12, 13, 14)
    j.DTSTART = None
    assert j.DTSTART is None
    assert "DTSTART" not in j
    with pytest.raises(IncompleteComponent):
        getattr(j, attr)


def setting_twice_does_not_duplicate_the_entry():
    j = Journal()
    j.DTSTART = date(2024, 1, 1)
    j.DTSTART = date(2024, 1, 3)
    assert date(2024, 1, 3) == j.DTSTART
    assert j.start == date(2024, 1, 3)
    assert j.end == date(2024, 1, 3)


@pytest.mark.parametrize(
    ("file", "trigger", "related"),
    [
        (
            "rfc_5545_absolute_alarm_example",
            vDatetime.from_ical("19970317T133000Z"),
            "START",
        ),
        ("rfc_5545_end", timedelta(days=-2), "END"),
        ("start_date", timedelta(days=-2), "START"),
    ],
)
def test_get_alarm_trigger_property(alarms, file, trigger, related):
    """Get the trigger property."""
    alarm = alarms[file]
    assert trigger == alarm.TRIGGER
    assert related == alarm.TRIGGER_RELATED


def test_set_alarm_trigger():
    """Set the alarm trigger."""
    a = Alarm()
    a.TRIGGER = timedelta(hours=1)
    assert timedelta(hours=1) == a.TRIGGER
    assert a.TRIGGER_RELATED == "START"


def test_set_alarm_trigger_related():
    """Set the alarm trigger."""
    a = Alarm()
    a.TRIGGER = timedelta(hours=1)
    a.TRIGGER_RELATED = "END"
    assert timedelta(hours=1) == a.TRIGGER
    assert a.TRIGGER_RELATED == "END"


def test_get_related_without_trigger():
    """The default is start"""
    assert Alarm().TRIGGER_RELATED == "START"


def test_cannot_set_related_without_trigger():
    """TRIGGER must be set to set the parameter."""
    with pytest.raises(ValueError) as e:
        a = Alarm()
        a.TRIGGER_RELATED = "END"
    assert (
        e.value.args[0]
        == "You must set a TRIGGER before setting the RELATED parameter."
    )


@pytest.mark.parametrize(
    ("file", "triggers"),
    [
        (
            "rfc_5545_absolute_alarm_example",
            (
                (),
                (),
                (
                    vDatetime.from_ical("19970317T133000Z"),
                    vDatetime.from_ical("19970317T134500Z"),
                    vDatetime.from_ical("19970317T140000Z"),
                    vDatetime.from_ical("19970317T141500Z"),
                    vDatetime.from_ical("19970317T143000Z"),
                ),
            ),
        ),
        ("rfc_5545_end", ((), (timedelta(days=-2),), ())),
        ("start_date", ((timedelta(days=-2),), (), ())),
    ],
)
def test_get_alarm_triggers(alarms, file, triggers):
    """Get the trigger property."""
    alarm = alarms[file]
    print(tuple(alarm.triggers))
    print(triggers)
    assert alarm.triggers == triggers


def test_triggers_emtpy_alarm():
    """An alarm with no trigger has no triggers."""
    assert Alarm().triggers == ((), (), ())


h1 = timedelta(hours=1)


def test_triggers_emtpy_with_no_repeat():
    """Check incomplete values."""
    a = Alarm()
    a.TRIGGER = h1
    a.DURATION = h1
    assert a.triggers == ((h1,), (), ())


def test_triggers_emtpy_with_no_duration():
    """Check incomplete values."""
    a = Alarm()
    a.TRIGGER = h1
    a.REPEAT = 10
    assert a.triggers == ((h1,), (), ())


@pytest.mark.parametrize(
    ("file", "triggers"),
    [
        (
            "rfc_5545_absolute_alarm_example",
            ((), (), (vDatetime.from_ical("19970317T133000Z"),)),
        ),
        ("rfc_5545_end", ((), (timedelta(days=-2),), ())),
        ("start_date", ((timedelta(days=-2),), (), ())),
    ],
)
@pytest.mark.parametrize("duration", [timedelta(days=-1), h1])
@pytest.mark.parametrize("repeat", [1, 3])
def test_get_alarm_triggers_repeated(alarms, file, triggers, duration, repeat):
    """Get the trigger property."""
    alarm = alarms[file].copy()
    alarm.REPEAT = repeat
    alarm.DURATION = duration
    for expected, triggers in zip(triggers, alarm.triggers, strict=False):  # noqa: PLR1704
        if not expected:
            assert triggers == ()
            continue
        assert len(triggers) == 1 + repeat
        assert triggers[0] == expected[0]
        for x, y in itertools.pairwise(triggers):
            assert y - x == duration

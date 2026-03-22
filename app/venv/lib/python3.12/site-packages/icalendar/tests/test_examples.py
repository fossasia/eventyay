"""tests ensuring that *the* way of doing things works"""

import datetime

import pytest

from icalendar import Alarm, Availability, Available, Calendar, Event, Timezone, Todo


def test_creating_calendar_with_unicode_fields(calendars, utc):
    """create a calendar with events that contain unicode characters in their fields"""
    cal = Calendar()
    cal.add("PRODID", "-//Plönë.org//NONSGML plone.app.event//EN")
    cal.add("VERSION", "2.0")
    cal.add("X-WR-CALNAME", "äöü ÄÖÜ €")
    cal.add("X-WR-CALDESC", "test non ascii: äöü ÄÖÜ €")
    cal.add("X-WR-RELCALID", "12345")

    event = Event()
    event.add("DTSTART", datetime.datetime(2010, 10, 10, 10, 0, 0, tzinfo=utc))
    event.add("DTEND", datetime.datetime(2010, 10, 10, 12, 0, 0, tzinfo=utc))
    event.add("CREATED", datetime.datetime(2010, 10, 10, 0, 0, 0, tzinfo=utc))
    event.add("UID", "123456")
    event.add("SUMMARY", "Non-ASCII Test: ÄÖÜ äöü €")
    event.add("DESCRIPTION", "icalendar should be able to de/serialize non-ascii.")
    event.add("LOCATION", "Tribstrül")
    cal.add_component(event)

    # test_create_event_simple
    event1 = Event()
    event1.add("DTSTART", datetime.datetime(2010, 10, 10, 0, 0, 0, tzinfo=utc))
    event1.add("SUMMARY", "åäö")
    cal.add_component(event1)

    # test_unicode_parameter_name
    # test for issue #80 https://github.com/collective/icalendar/issues/80
    event2 = Event()
    event2.add("DESCRIPTION", "äöüßÄÖÜ")
    cal.add_component(event2)

    assert cal.to_ical() == calendars.created_calendar_with_unicode_fields.raw_ics


@pytest.mark.parametrize(
    ("component", "example"),
    [
        (Calendar, "example"),
        (Calendar, "example.ics"),
        (Event, "event_with_rsvp"),
        (Timezone, "pacific_fiji"),
        (Todo, "example"),
    ],
)
def test_component_has_examples(
    tzp, calendars, timezones, events, todos, component, example, alarms
):
    """Check that the examples function works."""
    mapping = {
        Calendar: calendars,
        Event: events,
        Timezone: timezones,
        Todo: todos,
        Alarm: alarms,
    }
    example_component = component.example(example)
    expected_component = mapping[component][example]
    assert example_component == expected_component


def test_invalid_examples_lists_the_others():
    """We need a bit of guidance here."""
    with pytest.raises(ValueError) as e:
        Calendar.example("does not exist")
    assert "example.ics" in str(e.value)


@pytest.mark.parametrize(
    "component", [Calendar, Event, Timezone, Available, Availability, Todo, Alarm]
)
def test_default_example(component):
    """Check that we have a default example."""
    example = component.example()
    assert isinstance(example, component)

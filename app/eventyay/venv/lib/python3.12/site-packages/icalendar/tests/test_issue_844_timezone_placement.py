"""Tests for issue #844: timezone placement in calendar components."""

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event
from icalendar.cal.timezone import Timezone


def test_single_timezone_placed_before_event():
    """Test that single timezone is placed before event when using `add_missing_timezones()`."""
    calendar = Calendar()
    calendar.add("VERSION", "2.0")
    calendar.add("PRODID", "test calendar")

    event = Event()
    event.add("UID", str(uuid.uuid4()))
    event.start = datetime(2026, 3, 19, 12, 30, tzinfo=ZoneInfo("Europe/London"))
    event.add("SUMMARY", "Test Event")
    calendar.add_component(event)

    calendar.add_missing_timezones()

    components = [comp.name for comp in calendar.subcomponents]
    assert components == ["VTIMEZONE", "VEVENT"]

    # Verify the timezone is correct
    assert calendar.timezones[0].tz_name == "Europe/London"


def test_multiple_timezones_placed_before_events():
    """Test that multiple timezones are placed before events."""
    calendar = Calendar()
    calendar.add("VERSION", "2.0")
    calendar.add("PRODID", "test calendar")

    event1 = Event()
    event1.add("UID", str(uuid.uuid4()))
    event1.start = datetime(2026, 3, 19, 12, 30, tzinfo=ZoneInfo("Europe/London"))
    event1.add("SUMMARY", "London Event")
    calendar.add_component(event1)

    event2 = Event()
    event2.add("UID", str(uuid.uuid4()))
    event2.start = datetime(2026, 3, 19, 15, 30, tzinfo=ZoneInfo("America/New_York"))
    event2.add("SUMMARY", "New York Event")
    calendar.add_component(event2)

    calendar.add_missing_timezones()

    components = [comp.name for comp in calendar.subcomponents]
    assert components[:2] == ["VTIMEZONE", "VTIMEZONE"]
    assert components[2:] == ["VEVENT", "VEVENT"]

    # Verify both timezones are present
    timezone_names = {tz.tz_name for tz in calendar.timezones}
    assert timezone_names == {"Europe/London", "America/New_York"}


def test_existing_timezone_preserved_new_ones_added_correctly():
    """Test that existing timezones are preserved and new ones added in correct position."""
    calendar = Calendar()
    calendar.add("VERSION", "2.0")
    calendar.add("PRODID", "test calendar")

    # Add existing timezone manually
    existing_tz = Timezone.from_tzid("Europe/Berlin")
    calendar.add_component(existing_tz)

    event1 = Event()
    event1.add("UID", str(uuid.uuid4()))
    event1.start = datetime(2026, 3, 19, 12, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    event1.add("SUMMARY", "Berlin Event")
    calendar.add_component(event1)

    event2 = Event()
    event2.add("UID", str(uuid.uuid4()))
    event2.start = datetime(2026, 3, 19, 15, 30, tzinfo=ZoneInfo("America/New_York"))
    event2.add("SUMMARY", "New York Event")
    calendar.add_component(event2)

    calendar.add_missing_timezones()

    components = [comp.name for comp in calendar.subcomponents]
    assert components[:2] == ["VTIMEZONE", "VTIMEZONE"]
    assert components[2:] == ["VEVENT", "VEVENT"]

    # Verify both timezones are present (existing + new)
    timezone_names = {tz.tz_name for tz in calendar.timezones}
    assert timezone_names == {"Europe/Berlin", "America/New_York"}


def test_no_missing_timezones_no_changes():
    """Test that method handles case with no missing timezones. Gracefully."""
    calendar = Calendar()
    calendar.add("VERSION", "2.0")
    calendar.add("PRODID", "test calendar")

    event = Event()
    event.add("UID", str(uuid.uuid4()))
    event.start = datetime(2026, 3, 19, 12, 30)  # No timezone
    event.add("SUMMARY", "No Timezone Event")
    calendar.add_component(event)

    original_components = [comp.name for comp in calendar.subcomponents]
    calendar.add_missing_timezones()
    new_components = [comp.name for comp in calendar.subcomponents]

    assert original_components == new_components == ["VEVENT"]


def test_empty_calendar_add_missing_timezones():
    """Test that `add_missing_timezones()` handles empty calendar correctly."""
    calendar = Calendar()
    calendar.add("VERSION", "2.0")
    calendar.add("PRODID", "test calendar")

    calendar.add_missing_timezones()

    components = [comp.name for comp in calendar.subcomponents]
    assert components == []


def test_timezone_placement_in_serialized_output():
    """Test that timezones appear before events in serialized iCalendar output."""
    calendar = Calendar()
    calendar.add("VERSION", "2.0")
    calendar.add("PRODID", "test calendar")

    event = Event()
    event.add("UID", str(uuid.uuid4()))
    event.start = datetime(2026, 3, 19, 12, 30, tzinfo=ZoneInfo("Europe/London"))
    event.add("SUMMARY", "Test Event")
    calendar.add_component(event)

    calendar.add_missing_timezones()

    # Check serialized output
    ical_content = calendar.to_ical().decode()
    lines = ical_content.split("\n")

    vtimezone_line = None
    vevent_line = None

    for i, line in enumerate(lines):
        if line.strip() == "BEGIN:VTIMEZONE":
            vtimezone_line = i
        elif line.strip() == "BEGIN:VEVENT":
            vevent_line = i

    assert vtimezone_line is not None
    assert vevent_line is not None
    assert vtimezone_line < vevent_line


def test_forward_reference_compatibility():
    """Test that our fix doesn't break forward reference parsing."""
    # Create a calendar with forward reference (VEVENT before VTIMEZONE)
    ical_content = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VEVENT
UID:test-event
DTSTART;TZID=Europe/London:20260319T123000
SUMMARY:Test Event
END:VEVENT
BEGIN:VTIMEZONE
TZID:Europe/London
BEGIN:STANDARD
DTSTART:20001029T020000
TZOFFSETFROM:+0100
TZOFFSETTO:+0000
TZNAME:GMT
END:STANDARD
END:VTIMEZONE
END:VCALENDAR"""

    # This should still parse correctly due to existing forward reference handling
    calendar = Calendar.from_ical(ical_content)
    assert len(calendar.events) == 1
    assert len(calendar.timezones) == 1
    assert calendar.timezones[0].tz_name == "Europe/London"


def test_timezone_placement_without_pytz():
    """Test timezone placement. Works even if pytz is not available."""
    import sys

    # Temporarily mock pytz to simulate nopytz environment
    original_pytz = sys.modules.get("pytz")

    class MockPytz:
        def __getattr__(self, name):
            raise ImportError("No module named 'pytz'")

    sys.modules["pytz"] = MockPytz()

    try:
        calendar = Calendar()
        calendar.add("VERSION", "2.0")
        calendar.add("PRODID", "test calendar")

        event = Event()
        event.add("UID", str(uuid.uuid4()))
        event.start = datetime(2026, 3, 19, 12, 30, tzinfo=ZoneInfo("Europe/London"))
        event.add("SUMMARY", "Test Event")
        calendar.add_component(event)

        calendar.add_missing_timezones()

        components = [comp.name for comp in calendar.subcomponents]
        assert components == ["VTIMEZONE", "VEVENT"]
        assert len(calendar.timezones) == 1
        assert calendar.timezones[0].tz_name == "Europe/London"

    finally:
        # Restore original pytz state
        if original_pytz:
            sys.modules["pytz"] = original_pytz
        else:
            sys.modules.pop("pytz", None)

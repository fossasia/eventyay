"""Tests for error-tolerant parsing of property values."""

import pytest

from icalendar import Calendar
from icalendar.error import BrokenCalendarProperty
from icalendar.prop import vBroken, vDDDLists, vDDDTypes, vRecur, vText


def test_properties_parsed_immediately():
    """Verify properties are parsed immediately during from_ical()."""
    ical_str = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VEVENT
UID:test-123
DTSTART:20250101T100000Z
RRULE:FREQ=DAILY;COUNT=10
SUMMARY:Test Event
END:VEVENT
END:VCALENDAR"""

    cal = Calendar.from_ical(ical_str)
    event = cal.walk("VEVENT")[0]

    # Properties should already be parsed
    rrule = event["RRULE"]
    assert isinstance(rrule, vRecur)
    assert rrule["FREQ"] == ["DAILY"]
    assert rrule["COUNT"] == [10]


def test_params_accessible():
    """Verify params are accessible on parsed properties."""
    ical_str = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VEVENT
UID:test-123
DTSTART;TZID=America/New_York:20250101T100000
SUMMARY:Test Event
END:VEVENT
END:VCALENDAR"""

    cal = Calendar.from_ical(ical_str)
    event = cal.walk("VEVENT")[0]

    # Access property
    dtstart = event["DTSTART"]

    # Can access params
    assert dtstart.params["TZID"] == "America/New_York"


def test_broken_property_vbroken_fallback(calendars):
    """Verify broken properties fall back to vBroken."""
    cal = calendars["broken_dtstart"]
    event = cal.walk("VEVENT")[0]

    # Access broken property
    dtstart = event["DTSTART"]

    # Should fall back to vBroken (which is vText subclass)
    assert isinstance(dtstart, vBroken)
    assert isinstance(dtstart, vText)  # vBroken inherits from vText
    assert str(dtstart) == "INVALID-DATE"

    # Metadata should be present
    assert dtstart.property_name == "DTSTART"
    assert dtstart.expected_type is not None
    assert dtstart.parse_error is not None

    # Error should be recorded immediately
    assert len(event.errors) == 1
    assert event.errors[0][0] == "DTSTART"


def test_broken_property_doesnt_block_others():
    """Verify one broken property doesn't prevent accessing others."""
    ical_str = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VEVENT
UID:test-123
DTSTART:INVALID-DATE
DTEND:20250102T120000Z
SUMMARY:Test Event
END:VEVENT
END:VCALENDAR"""

    cal = Calendar.from_ical(ical_str)
    event = cal.walk("VEVENT")[0]

    # Access valid property should work
    dtend = event["DTEND"]
    assert isinstance(dtend, vDDDTypes)
    assert dtend.dt.year == 2025

    # Access broken property should work (as vBroken)
    dtstart = event["DTSTART"]
    assert isinstance(dtstart, vBroken)

    # Other properties accessible
    summary = event["SUMMARY"]
    assert str(summary) == "Test Event"


def test_property_equality():
    """Verify equality comparisons work with properties."""
    ical_str = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VEVENT
UID:test-123
SUMMARY:Test Event
END:VEVENT
END:VCALENDAR"""

    cal1 = Calendar.from_ical(ical_str)
    cal2 = Calendar.from_ical(ical_str)

    event1 = cal1.walk("VEVENT")[0]
    event2 = cal2.walk("VEVENT")[0]

    # Equality should work
    assert event1["SUMMARY"] == event2["SUMMARY"]
    assert event1["SUMMARY"] == "Test Event"


def test_property_to_ical():
    """Verify to_ical() works correctly with properties."""
    ical_str = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VEVENT
UID:test-123
DTSTART:20250101T100000Z
RRULE:FREQ=DAILY;COUNT=10
SUMMARY:Test Event
END:VEVENT
END:VCALENDAR"""

    cal = Calendar.from_ical(ical_str)

    # to_ical() should work without explicit access
    output = cal.to_ical()

    # Should contain all properties
    assert b"DTSTART:20250101T100000Z" in output
    assert b"RRULE:FREQ=DAILY;COUNT=10" in output
    assert b"SUMMARY:Test Event" in output


def test_multiple_properties_in_list():
    """Verify lists of properties work correctly."""
    ical_str = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VEVENT
UID:test-123
DTSTART:20250101T100000Z
EXDATE:20250105T100000Z
EXDATE:20250106T100000Z
SUMMARY:Test Event
END:VEVENT
END:VCALENDAR"""

    cal = Calendar.from_ical(ical_str)
    event = cal.walk("VEVENT")[0]

    # Access list of properties
    exdates = event["EXDATE"]

    # Should be list of vDDDLists
    assert isinstance(exdates, list)
    assert len(exdates) == 2
    assert all(isinstance(dt, vDDDLists) for dt in exdates)


def test_property_with_tzid():
    """Verify TZID parameter is handled correctly."""
    ical_str = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VEVENT
UID:test-123
DTSTART;TZID=America/New_York:20250101T100000
SUMMARY:Test Event
END:VEVENT
END:VCALENDAR"""

    cal = Calendar.from_ical(ical_str)
    event = cal.walk("VEVENT")[0]

    # Access datetime with TZID
    dtstart = event["DTSTART"]

    # Should be properly parsed with timezone
    assert isinstance(dtstart, vDDDTypes)
    assert dtstart.dt.year == 2025
    assert dtstart.dt.month == 1
    assert dtstart.dt.day == 1


def test_freebusy_comma_separated_values():
    """Verify FREEBUSY comma-separated values work with error-tolerant parsing."""
    ical_str = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VFREEBUSY
UID:test-123
DTSTART:20250101T000000Z
DTEND:20250102T000000Z
FREEBUSY:20250101T100000Z/20250101T120000Z,20250101T140000Z/20250101T160000Z
END:VFREEBUSY
END:VCALENDAR"""

    cal = Calendar.from_ical(ical_str)
    fb = cal.walk("VFREEBUSY")[0]

    # Access FREEBUSY list
    freebusy = fb["FREEBUSY"]

    # Should be list of periods
    assert isinstance(freebusy, list)
    assert len(freebusy) == 2


def test_empty_rdate_workaround():
    """Verify empty RDATE values are handled correctly."""
    ical_str = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VEVENT
UID:test-123
DTSTART:20250101T100000Z
RDATE:
SUMMARY:Test Event
END:VEVENT
END:VCALENDAR"""

    cal = Calendar.from_ical(ical_str)
    event = cal.walk("VEVENT")[0]

    # RDATE should not be in the event
    assert "RDATE" not in event


def test_vbroken_repr(calendars):
    """Verify vBroken repr includes metadata."""
    cal = calendars["broken_dtstart"]
    event = cal.walk("VEVENT")[0]

    # Access broken property
    dtstart = event["DTSTART"]

    # Repr should include metadata
    assert "vBroken" in repr(dtstart)
    assert "INVALID-DATE" in repr(dtstart)
    assert "expected_type" in repr(dtstart)
    assert "property_name" in repr(dtstart)


def test_ignore_exceptions_flag_respected():
    """Verify ignore_exceptions flag behavior."""
    # Event has ignore_exceptions=True
    ical_str_event = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VEVENT
UID:test-123
DTSTART:INVALID
SUMMARY:Test
END:VEVENT
END:VCALENDAR"""

    cal = Calendar.from_ical(ical_str_event)
    event = cal.walk("VEVENT")[0]

    # Should not raise, falls back to vBroken
    dtstart = event["DTSTART"]
    assert isinstance(dtstart, vBroken)
    assert len(event.errors) > 0


def test_property_str():
    """Verify __str__ works."""
    ical_str = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VEVENT
UID:test-123
SUMMARY:Test Event
END:VEVENT
END:VCALENDAR"""

    cal = Calendar.from_ical(ical_str)
    event = cal.walk("VEVENT")[0]

    summary = event["SUMMARY"]
    assert str(summary) == "Test Event"


def test_vbroken_metadata(calendars):
    """Verify vBroken stores parse error metadata."""
    cal = calendars["broken_dtstart"]
    event = cal.walk("VEVENT")[0]
    dtstart = event["DTSTART"]

    assert isinstance(dtstart, vBroken)
    assert dtstart.property_name == "DTSTART"
    assert dtstart.expected_type is not None
    assert dtstart.parse_error is not None


def test_errors_populated_immediately():
    """Verify errors available after from_ical without property access."""
    ical_str = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VEVENT
UID:test-123
DTSTART:INVALID-DATE
DTEND:ALSO-INVALID
SUMMARY:Test
END:VEVENT
END:VCALENDAR"""

    cal = Calendar.from_ical(ical_str)
    event = cal.walk("VEVENT")[0]

    # Errors should be populated WITHOUT accessing properties
    assert len(event.errors) == 2
    assert event.errors[0][0] == "DTSTART"
    assert event.errors[1][0] == "DTEND"


def test_typeerror_handling_in_tolerant_mode():
    """Verify TypeError exceptions are caught in error-tolerant mode.

    This test addresses the concern raised in PR #1044 review that
    TypeError exceptions should be handled consistently with ValueError.
    """
    # Event has ignore_exceptions=True (error-tolerant)
    # Using RRULE with invalid type that triggers TypeError during parsing
    ical_str = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VEVENT
UID:test-123
DTSTART:20250101T100000Z
RRULE:FREQ=INVALID_TYPE_CAUSES_ERROR
SUMMARY:Test Event
END:VEVENT
END:VCALENDAR"""

    # Should not raise - error-tolerant mode catches TypeError
    cal = Calendar.from_ical(ical_str)
    event = cal.walk("VEVENT")[0]

    # RRULE should fall back to vBroken
    rrule = event["RRULE"]
    assert isinstance(rrule, vBroken)

    # Error should be recorded
    assert len(event.errors) >= 1
    assert any("RRULE" in error[0] for error in event.errors)


def test_parse_error_is_exception_object(calendars):
    """Verify parse_error stores the actual exception, not a string."""
    cal = calendars["broken_dtstart"]
    event = cal.walk("VEVENT")[0]
    dtstart = event["DTSTART"]

    assert isinstance(dtstart, vBroken)
    assert isinstance(dtstart.parse_error, Exception)


def test_vbroken_getattr_raises_broken_calendar_property():
    """Verify accessing missing attributes raises BrokenCalendarProperty."""
    broken = vBroken(
        "INVALID",
        property_name="DTSTART",
        expected_type="vDDDTypes",
        parse_error=ValueError("bad value"),
    )

    with pytest.raises(BrokenCalendarProperty) as exc_info:
        broken.dt

    assert exc_info.value.__cause__ is broken.parse_error
    assert "DTSTART" in str(exc_info.value)
    assert "vDDDTypes" in str(exc_info.value)


def test_vbroken_getattr_preserves_existing_attributes():
    """Verify normal attributes still work on vBroken."""
    broken = vBroken(
        "INVALID",
        property_name="DTSTART",
        expected_type="vDDDTypes",
        parse_error=ValueError("bad value"),
    )

    # These should all work without raising
    assert broken.property_name == "DTSTART"
    assert broken.expected_type == "vDDDTypes"
    assert isinstance(broken.parse_error, ValueError)
    assert isinstance(broken.params, dict)
    assert broken.encoding is not None


def test_event_dtstart_raises_broken_calendar_property(calendars):
    """Verify event.DTSTART raises BrokenCalendarProperty for broken values."""
    cal = calendars["broken_dtstart"]
    event = cal.walk("VEVENT")[0]

    with pytest.raises(BrokenCalendarProperty) as exc_info:
        event.DTSTART

    assert exc_info.value.__cause__ is not None

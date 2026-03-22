"""Tests for issue #857: enhanced API usability improvements."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from icalendar import Calendar, Event
from icalendar.error import IncompleteComponent


def test_calendar_new_with_organization_and_language():
    """Test Calendar.new() with organization and language. Generates proper prodid."""
    calendar = Calendar.new(organization="foo.org", name="My parties", language="en")

    assert calendar.calendar_name == "My parties"
    assert calendar.prodid == "-//foo.org//My parties//EN"


def test_calendar_new_with_organization_no_language():
    """Test Calendar.new() with organization but no language. Defaults to EN."""
    calendar = Calendar.new(organization="example.com", name="Test Calendar")

    assert calendar.prodid == "-//example.com//Test Calendar//EN"


def test_calendar_new_with_organization_no_name():
    """Test Calendar.new() with organization but no name. Uses 'Calendar'."""
    calendar = Calendar.new(organization="example.com", language="fr")

    assert calendar.prodid == "-//example.com//Calendar//FR"


def test_calendar_new_explicit_prodid_overrides_organization():
    """Test that explicit prodid overrides organization-based generation."""
    calendar = Calendar.new(
        organization="foo.org",
        name="My parties",
        language="en",
        prodid="-//Custom//Product//ID",
    )

    assert calendar.prodid == "-//Custom//Product//ID"


def test_calendar_new_no_organization_uses_default_prodid():
    """Test that without organization, default prodid is used."""
    calendar = Calendar.new(name="Test Calendar")

    # Should use the default icalendar prodid
    assert "collective" in calendar.prodid
    assert "icalendar" in calendar.prodid


def test_event_duration_setter():
    """Test that setting event duration. Correctly calculates end time."""
    event = Event.new(summary="Test Meeting", start=datetime(2026, 3, 19, 12, 30))

    # Set duration
    event.duration = timedelta(hours=2)

    assert event.duration == timedelta(hours=2)
    assert event.end == datetime(2026, 3, 19, 14, 30)


def test_event_duration_setter_with_timezone():
    """Test duration setter. Works with timezone-aware events."""
    start_time = datetime(2026, 3, 19, 12, 30, tzinfo=ZoneInfo("Europe/London"))
    event = Event.new(summary="Test Meeting", start=start_time)

    event.duration = timedelta(minutes=90)

    expected_end = start_time + timedelta(minutes=90)
    assert event.duration == timedelta(minutes=90)
    assert event.end == expected_end


def test_event_duration_setter_without_start_raises_error():
    """Test that setting duration without start time. Raises error."""
    event = Event.new(summary="Incomplete Event")

    with pytest.raises(
        IncompleteComponent, match="Cannot set duration without DTSTART"
    ):
        event.duration = timedelta(hours=1)


def test_calendar_validate_missing_prodid():
    """Test that validate() detects missing PRODID."""
    calendar = Calendar()
    calendar.add("VERSION", "2.0")
    event = Event.new(summary="Test", start=datetime(2026, 3, 19, 12, 30))
    calendar.add_component(event)

    with pytest.raises(IncompleteComponent, match="Calendar must have a PRODID"):
        calendar.validate()


def test_calendar_validate_missing_version():
    """Test that validate() detects missing VERSION."""
    calendar = Calendar()
    calendar.add("PRODID", "-//Test//Test//EN")
    event = Event.new(summary="Test", start=datetime(2026, 3, 19, 12, 30))
    calendar.add_component(event)

    with pytest.raises(IncompleteComponent, match="Calendar must have a VERSION"):
        calendar.validate()


def test_calendar_validate_no_components():
    """Test that validate() detects empty calendar."""
    calendar = Calendar()
    calendar.add("PRODID", "-//Test//Test//EN")
    calendar.add("VERSION", "2.0")

    with pytest.raises(
        IncompleteComponent, match="Calendar must contain at least one component"
    ):
        calendar.validate()


def test_calendar_validate_passes_with_valid_calendar():
    """Test that validate() succeeds with valid calendar."""
    calendar = Calendar.new(name="Valid Calendar")
    event = Event.new(
        summary="Test Event",
        start=datetime(2026, 3, 19, 12, 30),
        end=datetime(2026, 3, 19, 14, 30),
    )
    calendar.add_component(event)

    # Should not raise any exception
    calendar.validate()

    # to_ical should still work normally
    ical_output = calendar.to_ical()
    assert b"BEGIN:VCALENDAR" in ical_output
    assert b"BEGIN:VEVENT" in ical_output


def test_user_desired_workflow_from_issue_857():
    """Test the exact workflow desired by the user in issue #857."""
    # User's ideal API: Calendar(organization="foo.org", name="My parties", language="en")
    cal = Calendar.new(organization="foo.org", name="My parties", language="en")

    # User's ideal API: Event(start=mydatetime)
    mydatetime = datetime(2026, 3, 19, 12, 30, tzinfo=ZoneInfo("UTC"))
    event = Event.new(start=mydatetime)

    # User wanted: event.end = mydatetime + timedelta(minutes=15)
    event.duration = timedelta(minutes=15)  # This achieves the same result

    # User wanted: event.name = "Some string" (summary works as alias)
    event.summary = "Some string"

    # Verify the result
    assert cal.calendar_name == "My parties"
    assert cal.prodid == "-//foo.org//My parties//EN"
    assert event.start == mydatetime
    assert event.end == mydatetime + timedelta(minutes=15)
    assert event.summary == "Some string"
    assert event.duration == timedelta(minutes=15)

    # Add event to calendar and generate valid output
    cal.add_component(event)
    ical_output = cal.to_ical()
    assert b"PRODID:-//foo.org//My parties//EN" in ical_output


def test_enhanced_api_compared_to_original_example():
    """Test that enhanced API is much simpler than original example from issue."""
    # Original complex example from issue #857:
    # Required knowing: PRODID, VERSION, SUMMARY, DTSTART, DTEND, DTSTAMP fields
    # Required manual timezone handling

    # Enhanced API - much simpler:
    cal = Calendar.new(organization="example.com", name="My calendar")
    event = Event.new(
        summary="Python meeting about calendaring",
        start=datetime(2005, 4, 4, 8, 0, 0, tzinfo=ZoneInfo("UTC")),
    )
    event.duration = timedelta(hours=2)  # Much simpler than calculating DTEND

    cal.add_component(event)

    # Automatic timezone handling
    cal.add_missing_timezones()

    ical_output = cal.to_ical().decode()

    # Verify key improvements:
    # 1. Automatic PRODID generation from organization
    assert "-//example.com//My calendar//EN" in ical_output
    # 2. Automatic VERSION and other required fields
    assert "VERSION:2.0" in ical_output
    # 3. Automatic UID and DTSTAMP generation (from Event.new())
    assert "UID:" in ical_output
    assert "DTSTAMP:" in ical_output
    # 4. Proper timezone handling and duration usage
    assert "DTSTART" in ical_output
    assert (
        "DURATION" in ical_output
    )  # Uses DURATION instead of DTEND when duration is set

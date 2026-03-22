"""Tests for issue #1066: Calendar.new() should auto-generate UID.

See https://github.com/collective/icalendar/issues/1066
"""

import uuid

from icalendar import Calendar


def test_calendar_new_auto_generates_uid(test_uid):
    """Test that Calendar.new() automatically generates a UID when not provided."""
    calendar = Calendar.new()

    # UID should not be None
    assert calendar.uid is not None

    # UID should match the test fixture default
    assert str(calendar.uid) == test_uid


def test_calendar_new_respects_explicit_uid():
    """Test that Calendar.new() respects explicitly provided UID."""
    custom_uid = "test-calendar-uid"
    calendar = Calendar.new(uid=custom_uid)

    assert calendar.uid == custom_uid


def test_calendar_new_accepts_uuid_object():
    """Test that Calendar.new() accepts UUID objects as uid parameter."""
    custom_uuid = uuid.UUID("12345678-1234-5678-1234-567812345678")
    calendar = Calendar.new(uid=custom_uuid)

    # The uid property returns a string representation
    assert str(calendar.uid) == str(custom_uuid)


def test_calendar_new_uid_appears_in_ical_output():
    """Test that the auto-generated UID appears in the iCalendar output."""
    calendar = Calendar.new(name="Test Calendar")

    ical_output = calendar.to_ical()

    # UID should be present in the output
    assert b"UID:" in ical_output
    # The UID value should match what we set
    assert str(calendar.uid).encode() in ical_output


def test_issue_1066_original_assertion():
    """Test the exact assertion from issue #1066."""
    # This was failing before the fix
    assert Calendar.new().uid is not None

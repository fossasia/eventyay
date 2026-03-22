"""Testing multiple VCALENDAR components and multiple VEVENT components"""

import pytest

from icalendar import Event, vText


def test_multiple(calendars):
    """Check opening multiple calendars."""

    cals = calendars.multiple.multiple_calendar_components

    assert len(cals) == 2
    assert [comp.name for comp in cals[0].walk()] == ["VCALENDAR", "VEVENT"]
    assert [comp.name for comp in cals[1].walk()] == ["VCALENDAR", "VEVENT", "VEVENT"]
    assert cals[0]["prodid"] == vText(
        "-//Mozilla.org/NONSGML Mozilla Calendar V1.0//EN"
    )


def test_multiple_events():
    """Raises ValueError unless multiple=True"""
    event_components = """
BEGIN:VEVENT
END:VEVENT
BEGIN:VEVENT
END:VEVENT
"""
    with pytest.raises(ValueError):
        Event.from_ical(event_components, multiple=False)


def test_missing_event():
    """Raises ValueError if no component found"""
    with pytest.raises(ValueError):
        Event.from_ical("")

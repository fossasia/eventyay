"""Test that composed values are properly converted."""

from datetime import datetime

from icalendar.cal.event import Event


def test_vDDDLists_timezone(tzp):
    """Test vDDDLists with timezone information."""
    vevent = Event()
    dt1 = tzp.localize(datetime(2013, 1, 1), "Europe/Vienna")
    dt2 = tzp.localize(datetime(2013, 1, 2), "Europe/Vienna")
    dt3 = tzp.localize(datetime(2013, 1, 3), "Europe/Vienna")
    vevent.add("rdate", [dt1, dt2])
    vevent.add("exdate", dt3)
    ical = vevent.to_ical()

    assert b"RDATE;TZID=Europe/Vienna:20130101T000000,20130102T000000" in ical
    assert b"EXDATE;TZID=Europe/Vienna:20130103T000000" in ical

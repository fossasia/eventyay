"""Some parameters are specified as default by the RFC 5545.

These tests make sure that these parameter values are not added to the
properties.

Example:

       DTSTART;VALUE=DATE-TIME:20190616T050000Z
equals DTSTART:20190616T050000Z

See https://github.com/collective/icalendar/issues/318
"""

from datetime import datetime

import pytest

from icalendar.cal.event import Event


@pytest.mark.parametrize(
    "attr",
    [
        "DTSTART",
        "DTEND",
        "DTSTAMP",
    ],
)
def test_datetime_in_event(attr):
    """Check that the "VALUE=DATE-TIME" is absent because not needed."""
    event = Event()
    event.add(attr, datetime(2022, 10, 13, 9, 16, 42))
    ics = event.to_ical()
    assert b"VALUE=DATE-TIME" not in ics

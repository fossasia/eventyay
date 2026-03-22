"""Parse the calendar and make sure the timezone is used.

See https://github.com/collective/icalendar/issues/218
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from icalendar.timezone.tzid import tzid_from_dt

if TYPE_CHECKING:
    from icalendar.cal.event import Event


@pytest.fixture
def event(calendars) -> Event:
    """The event to check."""
    return calendars.issue_218_bad_tzid.events[0]


def test_event_has_start_and_end(event: Event):
    """The calendar should be parsed and the start and end have a timezone."""
    assert event.start.replace(tzinfo=None) == datetime(2017, 2, 28, 23, 00)
    assert event.end.replace(tzinfo=None) == datetime(2017, 2, 28, 23, 30)


def test_timezone(event: Event):
    """The event uses a timezone."""
    assert event.start.tzinfo == event.end.tzinfo
    assert tzid_from_dt(event.start) == "UTC+11"
    assert event.start.utcoffset() == timedelta(hours=11)

"""This tests the RDATE property."""

from __future__ import annotations

from datetime import date, datetime
from pprint import pprint
from typing import TYPE_CHECKING

import pytest

from icalendar.cal.event import Event
from icalendar.cal.journal import Journal
from icalendar.cal.timezone import TimezoneDaylight, TimezoneStandard
from icalendar.cal.todo import Todo

if TYPE_CHECKING:
    from icalendar.cal.calendar import (
        Calendar,
    )

C_RDATE = Event | Todo | Journal | TimezoneDaylight | TimezoneStandard


@pytest.fixture(params=[Event, Todo, Journal, TimezoneDaylight, TimezoneStandard])
def c_rdate(request) -> C_RDATE:
    """Return a component that uses RDATE."""
    return request.param()


@pytest.fixture(
    params=[
        lambda _tzp: date(2019, 10, 11),
        lambda _tzp: datetime(2000, 1, 13, 12, 1),
        lambda tzp: tzp.localize_utc(datetime(2031, 12, 1, 23, 59)),
        lambda tzp: tzp.localize(datetime(1984, 1, 13, 13, 1), "Europe/Athens"),
        lambda _tzp: ((datetime(2000, 1, 13, 12, 1), datetime(2000, 1, 13, 12, 2))),
        lambda tzp: (
            (
                tzp.localize_utc(datetime(2001, 1, 13, 12, 1)),
                tzp.localize_utc(datetime(2001, 1, 13, 12, 2)),
            )
        ),
    ]
)
def rdate(request, tzp):
    """Possible values for an rdate."""
    return request.param(tzp)


def test_no_rdates_by_default(c_rdate):
    """We expect no rdate by default."""
    assert c_rdate.rdates == []


def test_set_and_retrieve_rdate(rdate, c_rdate):
    """Set the attribute and get the value."""
    c_rdate.add("RDATE", [rdate])
    result = [rdate if isinstance(rdate, tuple) else (rdate, None)]
    assert c_rdate.rdates == result


def test_get_example_0(calendars):
    """Test an example rdate."""
    cal: Calendar = calendars.rfc_5545_RDATE_example
    event = cal.events[0]
    assert event.rdates == [(datetime(1997, 7, 14, 12, 30), None)]


def test_get_example_1(calendars, tzp):
    """Test an example rdate."""
    cal: Calendar = calendars.rfc_5545_RDATE_example
    event = cal.events[1]
    assert event.rdates == [(tzp.localize_utc(datetime(1997, 7, 14, 12, 30)), None)]


def test_get_example_2(calendars, tzp):
    """Test an example rdate."""
    cal: Calendar = calendars.rfc_5545_RDATE_example
    event = cal.events[2]
    assert event.rdates == [
        (tzp.localize(datetime(1997, 7, 14, 8, 30), "America/New_York"), None)
    ]


def test_get_example_3(calendars, tzp):
    """Test an example rdate."""
    cal: Calendar = calendars.rfc_5545_RDATE_example
    event = cal.events[3]
    rdates_3 = [
        (
            tzp.localize_utc(datetime(1996, 4, 3, 2)),
            tzp.localize_utc(datetime(1996, 4, 3, 4)),
        ),
        (
            tzp.localize_utc(datetime(1996, 4, 4, 1)),
            tzp.localize_utc(datetime(1996, 4, 4, 4)),
        ),
    ]
    pprint(event.rdates)
    pprint(rdates_3)
    assert event.rdates == rdates_3


def d(i: int) -> tuple[date, None]:
    s = str(i)
    return (date(int(s[:4]), int(s[4:6].lstrip("0")), int(s[6:].lstrip("0"))), None)


RDATES_4 = list(
    map(
        d,
        (
            19970101,
            19970120,
            19970217,
            19970421,
            19970526,
            19970704,
            19970901,
            19971014,
            19971128,
            19971129,
            19971225,
        ),
    )
)


def test_get_example_4(calendars, tzp):
    """Test an example rdate."""
    cal: Calendar = calendars.rfc_5545_RDATE_example
    event = cal.events[4]
    pprint(event.rdates)
    pprint(RDATES_4)
    assert event.rdates == RDATES_4

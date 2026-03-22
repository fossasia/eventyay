"""Test getting the rrules from a component."""

import pytest

from icalendar import (
    vRecur,
)
from icalendar.cal.component import Component
from icalendar.cal.event import Event
from icalendar.cal.journal import Journal
from icalendar.cal.timezone import TimezoneDaylight, TimezoneStandard
from icalendar.cal.todo import Todo

RRULE_0 = vRecur.from_ical("FREQ=DAILY;COUNT=10")
RRULE_1 = vRecur.from_ical("FREQ=DAILY;UNTIL=19971224T000000Z")
RRULE_2 = vRecur.from_ical("FREQ=DAILY;INTERVAL=2")
RRULE_3 = vRecur.from_ical("FREQ=DAILY;INTERVAL=10;COUNT=5")
RRULE_4 = vRecur.from_ical(
    "FREQ=YEARLY;UNTIL=20000131T140000Z;BYMONTH=1;BYDAY=SU,MO,TU,WE,TH,FR,SA"
)


@pytest.fixture(params=[RRULE_0, RRULE_1, RRULE_2, RRULE_3, RRULE_4])
def rrule(request) -> str:
    """An rrule."""
    return request.param


@pytest.fixture(params=[Event, Todo, Journal, TimezoneDaylight, TimezoneStandard])
def c_rrule(request) -> Component:
    """Return a component that uses RDATE."""
    return request.param()


def test_no_rrules_by_default(c_rrule):
    """We expect no rdate by default."""
    assert c_rrule.rrules == []


def test_one_rrule(c_rrule, rrule):
    """Add one rrule."""
    c_rrule.add("rrule", rrule)
    assert c_rrule.rrules == [rrule]


def test_two_rrules(c_rrule, rrule):
    """Add two rrules."""
    c_rrule.add("rrule", rrule)
    c_rrule.add("rrule", RRULE_3)
    assert c_rrule.rrules == [rrule, RRULE_3]

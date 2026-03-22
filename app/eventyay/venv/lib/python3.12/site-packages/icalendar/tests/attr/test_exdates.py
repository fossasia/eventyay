"""This tests the exdate property."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from icalendar import (
    Event,
    Journal,
    TimezoneDaylight,
    TimezoneStandard,
    Todo,
)

C_EXDATE = Event | Todo | Journal | TimezoneDaylight | TimezoneStandard


@pytest.fixture(params=[Event, Todo, Journal, TimezoneDaylight, TimezoneStandard])
def c_exdate(request) -> C_EXDATE:
    """Return a component that uses exdate."""
    return request.param()


@pytest.fixture(
    params=[
        lambda _tzp: date(2019, 10, 11),
        lambda _tzp: datetime(2000, 1, 13, 12, 1),
        lambda tzp: tzp.localize_utc(datetime(2031, 12, 1, 23, 59)),
        lambda tzp: tzp.localize(datetime(1984, 1, 13, 13, 1), "Europe/Athens"),
    ]
)
def exdate(request, tzp):
    """Possible values for an exdate."""
    return request.param(tzp)


def test_no_exdates_by_default(c_exdate):
    """We expect no exdate by default."""
    assert c_exdate.exdates == []


def test_set_and_retrieve_exdate(exdate, c_exdate):
    """Set the attribute and get the value."""
    c_exdate.add("exdate", [exdate])
    result = [exdate]
    assert c_exdate.exdates == result


def test_set_and_retrieve_exdates_in_list(exdate, c_exdate):
    """Set the attribute and get the value."""
    c_exdate.add("exdate", [exdate, exdate])
    result = [exdate, exdate]
    assert c_exdate.exdates == result


def test_set_and_retrieve_exdates_twice(exdate, c_exdate):
    """Set the attribute and get the value."""
    c_exdate.add("exdate", [exdate])
    c_exdate.add("exdate", [exdate])
    result = [exdate, exdate]
    assert c_exdate.exdates == result

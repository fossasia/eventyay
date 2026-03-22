from datetime import date, datetime, time, timedelta

import pytest

from icalendar.prop import vDDDTypes


def test_instance():
    assert isinstance(vDDDTypes.from_ical("20010101T123000"), datetime)
    assert isinstance(vDDDTypes.from_ical("20010101"), date)


def test_datetime_with_timezone(tzp):
    assert vDDDTypes.from_ical("20010101T123000Z") == tzp.localize_utc(
        datetime(2001, 1, 1, 12, 30)
    )


def test_timedelta():
    assert vDDDTypes.from_ical("P31D") == timedelta(31)
    assert vDDDTypes.from_ical("-P31D") == timedelta(-31)


def test_bad_input():
    with pytest.raises(TypeError):
        vDDDTypes(42)


def test_time_from_string():
    assert vDDDTypes.from_ical("123000") == time(12, 30)
    assert isinstance(vDDDTypes.from_ical("123000"), time)


def test_invalid_period_to_ical():
    invalid_period = (datetime(2000, 1, 1), datetime(2000, 1, 2), datetime(2000, 1, 2))
    with pytest.raises(ValueError):
        vDDDTypes(invalid_period).to_ical()

import pytest

from icalendar.prop import vWeekday


def test_simple():
    weekday = vWeekday("SU")
    assert weekday.to_ical() == b"SU"
    assert weekday.weekday == "SU"
    assert weekday.relative is None


def test_relative():
    weekday = vWeekday("-1MO")
    assert weekday.to_ical() == b"-1MO"
    assert weekday.weekday == "MO"
    assert weekday.relative == -1


def test_roundtrip():
    assert vWeekday.from_ical(vWeekday("+2TH").to_ical()) == "+2TH"


def test_error():
    """Error: Expected weekday abbrevation, got: -100MO"""
    with pytest.raises(ValueError):
        vWeekday.from_ical("-100MO")

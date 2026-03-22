"""This file collects errors that the OSS FUZZ build has found."""

from datetime import time

import pytest

from icalendar.cal.calendar import Calendar
from icalendar.prop import vDDDLists


def test_stack_is_empty():
    """If we get passed an invalid string, we expect to get a ValueError."""
    with pytest.raises(ValueError):
        Calendar.from_ical("END:CALENDAR")


def test_vdd_list_type_mismatch():
    """If we pass in a string type, we expect it to be converted to bytes"""
    vddd_list = vDDDLists([time(hour=6, minute=6, second=6)])
    assert vddd_list.to_ical() == b"060606"

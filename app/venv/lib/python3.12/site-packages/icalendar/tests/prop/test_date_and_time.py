"""Testing functionality that is common to date and time property types."""

from datetime import datetime, time
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest

from icalendar import Component, vDatetime, vDDDLists, vDDDTypes, vTime
from icalendar.parser_tools import to_unicode
from icalendar.prop import VPROPERTY
from icalendar.timezone.tzid import is_utc

if TYPE_CHECKING:
    from icalendar.cal.event import Event


@pytest.fixture(
    params=[
        vDatetime(datetime(2018, 1, 1, tzinfo=ZoneInfo("UTC"))),
        vTime(time(1, 1, tzinfo=ZoneInfo("UTC"))),
    ]
)
def utc_prop(request):
    return request.param


@pytest.mark.parametrize("convert", [None, vDDDLists, vDDDTypes])
def test_setting_a_utc_datetime_value_does_not_include_a_TZID(
    utc_prop: VPROPERTY, convert
):
    """Check that the VALUE parameter is correctly determined."""
    if convert:
        utc_prop = convert(utc_prop.dt)
    assert not utc_prop.params.tzid, "UTC datetimes must not carry a TZID parameter"
    component = Component()
    component.add("X-PROP", utc_prop)
    component.add("DTSTAMP", utc_prop)
    component.add("DTSTART", utc_prop)
    component.add("DUE", utc_prop)

    ical = component.to_ical().decode()
    print(ical)
    assert "TZID" not in ical


def test_converting_to_utc_puts_a_z_in_the_end(utc_prop: VPROPERTY):
    """Test that the Z is appended.

    :rfc:`5545`, TIME:
        UTC time, or absolute time, is identified by a LATIN CAPITAL
        LETTER Z suffix character, the UTC designator, appended to the
        time value.  For example, the following represents 07:00 AM UTC:

        .. code-block:: text

            070000Z

        The "TZID" property parameter MUST NOT be applied to TIME
        properties whose time values are specified in UTC.

    :rfc:`5545`, DATE-TIME:
        The date with UTC time, or absolute time, is identified by a LATIN
        CAPITAL LETTER Z suffix character, the UTC designator, appended to
        the time value.  For example, the following represents January 19,
        1998, at 0700 UTC:

        .. code-block:: text

            19980119T070000Z

        The "TZID" property parameter MUST NOT be applied to DATE-TIME
        properties whose time values are specified in UTC.

    """
    ical = to_unicode(utc_prop.to_ical())
    assert ical.endswith("Z")


def test_reformed_UTC_serialization(events):
    """Check that UTC values are still propertly serialized."""
    event: Event = events.issue_156_RDATE_with_PERIOD
    utc_value = event["DTSTART"]
    assert is_utc(utc_value.dt)
    # TODO: the UTC parameter is special - it can be present but should not be serialized
    # How should we treat the parameter?
    # I think: have it there, but do not serialize it

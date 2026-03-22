"""Test that we can identify all timezones.

Timezones can be removed from ./timezone_ids.py if they make the tests fail:
Timezone information changes over time and can be dependent on the operating system's
timezone database (zoneinfo, dateutil) or the package (pytz).
We want to make sure we can roughly identify most of them.
"""

import sys
from datetime import datetime, timedelta, timezone

import pytest

from icalendar.timezone import is_utc, tzid_from_tzinfo, tzids_from_tzinfo
from icalendar.timezone.tzp import TZP


def test_can_identify_zoneinfo(tzid, zoneinfo_only, tzp: TZP):
    """Check that all those zoneinfo timezones can be identified."""
    assert tzid in tzids_from_tzinfo(tzp.timezone(tzid))


def test_can_identify_pytz(tzid, pytz_only, tzp: TZP):
    """Check that all those pytz timezones can be identified."""
    assert tzid in tzids_from_tzinfo(tzp.timezone(tzid))


def test_can_identify_dateutil(tzid):
    """Check that all those dateutil timezones can be identified."""
    from dateutil.tz import gettz

    assert tzid in tzids_from_tzinfo(gettz(tzid))


def test_utc_is_identified(utc):
    """Test UTC because it is handled in a special way."""
    assert "UTC" in tzids_from_tzinfo(utc)
    assert tzid_from_tzinfo(utc) == "UTC"
    assert is_utc(utc)


def test_some_timezones_are_not_utc(tzp: TZP):
    """If we have an offset, it is not utc."""
    assert not is_utc(tzp.timezone("Europe/Berlin"))


def test_some_timezones_are_recognized_as_utc():
    """If we are at 0 offset, it is utc."""
    tzinfo = timezone(timedelta(hours=0))
    assert is_utc(tzinfo)
    assert is_utc(datetime(2019, 1, 1, 0, 0, 0, 0, tzinfo=tzinfo))


@pytest.mark.parametrize(
    "tzinfo",
    [
        timezone(timedelta(hours=1)),
        timezone(timedelta(hours=-1)),
        timezone(timedelta(hours=2)),
        timezone(timedelta(hours=-2)),
    ],
)
def test_getting_a_timezone_name_for_timezones(tzinfo):
    """We should get a name that we can use."""
    assert tzid_from_tzinfo(tzinfo)


@pytest.mark.skipif(sys.platform != "win32", reason="tzwin only exists on Windows")
def test_tzwin_utc_is_identified():
    """tzwin('UTC') from dateutil.tz.gettz('UTC') must be recognized as UTC.

    On Windows, dateutil.tz.gettz('UTC') returns tzwin('UTC') whose tzname()
    is 'Coordinated Universal Time', not 'UTC'. This must still be identified
    as UTC so that datetimes use the Z suffix instead of a TZID parameter.
    """
    from dateutil.tz import gettz

    tzinfo = gettz("UTC")  # returns tzwin('UTC') on Windows
    assert "UTC" in tzids_from_tzinfo(tzinfo)
    assert tzid_from_tzinfo(tzinfo) == "UTC"
    assert is_utc(tzinfo)


@pytest.mark.skipif(sys.platform != "win32", reason="tzwin only exists on Windows")
def test_tzwin_non_utc_is_identified():
    """tzwin for a non-UTC Windows timezone maps to its IANA equivalent."""
    from dateutil.tz import gettz

    tzinfo = gettz("Eastern Standard Time")
    assert tzid_from_tzinfo(tzinfo) == "America/New_York"

"""Generate VTIMEZONE components from actual timezone information.

When we generate VTIMEZONE from actual tzinfo instances of
- dateutil
- zoneinfo
- pytz

Then, we cannot assume that the future information stays the same but
we should be able to create tests that work for the past.

See https://github.com/collective/icalendar/issues/722
"""

import zoneinfo
from copy import deepcopy
from datetime import date, datetime, timedelta
from re import findall

import pytest
from dateutil.tz import gettz

from icalendar import Calendar, Component, Event, Timezone
from icalendar.timezone import tzid_from_tzinfo, tzids_from_tzinfo

tzids = pytest.mark.parametrize(
    "tzid",
    [
        "Europe/Berlin",
        "Asia/Singapore",
        "America/New_York",
    ],
)


def assert_components_equal(c1: Component, c2: Component):
    """Print the diff of two components."""
    ML = 32
    ll1 = c1.to_ical().decode().splitlines()
    ll2 = c2.to_ical().decode().splitlines()
    pad = max(len(l) for l in ll1 if len(l) <= ML)
    diff = 0
    for l1, l2 in zip(ll1, ll2, strict=False):
        a = len(l1) > 32 or len(l2) > 32
        print(
            a * "  " + l1,
            " " * (pad - len(l1)),
            a * "\n->" + l2,
            " " * (pad - len(l2)),
            "\tdiff!" if l1 != l2 else "",
        )
        diff += l1 != l2
    assert not diff, f"{diff} lines differ"


@tzids
def test_conversion_converges(tzp, tzid):
    """tzinfo -> VTIMEZONE -> tzinfo -> VTIMEZONE

    We can assume that both generated VTIMEZONEs are equivalent.
    """
    if tzp.uses_pytz():
        pytest.skip(
            "pytz will not converge on the first run. This is problematic. PYTZ-TODO"
        )
    tzinfo1 = tzp.timezone(tzid)
    assert tzinfo1 is not None
    generated1 = Timezone.from_tzinfo(tzinfo1)
    generated1["TZID"] = (
        "test-generated"  # change the TZID so we do not use an existing one
    )
    tzinfo2 = generated1.to_tz()
    generated2 = Timezone.from_tzinfo(tzinfo2, "test-generated")
    tzinfo3 = generated2.to_tz()
    generated3 = Timezone.from_tzinfo(tzinfo3, "test-generated")
    # pprint(generated1.get_transitions())
    # pprint(generated2.get_transitions())
    assert_components_equal(generated1, generated2)
    assert_components_equal(generated2, generated3)
    assert 2 <= len(generated1.standard + generated1.daylight) <= 3
    assert 2 <= len(generated2.standard + generated2.daylight) <= 3
    assert dict(generated1) == dict(generated2)
    assert generated1.to_ical().decode() == generated2.to_ical().decode()
    assert generated1.daylight == generated2.daylight
    assert generated1.standard == generated2.standard
    assert generated1 == generated2


@tzids
def both_tzps_generate_the_same_info(tzid, tzp):
    """We want to make sure that we get the same info for all timezone implementations.

    We assume that
    - the timezone implementations have the same info within the days we test
    - the timezone transitions times do not change because they are before last_date
    """
    # default generation
    tz1 = Timezone.from_tzid(tzid, tzp, last_date=date(2024, 1, 1))
    tzp.use_zoneinfo()  # we compare to zoneinfo
    tz2 = Timezone.from_tzid(tzid, tzp, last_date=date(2024, 1, 1))
    assert_components_equal(tz1, tz2)
    assert tz1 == tz2


@tzids
def test_tzid_matches(tzid, tzp):
    """Check the TZID."""
    tz = Timezone.from_tzinfo(tzp.timezone(tzid))
    assert tz["TZID"] == tzid


def test_do_not_convert_utc(tzp):
    """We do not need to convert UTC but it should work."""
    utc = Timezone.from_tzid("UTC")
    assert utc.daylight == []
    assert len(utc.standard) == 1
    standard = utc.standard[0]
    assert standard["TZOFFSETFROM"].td == timedelta(0)
    assert standard["TZOFFSETTO"].td == timedelta(0)
    assert standard["TZNAME"] == "UTC"


def test_berlin_time(tzp):
    """Test the Europe/Berlin timezone conversion."""
    tz = Timezone.from_tzid("Europe/Berlin")
    # we should have two timezones in it
    for x in tz.standard:
        print(x.name, x["TZNAME"], x["TZOFFSETFROM"].td, x["TZOFFSETTO"].td)
        print(x.to_ical().decode())
    assert len(tz.daylight) == 1
    assert len(tz.standard) in (1, 2), "We start in winter"
    dst = tz.daylight[-1]
    sta = tz.standard[-1]
    assert dst["TZNAME"] == "CEST"  # summer
    assert sta["TZNAME"] == "CET"
    assert dst["TZOFFSETFROM"].td == timedelta(hours=1)  # summer
    assert sta["TZOFFSETFROM"].td == timedelta(hours=2)
    assert dst["TZOFFSETTO"].td == timedelta(hours=2)  # summer
    assert sta["TZOFFSETTO"].td == timedelta(hours=1)


def test_range_is_not_crossed():
    first_date = datetime(2023, 1, 1)
    last_date = datetime(2024, 1, 1)

    def check(dt):
        assert first_date <= dt <= last_date

    tz = Timezone.from_tzid("Europe/Berlin", last_date=last_date, first_date=first_date)
    for sub in tz.standard + tz.daylight:
        check(sub.DTSTART)
        for rdate in sub.get("RDATE", []):
            check(rdate)


@tzids
def test_use_the_original_timezone(tzid, tzp):
    """When we get the timezone again, usually, we should use the
    one of the library/tzp."""
    tzinfo1 = tzp.timezone(tzid)
    assert tzinfo1 is not None
    generated1 = Timezone.from_tzinfo(tzinfo1)
    tzinfo2 = generated1.to_tz()
    assert type(tzinfo1) == type(tzinfo2)
    assert tzinfo1 == tzinfo2


@pytest.mark.parametrize(
    ("tzid", "dt", "tzname"),
    [
        ("Asia/Singapore", datetime(1970, 1, 1), "+0730"),
        ("Asia/Singapore", datetime(1981, 12, 31), "+0730"),
        ("Asia/Singapore", datetime(1981, 12, 31, 23, 10), "+0730"),
        ("Asia/Singapore", datetime(1981, 12, 31, 23, 34), "+0730"),
        ("Asia/Singapore", datetime(1981, 12, 31, 23, 59, 59), "+0730"),
        ("Asia/Singapore", datetime(1982, 1, 1), "+08"),
        ("Asia/Singapore", datetime(1982, 1, 1, 0, 1), "+08"),
        ("Asia/Singapore", datetime(1982, 1, 1, 0, 34), "+08"),
        ("Asia/Singapore", datetime(1982, 1, 1, 1, 0), "+08"),
        ("Asia/Singapore", datetime(1982, 1, 1, 1, 1), "+08"),
        ("Europe/Berlin", datetime(1970, 1, 1), "CET"),
        ("Europe/Berlin", datetime(2024, 3, 31, 0, 0), "CET"),
        ("Europe/Berlin", datetime(2024, 3, 31, 1, 0), "CET"),
        ("Europe/Berlin", datetime(2024, 3, 31, 2, 0), "CET"),
        ("Europe/Berlin", datetime(2024, 3, 31, 2, 59, 59), "CET"),
        ("Europe/Berlin", datetime(2024, 3, 31, 3, 0), "CEST"),
        ("Europe/Berlin", datetime(2024, 3, 31, 3, 0, 1), "CEST"),
        ("Europe/Berlin", datetime(2024, 3, 31, 4, 0), "CEST"),
        ("Europe/Berlin", datetime(2024, 10, 27, 0, 0), "CEST"),
        ("Europe/Berlin", datetime(2024, 10, 27, 1, 0), "CEST"),
        ("Europe/Berlin", datetime(2024, 10, 27, 2, 0), "CEST"),
        ("Europe/Berlin", datetime(2024, 10, 27, 2, 30), "CEST"),
        ("Europe/Berlin", datetime(2024, 10, 27, 2, 59, 59), "CEST"),
        ("Europe/Berlin", datetime(2024, 10, 27, 3, 0), "CET"),
        ("Europe/Berlin", datetime(2024, 10, 27, 3, 0, 1), "CET"),
        ("Europe/Berlin", datetime(2024, 10, 27, 4, 0), "CET"),
        # transition times from https://www.zeitverschiebung.net/de/timezone/america--new_york
        ("America/New_York", datetime(1970, 1, 1), "EST"),
        # Daylight Saving Time
        ("America/New_York", datetime(2024, 11, 3, 0, 0), "EDT"),
        ("America/New_York", datetime(2024, 11, 3, 1, 0), "EDT"),
        ("America/New_York", datetime(2024, 11, 3, 1, 59, 59), "EDT"),
        # 03.11.2024 2:00am -> 1:00am Standard
        # ("America/New_York", datetime(2024, 11, 3, 2, 0), "EDT"),
        ("America/New_York", datetime(2024, 11, 3, 2, 0, 1), "EST"),
        ("America/New_York", datetime(2024, 11, 3, 3, 0), "EST"),
        ("America/New_York", datetime(2025, 3, 9, 1, 0), "EST"),
        ("America/New_York", datetime(2025, 3, 9, 1, 59, 59), "EST"),
        ("America/New_York", datetime(2025, 3, 9, 2, 0), "EST"),
        # 09.03.2025 2:00am -> 3:00am Daylight Saving Time
        ("America/New_York", datetime(2025, 3, 9, 3, 0), "EDT"),
        ("America/New_York", datetime(2025, 3, 9, 3, 1, 1), "EDT"),
        ("America/New_York", datetime(2025, 3, 9, 4, 0), "EDT"),
    ],
)
def test_check_datetimes_around_transition_times(tzp, tzid, dt, tzname):
    """We should make sure than the datetimes with the generated timezones
    work as expected: They have the right UTC offset, dst and tzname.
    """
    message = f"{tzid}: {dt} (expected in {tzname})"
    expected_dt = tzp.localize(dt, tzid)
    component = Timezone.from_tzinfo(tzp.timezone(tzid))
    generated_tzinfo = component.to_tz(tzp, lookup_tzid=False)
    generated_dt = dt.replace(tzinfo=generated_tzinfo)
    print(generated_tzinfo)
    if tzp.uses_pytz():
        # generated_dt = generated_tzinfo.localize(dt)
        generated_dt = generated_tzinfo.normalize(generated_dt)
        if dt in (
            datetime(2024, 10, 27, 1, 0),
            datetime(2024, 11, 3, 1, 59, 59),
            datetime(2024, 11, 3, 1, 0),
            datetime(2024, 11, 3, 0, 0),
            datetime(2024, 10, 27, 2, 59, 59),
            datetime(2024, 10, 27, 2, 30),
            datetime(2024, 10, 27, 2, 0),
            datetime(2024, 10, 27, 1, 0),
        ):
            pytest.skip("We do not know how to do this. PYTZ-TODO")
    assert generated_dt.tzname() == expected_dt.tzname() == tzname, message
    assert generated_dt.dst() == expected_dt.dst(), message
    assert generated_dt.utcoffset() == expected_dt.utcoffset(), message


@pytest.mark.parametrize("uid", [0, 1, 2, 3])
def test_dateutil_timezone_when_time_is_going_backwards(calendars, tzp, uid):
    """When going from Daylight Saving Time to Standard Time, times can be ambiguous.
    For example, at 3:00 AM, the time falls back to 2:00 AM, repeating a full hour of times from 2:00 AM to 3:00 AM on the same date.

    By the RFC 5545, we cannot accommodate this case. All datetimes should
    be BEFORE the transition if ambiguous. However, dateutil can
    create a timezone that allows the event to be after this ambiguous time span, of course.

    Each event has its timezone saved in it.
    """
    cal: Calendar = calendars.issue_722_timezone_transition_ambiguity
    event: Event = cal.events[uid]
    expected_tzname = str(event["X-TZNAME"])
    actual_tzname = event.start.tzname()
    assert actual_tzname == expected_tzname, event["SUMMARY"]


def query_tzid(query: str, cal: Calendar) -> str:
    """The tzid from the query."""
    try:
        tzinfo = eval(query, {"cal": cal})  # noqa: S307
    except Exception as e:
        raise ValueError(query) from e
    return tzid_from_tzinfo(tzinfo)


# these are queries for all the places that have a TZID
# according to RFC 5545
queries = [
    "cal.events[0].start.tzinfo",  # DTSTART
    "cal.events[0].end.tzinfo",  # DTEND
    # EXDATE
    "cal.todos[0].end.tzinfo",  # DUE
    "cal.events[0].get('RDATE').dts[0].dt[0].tzinfo",  # RDATE
    "cal.events[1].get('RECURRENCE-ID').dt.tzinfo",  # RECURRENCE-ID
    "cal.events[2].get('RDATE')[0].dts[0].dt.tzinfo",  # RDATE multiple
    "cal.events[2].get('RDATE')[1].dts[0].dt.tzinfo",  # RDATE multiple
]


@pytest.mark.parametrize("query", queries)
def test_add_missing_timezones_to_example(calendars, query):
    """Add the missing timezones to the calendar."""
    cal: Calendar = calendars.issue_722_missing_timezones
    tzid = query_tzid(query, cal)
    tzs = cal.get_missing_tzids()
    assert tzid in tzs


def test_queries_yield_unique_tzids(calendars):
    """We make sure each query tests a unique place to find for the algorithm."""
    cal = calendars.issue_722_missing_timezones
    tzids = set()
    for query in queries:
        tzid = query_tzid(query, cal)
        print(query, "->", tzid)
        tzids.add(tzid)
    assert len(tzids) == len(queries)


def test_we_do_not_miss_to_add_a_query(calendars):
    """Make sure all tzids are actually queried."""
    cal = calendars.issue_722_missing_timezones
    raw = cal.raw_ics.decode()
    ids = set(findall("TZID=([a-zA-Z_/+-]+)", raw))
    assert cal.get_used_tzids() == ids, "We find all tzids and they are unique."
    assert len(ids) == len(queries), "We query all the tzids."


def test_unknown_tzid(calendars):
    """If we have an unknown tzid with no timezone component."""
    cal = calendars.issue_722_missing_VTIMEZONE_custom
    assert "CUSTOM_tzid" in cal.get_used_tzids()
    assert "CUSTOM_tzid" in cal.get_missing_tzids()


def test_custom_timezone_is_found_and_used(calendars):
    """Check the custom timezone component is not missing."""
    cal = calendars.america_new_york
    assert "custom_America/New_York" in cal.get_used_tzids()
    assert "custom_America/New_York" not in cal.get_missing_tzids()


def test_not_missing_anything():
    """Check that no timezone is missing."""
    cal = Calendar()
    assert cal.get_missing_tzids() == set()


def test_utc_is_not_missing(calendars):
    """UTC should not be found missing."""
    cal = calendars.issue_722_missing_timezones
    assert "UTC" not in cal.get_missing_tzids()
    assert "UTC" not in cal.get_used_tzids()


def test_dateutil_timezone_is_not_found_with_tzname(calendars, no_pytz):
    """dateutil is an example of a timezone that has no tzid.

    In this test we make sure that the timezone is said to be missing.
    """
    cal: Calendar = calendars.america_new_york
    cal.subcomponents.remove(cal.timezones[0])
    assert cal.get_missing_tzids() == {"custom_America/New_York"}
    assert "dateutil" in repr(cal.events[0].start.tzinfo.__class__)


@pytest.mark.parametrize("tzname", ["America/New_York", "Arctic/Longyearbyen"])
# @pytest.mark.parametrize("component", ["STANDARD", "DAYLIGHT"])
def test_dateutil_timezone_is_matched_with_tzname(tzname):
    """dateutil is an example of a timezone that has no tzid.

    In this test we make sure that the timezone is matched by its
    tzname() in the timezone in the STANDARD and DAYLIGHT components.
    """
    cal = Calendar()
    event = Event()
    event.start = datetime(2024, 11, 12, tzinfo=gettz(tzname))
    print(dir(event.start.tzinfo))
    cal.add_component(event)
    assert cal.get_missing_tzids() == {tzname}
    cal.add_missing_timezones()
    assert cal.get_missing_tzids() == set()


def test_dateutil_timezone_is_also_added(calendars):
    """We find and add a dateutil timezone.

    This is important as we use those in the zoneinfo implementation.
    """


@pytest.mark.parametrize(
    "calendar",
    [
        "example",
        "america_new_york",  # custom
        "timezone_same_start",  # known tzid
        "period_with_timezone",  # known tzid
    ],
)
def test_timezone_is_not_missing(calendars, calendar):
    """Check that these calendars have no timezone missing."""
    cal: Calendar = calendars[calendar]
    timezones = cal.timezones[:]
    assert set() == cal.get_missing_tzids()
    cal.add_missing_timezones()
    assert set() == cal.get_missing_tzids()
    assert cal.timezones == timezones


def test_add_missing_known_timezones(calendars):
    """Add all timezones specified."""
    cal: Calendar = deepcopy(
        calendars.issue_722_missing_timezones
    )  # avoid side effects
    assert len(cal.timezones) == 0
    cal.add_missing_timezones()
    assert len(cal.timezones) == len(queries), "all timezones are known"
    assert len(cal.get_missing_tzids()) == 0


def test_cannot_add_unknown_timezone(calendars):
    """I cannot add a timezone that is unknown."""
    cal: Calendar = calendars.issue_722_missing_VTIMEZONE_custom
    assert len(cal.timezones) == 0
    assert cal.get_missing_tzids() == {"CUSTOM_tzid"}
    cal.add_missing_timezones()
    assert cal.timezones == [], "we cannot add this timezone"
    assert cal.get_missing_tzids() == {"CUSTOM_tzid"}


def test_cannot_create_a_timezone_from_an_invalid_tzid():
    with pytest.raises(ValueError):
        Timezone.from_tzid("invalid/tzid")


def test_dates_before_and_after_are_considered():
    """When we add the timezones, we should check the calendar to see
    if all dates really occur in the span we use.

    We should also consider a huge default range.
    """
    pytest.skip("todo")


@pytest.mark.parametrize(
    "tzid", zoneinfo.available_timezones() - {"Factory", "localtime"}
)
def test_we_can_identify_dateutil_timezones(tzid):
    """dateutil and others were badly supported.

    But if we know their shortcodes, we should be able to identify them.
    """
    tz = gettz(tzid)
    assert tz is None or tzid in tzids_from_tzinfo(tz)

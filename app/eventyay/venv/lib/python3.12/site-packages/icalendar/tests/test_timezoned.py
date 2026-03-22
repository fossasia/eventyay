import datetime

import dateutil.parser

import icalendar
import icalendar.cal.calendar
import icalendar.cal.event
import icalendar.cal.timezone
from icalendar.timezone import tzid_from_dt


def test_create_from_ical(calendars, other_tzp):
    """Create a calendar from a .ics file."""
    cal = calendars.timezoned

    assert cal["prodid"].to_ical() == b"-//Plone.org//NONSGML plone.app.event//EN"

    timezones = cal.walk("VTIMEZONE")
    assert len(timezones) == 1

    tz = timezones[0]
    assert tz["tzid"].to_ical() == b"Europe/Vienna"

    std = tz.walk("STANDARD")[0]
    assert std.decoded("TZOFFSETFROM") == datetime.timedelta(0, 7200)

    ev1 = cal.walk("VEVENT")[0]
    assert ev1.decoded("DTSTART") == other_tzp.localize(
        datetime.datetime(2012, 2, 13, 10, 0, 0), "Europe/Vienna"
    )
    assert ev1.decoded("DTSTAMP") == other_tzp.localize(
        datetime.datetime(2010, 10, 10, 9, 10, 10), "UTC"
    )


def test_create_to_ical(tzp):
    cal = icalendar.cal.calendar.Calendar()

    cal.add("prodid", "-//Plone.org//NONSGML plone.app.event//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "test create calendar")
    cal.add("x-wr-caldesc", "icalendar tests")
    cal.add("x-wr-relcalid", "12345")
    cal.add("x-wr-timezone", "Europe/Vienna")

    tzc = icalendar.cal.timezone.Timezone()
    tzc.add("tzid", "Europe/Vienna")
    tzc.add("x-lic-location", "Europe/Vienna")

    tzs = icalendar.cal.timezone.TimezoneStandard()
    tzs.add("tzname", "CET")
    tzs.add("dtstart", datetime.datetime(1970, 10, 25, 3, 0, 0))
    tzs.add("rrule", {"freq": "yearly", "bymonth": 10, "byday": "-1su"})
    tzs.add("TZOFFSETFROM", datetime.timedelta(hours=2))
    tzs.add("TZOFFSETTO", datetime.timedelta(hours=1))

    tzd = icalendar.cal.timezone.TimezoneDaylight()
    tzd.add("tzname", "CEST")
    tzd.add("dtstart", datetime.datetime(1970, 3, 29, 2, 0, 0))
    tzs.add("rrule", {"freq": "yearly", "bymonth": 3, "byday": "-1su"})
    tzd.add("TZOFFSETFROM", datetime.timedelta(hours=1))
    tzd.add("TZOFFSETTO", datetime.timedelta(hours=2))

    tzc.add_component(tzs)
    tzc.add_component(tzd)
    cal.add_component(tzc)

    event = icalendar.cal.event.Event()
    event.add(
        "dtstart",
        tzp.localize(datetime.datetime(2012, 2, 13, 10, 00, 00), "Europe/Vienna"),
    )
    event.add(
        "dtend",
        tzp.localize(datetime.datetime(2012, 2, 17, 18, 00, 00), "Europe/Vienna"),
    )
    event.add(
        "dtstamp",
        tzp.localize(datetime.datetime(2010, 10, 10, 10, 10, 10), "Europe/Vienna"),
    )
    event.add(
        "created",
        tzp.localize(datetime.datetime(2010, 10, 10, 10, 10, 10), "Europe/Vienna"),
    )
    event.add("uid", "123456")
    event.add(
        "last-modified",
        tzp.localize(datetime.datetime(2010, 10, 10, 10, 10, 10), "Europe/Vienna"),
    )
    event.add("summary", "artsprint 2012")
    # event.add('rrule', 'FREQ=YEARLY;INTERVAL=1;COUNT=10')
    event.add("description", "sprinting at the artsprint")
    event.add("location", "aka bild, wien")
    event.add("categories", "first subject")
    event.add("categories", "second subject")
    event.add("attendee", "häns")
    event.add("attendee", "franz")
    event.add("attendee", "sepp")
    event.add("contact", "Max Mustermann, 1010 Wien")
    event.add("url", "https://plone.org")
    cal.add_component(event)

    test_out = b"|".join(cal.to_ical().splitlines())
    test_out = test_out.decode("utf-8")

    vtimezone_lines = "BEGIN:VTIMEZONE|TZID:Europe/Vienna|X-LIC-LOCATION:"
    "Europe/Vienna|BEGIN:STANDARD|DTSTART:19701025T03"
    "0000|RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=10|RRULE:FREQ=YEARLY;B"
    "YDAY=-1SU;BYMONTH=3|TZNAME:CET|TZOFFSETFROM:+0200|TZOFFSETTO:+01"
    "00|END:STANDARD|BEGIN:DAYLIGHT|DTSTART:19700329T"
    "020000|TZNAME:CEST|TZOFFSETFROM:+0100|TZOFFSETTO:+0200|END:DAYLI"
    "GHT|END:VTIMEZONE"
    assert vtimezone_lines in test_out

    test_str = "DTSTART;TZID=Europe/Vienna:20120213T100000"
    assert test_str in test_out
    assert "ATTENDEE:sepp" in test_out

    # ical standard expects DTSTAMP and CREATED in UTC
    assert "DTSTAMP:20101010T081010Z" in test_out
    assert "CREATED:20101010T081010Z" in test_out


def test_tzinfo_dateutil():
    """Test for issues #77, #63
    references: #73,7430b66862346fe3a6a100ab25e35a8711446717
    """
    date = dateutil.parser.parse("2012-08-30T22:41:00Z")
    date2 = dateutil.parser.parse("2012-08-30T22:41:00 +02:00")
    assert date.tzinfo.__module__.startswith("dateutil.tz")
    assert date2.tzinfo.__module__.startswith("dateutil.tz")

    # make sure, it's parsed properly and doesn't throw an error
    assert icalendar.vDDDTypes(date).to_ical() == b"20120830T224100Z"
    assert icalendar.vDDDTypes(date2).to_ical() == b"20120830T224100"


def test_create_america_new_york(calendars, tzp):
    """testing America/New_York, the most complex example from the RFC"""
    cal = calendars.america_new_york
    dt = cal.events[0].start
    assert tzid_from_dt(dt) in ("custom_America/New_York", "EDT")


def test_create_america_new_york_forward_reference(calendars, tzp):
    """testing America/New_York variant with VTIMEZONE as a forward reference"""
    cal = calendars.america_new_york_forward_reference
    dt = cal.walk("VEVENT")[0]["DTSTART"][0].dt
    assert tzid_from_dt(dt) in ("custom_America/New_York_Forward_reference", "EDT")


def test_america_new_york_with_pytz(calendars, tzp, pytz_only):
    """Create a custom timezone with pytz and test the transition times."""
    print(tzp)
    cal = calendars.america_new_york
    dt = cal.events[0].start
    tz = dt.tzinfo
    tz_new_york = tzp.timezone("America/New_York")
    # for reasons (tm) the locally installed version of the timezone
    # database isn't always complete, therefore we only compare some
    # transition times
    ny_transition_times = []
    ny_transition_info = []
    for num, date in enumerate(tz_new_york._utc_transition_times):
        if (
            datetime.datetime(1967, 4, 30, 7, 0)
            <= date
            <= datetime.datetime(2037, 11, 1, 6, 0)
        ):
            ny_transition_times.append(date)
            ny_transition_info.append(tz_new_york._transition_info[num])
    assert tz._utc_transition_times[:142] == ny_transition_times
    assert tz._transition_info[0:142] == ny_transition_info
    assert (
        datetime.timedelta(-1, 72000),
        datetime.timedelta(0, 3600),
        "EDT",
    ) in tz._tzinfos
    assert (
        datetime.timedelta(-1, 68400),
        datetime.timedelta(0),
        "EST",
    ) in tz._tzinfos


fiji_transition_times = [
    datetime.datetime(1915, 10, 25, 12, 4),
    datetime.datetime(1998, 10, 31, 14, 0),
    datetime.datetime(1999, 2, 27, 14, 0),
    datetime.datetime(1999, 11, 6, 14, 0),
    datetime.datetime(2000, 2, 26, 14, 0),
    datetime.datetime(2009, 11, 28, 14, 0),
    datetime.datetime(2010, 3, 27, 14, 0),
    datetime.datetime(2010, 10, 23, 14, 0),
    datetime.datetime(2011, 3, 5, 14, 0),
    datetime.datetime(2011, 10, 22, 14, 0),
    datetime.datetime(2012, 1, 21, 14, 0),
    datetime.datetime(2012, 10, 20, 14, 0),
    datetime.datetime(2013, 1, 19, 14, 0),
    datetime.datetime(2013, 10, 26, 14, 0),
    datetime.datetime(2014, 1, 18, 13, 0),
    datetime.datetime(2014, 10, 25, 14, 0),
    datetime.datetime(2015, 1, 17, 13, 0),
    datetime.datetime(2015, 10, 24, 14, 0),
    datetime.datetime(2016, 1, 23, 13, 0),
    datetime.datetime(2016, 10, 22, 14, 0),
    datetime.datetime(2017, 1, 21, 13, 0),
    datetime.datetime(2017, 10, 21, 14, 0),
    datetime.datetime(2018, 1, 20, 13, 0),
    datetime.datetime(2018, 10, 20, 14, 0),
    datetime.datetime(2019, 1, 19, 13, 0),
    datetime.datetime(2019, 10, 26, 14, 0),
    datetime.datetime(2020, 1, 18, 13, 0),
    datetime.datetime(2020, 10, 24, 14, 0),
    datetime.datetime(2021, 1, 23, 13, 0),
    datetime.datetime(2021, 10, 23, 14, 0),
    datetime.datetime(2022, 1, 22, 13, 0),
    datetime.datetime(2022, 10, 22, 14, 0),
    datetime.datetime(2023, 1, 21, 13, 0),
    datetime.datetime(2023, 10, 21, 14, 0),
    datetime.datetime(2024, 1, 20, 13, 0),
    datetime.datetime(2024, 10, 26, 14, 0),
    datetime.datetime(2025, 1, 18, 13, 0),
    datetime.datetime(2025, 10, 25, 14, 0),
    datetime.datetime(2026, 1, 17, 13, 0),
    datetime.datetime(2026, 10, 24, 14, 0),
    datetime.datetime(2027, 1, 23, 13, 0),
    datetime.datetime(2027, 10, 23, 14, 0),
    datetime.datetime(2028, 1, 22, 13, 0),
    datetime.datetime(2028, 10, 21, 14, 0),
    datetime.datetime(2029, 1, 20, 13, 0),
    datetime.datetime(2029, 10, 20, 14, 0),
    datetime.datetime(2030, 1, 19, 13, 0),
    datetime.datetime(2030, 10, 26, 14, 0),
    datetime.datetime(2031, 1, 18, 13, 0),
    datetime.datetime(2031, 10, 25, 14, 0),
    datetime.datetime(2032, 1, 17, 13, 0),
    datetime.datetime(2032, 10, 23, 14, 0),
    datetime.datetime(2033, 1, 22, 13, 0),
    datetime.datetime(2033, 10, 22, 14, 0),
    datetime.datetime(2034, 1, 21, 13, 0),
    datetime.datetime(2034, 10, 21, 14, 0),
    datetime.datetime(2035, 1, 20, 13, 0),
    datetime.datetime(2035, 10, 20, 14, 0),
    datetime.datetime(2036, 1, 19, 13, 0),
    datetime.datetime(2036, 10, 25, 14, 0),
    datetime.datetime(2037, 1, 17, 13, 0),
    datetime.datetime(2037, 10, 24, 14, 0),
    datetime.datetime(2038, 1, 23, 13, 0),
    datetime.datetime(2038, 10, 23, 14, 0),
]

fiji_transition_info = (
    [
        (
            datetime.timedelta(0, 43200),
            datetime.timedelta(0),
            "custom_Pacific/Fiji_19151026T000000_+115544_+1200",
        )
    ]
    + 3
    * [
        (
            datetime.timedelta(0, 46800),
            datetime.timedelta(0, 3600),
            "custom_Pacific/Fiji_19981101T020000_+1200_+1300",
        ),
        (
            datetime.timedelta(0, 43200),
            datetime.timedelta(0),
            "custom_Pacific/Fiji_19990228T030000_+1300_+1200",
        ),
    ]
    + 3
    * [
        (
            datetime.timedelta(0, 46800),
            datetime.timedelta(0, 3600),
            "custom_Pacific/Fiji_20101024T020000_+1200_+1300",
        ),
        (
            datetime.timedelta(0, 43200),
            datetime.timedelta(0),
            "custom_Pacific/Fiji_19990228T030000_+1300_+1200",
        ),
    ]
    + 25
    * [
        (
            datetime.timedelta(0, 46800),
            datetime.timedelta(0, 3600),
            "custom_Pacific/Fiji_20101024T020000_+1200_+1300",
        ),
        (
            datetime.timedelta(0, 43200),
            datetime.timedelta(0),
            "custom_Pacific/Fiji_20140119T020000_+1300_+1200",
        ),
    ]
    + [
        (
            datetime.timedelta(0, 46800),
            datetime.timedelta(0, 3600),
            "custom_Pacific/Fiji_20101024T020000_+1200_+1300",
        )
    ]
)


def test_create_pacific_fiji(calendars, pytz_only):
    """testing Pacific/Fiji, another pretty complex example with more than
    one RDATE property per subcomponent"""
    cal = calendars.pacific_fiji

    tz = cal.walk("VEVENT")[0]["DTSTART"][0].dt.tzinfo
    assert str(tz) == "custom_Pacific/Fiji"
    assert tz._utc_transition_times == fiji_transition_times
    assert tz._transition_info == fiji_transition_info
    assert (
        datetime.timedelta(0, 46800),
        datetime.timedelta(0, 3600),
        "custom_Pacific/Fiji_19981101T020000_+1200_+1300",
    ) in tz._tzinfos
    assert (
        datetime.timedelta(0, 43200),
        datetime.timedelta(0),
        "custom_Pacific/Fiji_19990228T030000_+1300_+1200",
    ) in tz._tzinfos


# these are the expected offsets before and after the fiji_transition_times
fiji_expected_offsets = [
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
    (datetime.timedelta(hours=13), datetime.timedelta(hours=13)),
    (datetime.timedelta(hours=12), datetime.timedelta(hours=12)),
]


def test_transition_times_fiji(tzp, timezones):
    """The transition times are computed."""
    tz = timezones.pacific_fiji.to_tz(tzp, lookup_tzid=False)
    offsets = []  # [(before, after), ...]
    for _i, transition_time in enumerate(fiji_transition_times):
        before_after_offset = []
        for offset in (datetime.timedelta(hours=-1), datetime.timedelta(hours=+1)):
            time_in_timezone = tzp.localize(transition_time + offset, tz)
            utc_offset = time_in_timezone.utcoffset()
            before_after_offset.append(utc_offset)
        offsets.append(tuple(before_after_offset))
    assert offsets == fiji_expected_offsets


def test_same_start_date(calendars):
    """testing if we can handle VTIMEZONEs whose different components
    have the same start DTIMEs."""
    cal = calendars.timezone_same_start
    d = cal.subcomponents[1]["DTSTART"].dt
    assert d.strftime("%c") == "Fri Feb 24 12:00:00 2017"


def test_same_start_date_and_offset(calendars):
    """testing if we can handle VTIMEZONEs whose different components
    have the same DTSTARTs, TZOFFSETFROM, and TZOFFSETTO."""
    cal = calendars.timezone_same_start_and_offset
    d = cal.subcomponents[1]["DTSTART"].dt
    assert d.strftime("%c") == "Fri Feb 24 12:00:00 2017"


def test_rdate(calendars):
    """testing if we can handle VTIMEZONEs who only have an RDATE, not RRULE"""
    cal = calendars.timezone_rdate
    vevent = cal.walk("VEVENT")[0]
    assert tzid_from_dt(vevent["DTSTART"].dt) in ("posix/Europe/Vaduz", "CET")


def test_rdate_pytz(calendars, pytz_only):
    """testing if we can handle VTIMEZONEs who only have an RDATE, not RRULE"""
    cal = calendars.timezone_rdate
    vevent = cal.walk("VEVENT")[0]
    tz = vevent["DTSTART"].dt.tzinfo
    assert tz._utc_transition_times[:6] == [
        datetime.datetime(1901, 12, 13, 20, 45, 38),
        datetime.datetime(1941, 5, 5, 0, 0, 0),
        datetime.datetime(1941, 10, 6, 0, 0, 0),
        datetime.datetime(1942, 5, 4, 0, 0, 0),
        datetime.datetime(1942, 10, 5, 0, 0, 0),
        datetime.datetime(1981, 3, 29, 1, 0),
    ]
    assert tz._transition_info[:6] == [
        (datetime.timedelta(0, 3600), datetime.timedelta(0), "CET"),
        (datetime.timedelta(0, 7200), datetime.timedelta(0, 3600), "CEST"),
        (datetime.timedelta(0, 3600), datetime.timedelta(0), "CET"),
        (datetime.timedelta(0, 7200), datetime.timedelta(0, 3600), "CEST"),
        (datetime.timedelta(0, 3600), datetime.timedelta(0), "CET"),
        (datetime.timedelta(0, 7200), datetime.timedelta(0, 3600), "CEST"),
    ]

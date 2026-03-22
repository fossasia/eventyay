from datetime import date, datetime

import pytest

from icalendar.cal.event import Event


def test_recurrence_properly_parsed(events):
    assert events.event_with_recurrence["rrule"] == {"COUNT": [100], "FREQ": ["DAILY"]}


@pytest.mark.parametrize(
    ("i", "exception_date"),
    [
        (0, datetime(1996, 4, 2, 1, 0)),
        (1, datetime(1996, 4, 3, 1, 0)),
        (2, datetime(1996, 4, 4, 1, 0)),
    ],
)
def test_exdate_properly_parsed(events, i, exception_date, in_timezone):
    assert events.event_with_recurrence["exdate"].dts[i].dt == in_timezone(
        exception_date, "UTC"
    )


def test_exdate_properly_marshalled(events):
    actual = events.event_with_recurrence["exdate"].to_ical()
    assert actual == b"19960402T010000Z,19960403T010000Z,19960404T010000Z"


# TODO: DOCUMENT BETTER!
# In this case we have multiple EXDATE definitions, one per line.
# Icalendar makes a list out of this instead of zipping it into one
# vDDDLists object. Actually, this feels correct for me, as it also
# allows to define different timezones per exdate line - but client
# code has to handle this as list and not blindly expecting to be able
# to call event['EXDATE'].to_ical() on it:
def test_exdate_formed_from_exdates_on_multiple_lines_is_a_list(events):
    exdate = events.event_with_recurrence_exdates_on_different_lines["exdate"]
    assert isinstance(exdate, list)


@pytest.mark.parametrize(
    ("i", "exception_date", "exception_date_ics"),
    [
        (0, datetime(2012, 5, 29, 10, 0), b"20120529T100000"),
        (1, datetime(2012, 4, 3, 10, 0), b"20120403T100000"),
        (2, datetime(2012, 4, 10, 10, 0), b"20120410T100000"),
        (3, datetime(2012, 5, 1, 10, 0), b"20120501T100000"),
        (4, datetime(2012, 4, 17, 10, 0), b"20120417T100000"),
    ],
)
def test_list_exdate_to_ical_is_inverse_of_from_ical(
    events, i, exception_date, exception_date_ics, in_timezone
):
    exdate = events.event_with_recurrence_exdates_on_different_lines["exdate"]
    assert exdate[i].dts[0].dt == in_timezone(exception_date, "Europe/Vienna")
    assert exdate[i].to_ical() == exception_date_ics


@pytest.mark.parametrize(
    ("freq", "byday", "dtstart", "expected"),
    [
        # Test some YEARLY BYDAY repeats
        (
            "YEARLY",
            "1SU",
            date(2016, 1, 3),  # 1st Sunday in year
            b"BEGIN:VEVENT\r\nSUMMARY:Event YEARLY 1SU\r\nDTSTART;VALUE=DATE:20160103\r\nRRULE:FREQ=YEARLY;BYDAY=1SU\r\nEND:VEVENT\r\n",
        ),
        (
            "YEARLY",
            "53MO",
            date(1984, 12, 31),  # 53rd Monday in (leap) year
            b"BEGIN:VEVENT\r\nSUMMARY:Event YEARLY 53MO\r\nDTSTART;VALUE=DATE:19841231\r\nRRULE:FREQ=YEARLY;BYDAY=53MO\r\nEND:VEVENT\r\n",
        ),
        (
            "YEARLY",
            "-1TU",
            date(1999, 12, 28),  # Last Tuesday in year
            b"BEGIN:VEVENT\r\nSUMMARY:Event YEARLY -1TU\r\nDTSTART;VALUE=DATE:19991228\r\nRRULE:FREQ=YEARLY;BYDAY=-1TU\r\nEND:VEVENT\r\n",
        ),
        (
            "YEARLY",
            "-17WE",
            date(2000, 9, 6),  # 17th-to-last Wednesday in year
            b"BEGIN:VEVENT\r\nSUMMARY:Event YEARLY -17WE\r\nDTSTART;VALUE=DATE:20000906\r\nRRULE:FREQ=YEARLY;BYDAY=-17WE\r\nEND:VEVENT\r\n",
        ),
        # Test some MONTHLY BYDAY repeats
        (
            "MONTHLY",
            "2TH",
            date(2003, 4, 10),  # 2nd Thursday in month
            b"BEGIN:VEVENT\r\nSUMMARY:Event MONTHLY 2TH\r\nDTSTART;VALUE=DATE:20030410\r\nRRULE:FREQ=MONTHLY;BYDAY=2TH\r\nEND:VEVENT\r\n",
        ),
        (
            "MONTHLY",
            "-3FR",
            date(2017, 5, 12),  # 3rd-to-last Friday in month
            b"BEGIN:VEVENT\r\nSUMMARY:Event MONTHLY -3FR\r\nDTSTART;VALUE=DATE:20170512\r\nRRULE:FREQ=MONTHLY;BYDAY=-3FR\r\nEND:VEVENT\r\n",
        ),
        (
            "MONTHLY",
            "-5SA",
            date(2053, 11, 1),  # 5th-to-last Saturday in month
            b"BEGIN:VEVENT\r\nSUMMARY:Event MONTHLY -5SA\r\nDTSTART;VALUE=DATE:20531101\r\nRRULE:FREQ=MONTHLY;BYDAY=-5SA\r\nEND:VEVENT\r\n",
        ),
        # Specifically test examples from the report of Issue #518
        # https://github.com/collective/icalendar/issues/518
        (
            "YEARLY",
            "9MO",
            date(2023, 2, 27),  # 9th Monday in year
            b"BEGIN:VEVENT\r\nSUMMARY:Event YEARLY 9MO\r\nDTSTART;VALUE=DATE:20230227\r\nRRULE:FREQ=YEARLY;BYDAY=9MO\r\nEND:VEVENT\r\n",
        ),
        (
            "YEARLY",
            "10MO",
            date(2023, 3, 6),  # 10th Monday in year
            b"BEGIN:VEVENT\r\nSUMMARY:Event YEARLY 10MO\r\nDTSTART;VALUE=DATE:20230306\r\nRRULE:FREQ=YEARLY;BYDAY=10MO\r\nEND:VEVENT\r\n",
        ),
    ],
)
def test_byday_to_ical(freq, byday, dtstart, expected):
    """Test the BYDAY rule is correctly processed by to_ical()."""
    event = Event()
    event.add("SUMMARY", f"Event {freq} {byday}")
    event.add("DTSTART", dtstart)
    event.add("RRULE", {"FREQ": [freq], "BYDAY": byday})
    assert event.to_ical() == expected

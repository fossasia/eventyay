"""These tests make sure that we have some coverage on the usage of the PERIOD value type.

See
- https://github.com/collective/icalendar/issues/156
- https://github.com/pimutils/khal/issues/152#issuecomment-933635248
"""

import datetime

import pytest

from icalendar.prop import vDDDTypes, vPeriod


@pytest.mark.parametrize(
    ("calname", "tzname", "index", "period_string"),
    [
        (
            "issue_156_RDATE_with_PERIOD_TZID_khal_2",
            "Europe/Berlin",
            0,
            "20211101T160000/20211101T163000",
        ),
        (
            "issue_156_RDATE_with_PERIOD_TZID_khal_2",
            "Europe/Berlin",
            1,
            "20211206T160000/20211206T163000",
        ),
        (
            "issue_156_RDATE_with_PERIOD_TZID_khal_2",
            "Europe/Berlin",
            2,
            "20220103T160000/20220103T163000",
        ),
        (
            "issue_156_RDATE_with_PERIOD_TZID_khal_2",
            "Europe/Berlin",
            3,
            "20220207T160000/20220207T163000",
        ),
    ]
    + [
        ("issue_156_RDATE_with_PERIOD_TZID_khal", "America/Chicago", i, period)
        for i, period in enumerate(
            [
                "20180327T080000/20180327T090000",
                "20180403T080000/20180403T090000",
                "20180410T080000/20180410T090000",
                "20180417T080000/20180417T090000",
                "20180424T080000/20180424T090000",
                "20180501T080000/20180501T090000",
                "20180508T080000/20180508T090000",
                "20180515T080000/20180515T090000",
                "20180522T080000/20180522T090000",
                "20180529T080000/20180529T090000",
                "20180605T080000/20180605T090000",
                "20180612T080000/20180612T090000",
                "20180619T080000/20180619T090000",
                "20180626T080000/20180626T090000",
                "20180703T080000/20180703T090000",
                "20180710T080000/20180710T090000",
                "20180717T080000/20180717T090000",
                "20180724T080000/20180724T090000",
                "20180731T080000/20180731T090000",
            ]
        )
    ],
)
def test_issue_156_period_list_in_rdate(
    calendars, calname, tzname, index, period_string
):
    """Check items in a list of period values."""
    calendar = calendars[calname]
    rdate = calendar.walk("vevent")[0]["rdate"]
    period = rdate.dts[index]
    assert period.dt == vDDDTypes.from_ical(period_string, timezone=tzname)


def test_duration_properly_parsed(events):
    """This checks the duration PT5H30M."""
    start = vDDDTypes.from_ical("19970109T180000Z")
    duration = vDDDTypes.from_ical("PT5H30M")
    rdate = events.issue_156_RDATE_with_PERIOD_list["RDATE"]
    print(rdate)
    period = rdate.dts[1].dt
    print(dir(duration))
    assert period[0] == start
    assert period[1].days == 0
    assert period[1].seconds == (5 * 60 + 30) * 60
    assert period[1] == duration


def test_tzid_is_part_of_the_parameters(calendars):
    """The TZID should be mentioned in the parameters."""
    event = list(calendars.period_with_timezone.walk("VEVENT"))[0]
    assert event["RDATE"].params["TZID"] == "America/Vancouver"


def test_tzid_is_part_of_the_period_values(calendars, tzp):
    """The TZID should be set in the datetime."""
    event = list(calendars.period_with_timezone.walk("VEVENT"))[0]
    start, end = event["RDATE"].dts[0].dt
    assert start == tzp.localize(
        datetime.datetime(2023, 12, 13, 12), "America/Vancouver"
    )
    assert end == tzp.localize(datetime.datetime(2023, 12, 13, 15), "America/Vancouver")


def test_period_overlaps():
    # 30 minute increments
    datetime_1 = datetime.datetime(2024, 11, 20, 12, 0)  # 12:00
    datetime_2 = datetime.datetime(2024, 11, 20, 12, 30)  # 12:30
    datetime_3 = datetime.datetime(2024, 11, 20, 13, 0)  # 13:00

    period_1 = vPeriod((datetime_1, datetime_2))
    period_2 = vPeriod((datetime_1, datetime_3))
    period_3 = vPeriod((datetime_2, datetime_3))

    assert period_1.overlaps(period_2)
    assert period_3.overlaps(period_2)
    assert not period_1.overlaps(period_3)

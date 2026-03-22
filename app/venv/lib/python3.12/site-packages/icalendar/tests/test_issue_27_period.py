"""Issue #27 - multiple periods

https://github.com/collective/icalendar/issues/27
"""


def test_issue_27_multiple_periods(calendars):
    free_busy = list(
        calendars.issue_27_multiple_periods_in_freebusy_multiple_freebusies.walk(
            "VFREEBUSY"
        )
    )[0]
    free_busy_period = free_busy["freebusy"]
    print(free_busy["freebusy"])
    equivalent_way_of_defining_free_busy = list(
        calendars.issue_27_multiple_periods_in_freebusy_one_freebusy.walk("VFREEBUSY")
    )[0]
    free_busy_period_equivalent = equivalent_way_of_defining_free_busy["freebusy"]
    assert free_busy_period == free_busy_period_equivalent

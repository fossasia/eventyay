"""These are tests for Issue #348

see https://github.com/collective/icalendar/issues/348
"""


def test_calendar_can_be_parsed_correctly(calendars):
    """Exception when there's no ':' when parsing value #348

    see https://github.com/collective/icalendar/issues/348
    """
    freebusy = calendars.issue_348_exception_parsing_value.walk("VFREEBUSY")[0]
    assert freebusy["ORGANIZER"].params["CN"] == "Sixt SE"


def test_parameters_are_not_truncated(calendars):
    """We skip to the end and we do not want to loose parameters.

    see https://github.com/collective/icalendar/pull/514#issuecomment-1505878801
    """
    freebusy = calendars.issue_348_exception_parsing_value.walk("VFREEBUSY")[0]
    assert freebusy["X-ORGANIZER2"].params["CN"] == "Sixt SE"
    assert freebusy["X-ORGANIZER2"].params["CN2"] == "Test!"

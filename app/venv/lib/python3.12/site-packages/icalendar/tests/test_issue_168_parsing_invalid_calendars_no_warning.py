"""Issue #168 - Parsing invalid icalendars fails without any warning

https://github.com/collective/icalendar/issues/168
"""


def test_issue_168_parsing_inavlid_calendars_no_warning(calendars):
    expected_error = (
        None,
        "Content line could not be parsed into parts: 'X-APPLE-RADIUS=49.91307046514149': X-APPLE-RADIUS=49.91307046514149",
    )
    assert expected_error in calendars.issue_168_input.walk("VEVENT")[0].errors
    assert (
        calendars.issue_168_input.to_ical()
        == calendars.issue_168_expected_output.raw_ics
    )

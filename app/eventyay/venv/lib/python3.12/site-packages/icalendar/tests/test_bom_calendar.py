def test_bom_calendar(calendars):
    assert calendars.bom_calendar.walk("VCALENDAR"), (
        "Unable to parse a calendar starting with an Unicode BOM"
    )

"""Issue #350 - Ignore X-... properties also at end of file?

https://github.com/collective/icalendar/issues/350
"""


def test_issue_350(calendars):
    calendar = list(calendars.issue_350.walk("X-COMMENT"))
    assert len(calendar) == 0, "X-COMMENT at the end of the file was parsed"

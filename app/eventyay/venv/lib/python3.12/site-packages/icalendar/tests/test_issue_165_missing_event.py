"""Issue #165 - Problem parsing a file with event recurring on weekdays

https://github.com/collective/icalendar/issues/165
"""


def test_issue_165_missing_event(calendars):
    events = list(calendars.issue_165_missing_event.walk("VEVENT"))
    assert len(events) == 1, "There was an event missing from the parsed events' list."

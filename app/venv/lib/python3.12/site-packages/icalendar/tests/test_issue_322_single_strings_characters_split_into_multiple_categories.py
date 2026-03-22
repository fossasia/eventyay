"""

See https://github.com/collective/icalendar/issues/322
"""

from icalendar.cal.calendar import Calendar
from icalendar.cal.event import Event


def test_issue_322_single_string_split_into_multiple_categories(calendars):
    calendar = Calendar()
    event = Event()
    event.add("summary", "Event with bare string as argument for categories")
    event.add("categories", "Lecture")
    calendar.add_component(event)
    assert calendar.to_ical() == calendars.issue_322_expected_calendar.raw_ics

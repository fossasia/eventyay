"""Test for issue #898 - TODO.end should equal TODO.start when no DURATION/DUE.

For Events with only DTSTART:
- date: end = start + 1 day
- datetime: end = start

For Todos with only DTSTART:
- date: end = start (NOT start + 1 day)
- datetime: end = start

See https://github.com/collective/icalendar/issues/898
"""

from datetime import date, datetime

from icalendar import Event, Todo


class TestIssue898TodoEnd:
    """Test TODO.end behavior when only DTSTART is provided."""

    def test_event_with_date_dtstart_only(self):
        """Event with date DTSTART should have end = start + 1 day."""
        event = Event()
        event.add("UID", "test-event-date")
        event.add("DTSTART", date(2026, 1, 1))

        assert event.end == date(2026, 1, 2)

    def test_event_with_datetime_dtstart_only(self):
        """Event with datetime DTSTART should have end = start."""
        event = Event()
        event.add("UID", "test-event-datetime")
        event.add("DTSTART", datetime(2026, 1, 1, 12, 0))

        assert event.end == datetime(2026, 1, 1, 12, 0)

    def test_todo_with_date_dtstart_only(self):
        """Todo with date DTSTART should have end = start (NOT start + 1 day).

        The RFC doesn't specify this behavior explicitly.
        Returning None is another option, but returning start works best.
        """
        todo = Todo()
        todo.add("UID", "test-todo-date")
        todo.add("DTSTART", date(2026, 1, 1))

        # This should be start, not start + 1 day
        assert todo.end == date(2026, 1, 1)

    def test_todo_with_datetime_dtstart_only(self):
        """Todo with datetime DTSTART should have end = start."""
        todo = Todo()
        todo.add("UID", "test-todo-datetime")
        todo.add("DTSTART", datetime(2026, 1, 1, 12, 0))

        assert todo.end == datetime(2026, 1, 1, 12, 0)

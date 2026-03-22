"""Tests for consolidated attribute functions in icalendar.attr module."""

from datetime import date, datetime, timedelta

import pytest

from icalendar import Event, Todo
from icalendar.attr import (
    get_duration_property,
    get_end_property,
    get_start_end_duration_with_validation,
    get_start_property,
    set_duration_with_locking,
    set_end_with_locking,
    set_start_with_locking,
)
from icalendar.error import IncompleteComponent, InvalidCalendar


class TestConsolidatedSetters:
    """Test consolidated setter functions from icalendar.attr."""

    def test_set_start_with_locking_event(self) -> None:
        """Test set_start_with_locking for Event components."""
        event = Event()
        event.add("UID", "test-event")
        event.add("DTSTART", datetime(2026, 1, 1, 12, 0))
        event.add("DTEND", datetime(2026, 1, 1, 14, 0))

        # Keep end locked
        set_start_with_locking(event, datetime(2026, 1, 1, 10, 0), "end", "DTEND")

        assert event.start == datetime(2026, 1, 1, 10, 0)
        assert event.end == datetime(2026, 1, 1, 14, 0)
        assert event.duration == timedelta(hours=4)

    def test_set_start_with_locking_todo(self) -> None:
        """Test set_start_with_locking for Todo components."""
        todo = Todo()
        todo.add("UID", "test-todo")
        todo.add("DTSTART", datetime(2026, 1, 1, 12, 0))
        todo.add("DUE", datetime(2026, 1, 1, 14, 0))

        # Keep end locked
        set_start_with_locking(todo, datetime(2026, 1, 1, 10, 0), "end", "DUE")

        assert todo.start == datetime(2026, 1, 1, 10, 0)
        assert todo.end == datetime(2026, 1, 1, 14, 0)
        assert todo.duration == timedelta(hours=4)

    def test_set_end_with_locking_event(self) -> None:
        """Test set_end_with_locking for Event components."""
        event = Event()
        event.add("UID", "test-event")
        event.add("DTSTART", datetime(2026, 1, 1, 12, 0))
        event.add("DTEND", datetime(2026, 1, 1, 14, 0))

        # Keep start locked
        set_end_with_locking(event, datetime(2026, 1, 1, 16, 0), "start", "DTEND")

        assert event.start == datetime(2026, 1, 1, 12, 0)
        assert event.end == datetime(2026, 1, 1, 16, 0)
        assert event.duration == timedelta(hours=4)

    def test_set_end_with_locking_todo(self) -> None:
        """Test set_end_with_locking for Todo components."""
        todo = Todo()
        todo.add("UID", "test-todo")
        todo.add("DTSTART", datetime(2026, 1, 1, 12, 0))
        todo.add("DUE", datetime(2026, 1, 1, 14, 0))

        # Keep start locked
        set_end_with_locking(todo, datetime(2026, 1, 1, 16, 0), "start", "DUE")

        assert todo.start == datetime(2026, 1, 1, 12, 0)
        assert todo.end == datetime(2026, 1, 1, 16, 0)
        assert todo.duration == timedelta(hours=4)

    def test_set_duration_with_locking_event(self) -> None:
        """Test set_duration_with_locking for Event components."""
        event = Event()
        event.add("UID", "test-event")
        event.add("DTSTART", datetime(2026, 1, 1, 12, 0))
        event.add("DTEND", datetime(2026, 1, 1, 14, 0))

        # Set duration with start locked
        set_duration_with_locking(event, timedelta(hours=3), "start", "DTEND")

        assert event.start == datetime(2026, 1, 1, 12, 0)
        assert event.end == datetime(2026, 1, 1, 15, 0)
        assert event.duration == timedelta(hours=3)

    def test_set_duration_with_locking_todo(self) -> None:
        """Test set_duration_with_locking for Todo components."""
        todo = Todo()
        todo.add("UID", "test-todo")
        todo.add("DTSTART", datetime(2026, 1, 1, 12, 0))
        todo.add("DUE", datetime(2026, 1, 1, 14, 0))

        # Set duration with start locked
        set_duration_with_locking(todo, timedelta(hours=3), "start", "DUE")

        assert todo.start == datetime(2026, 1, 1, 12, 0)
        assert todo.end == datetime(2026, 1, 1, 15, 0)
        assert todo.duration == timedelta(hours=3)

    def test_auto_detect_property_locking(self) -> None:
        """Test auto-detection of property locking."""
        event = Event()
        event.add("UID", "test-event")
        event.add("DTSTART", datetime(2026, 1, 1, 12, 0))
        event.add("DURATION", timedelta(hours=2))

        # Auto-detect should choose duration
        set_start_with_locking(
            event,
            datetime(2026, 1, 1, 10, 0),
            None,
            "DTEND",
        )

        assert event.start == datetime(2026, 1, 1, 10, 0)
        assert event.duration == timedelta(hours=2)
        assert event.end == datetime(2026, 1, 1, 12, 0)

    def test_error_handling_consolidated_functions(self) -> None:
        """Test error handling in consolidated functions."""
        event = Event()
        event.add("UID", "test-event")

        # Invalid locked parameter
        with pytest.raises(ValueError, match="locked must be"):
            set_start_with_locking(
                event,
                datetime(2026, 1, 1, 12, 0),
                "invalid",
                "DTEND",
            )

        with pytest.raises(ValueError, match="locked must be"):
            set_end_with_locking(
                event,
                datetime(2026, 1, 1, 12, 0),
                "invalid",
                "DTEND",
            )

        with pytest.raises(ValueError, match="locked must be"):
            set_duration_with_locking(
                event,
                timedelta(hours=1),
                "invalid",
                "DTEND",
            )

    def test_consolidated_functions_maintain_identical_behavior(self) -> None:
        """Test that consolidated functions maintain identical behavior."""
        # Create identical events
        event1 = Event()
        event1.add("UID", "test-event-1")
        event1.add("DTSTART", datetime(2026, 1, 1, 12, 0))
        event1.add("DTEND", datetime(2026, 1, 1, 14, 0))

        event2 = Event()
        event2.add("UID", "test-event-2")
        event2.add("DTSTART", datetime(2026, 1, 1, 12, 0))
        event2.add("DTEND", datetime(2026, 1, 1, 14, 0))

        # Use consolidated function vs direct property
        set_start_with_locking(
            event1,
            datetime(2026, 1, 1, 10, 0),
            "end",
            "DTEND",
        )
        event2.set_start(datetime(2026, 1, 1, 10, 0), locked="end")

        # Results should be identical
        assert event1.start == event2.start
        assert event1.end == event2.end
        assert event1.duration == event2.duration


class TestConsolidatedPropertyGetters:
    """Test consolidated property getter functions."""

    def test_get_duration_property_with_duration_set(self) -> None:
        """Test get_duration_property when DURATION is explicitly set."""
        event = Event()
        event.add("UID", "test-duration")
        event.add("DTSTART", datetime(2026, 1, 1, 12, 0))
        event.add("DURATION", timedelta(hours=1))

        duration = get_duration_property(event)
        assert duration == timedelta(hours=1)

    def test_get_duration_property_calculated(self) -> None:
        """Test get_duration_property when calculated from start/end."""
        event = Event()
        event.add("UID", "test-calculated")
        event.add("DTSTART", datetime(2026, 1, 1, 12, 0))
        event.add("DTEND", datetime(2026, 1, 1, 15, 0))

        duration = get_duration_property(event)
        assert duration == timedelta(hours=3)

    def test_get_start_property_success(self) -> None:
        """Test get_start_property success case."""
        event = Event()
        event.add("UID", "test-start")
        event.add("DTSTART", datetime(2026, 1, 1, 12, 0))

        start = get_start_property(event)
        assert start == datetime(2026, 1, 1, 12, 0)

    def test_get_start_property_missing(self) -> None:
        """Test get_start_property when DTSTART is missing."""
        event = Event()
        event.add("UID", "test-start")

        with pytest.raises(IncompleteComponent, match="No DTSTART given"):
            get_start_property(event)

    def test_get_end_property_with_dtend(self) -> None:
        """Test get_end_property when DTEND is set."""
        event = Event()
        event.add("UID", "test-end")
        event.add("DTSTART", datetime(2026, 1, 1, 12, 0))
        event.add("DTEND", datetime(2026, 1, 1, 15, 0))

        end = get_end_property(event, "DTEND")
        assert end == datetime(2026, 1, 1, 15, 0)

    def test_get_end_property_with_duration(self) -> None:
        """Test get_end_property when DURATION is set."""
        event = Event()
        event.add("UID", "test-duration-end")
        event.add("DTSTART", datetime(2026, 1, 1, 12, 0))
        event.add("DURATION", timedelta(hours=3))

        end = get_end_property(event, "DTEND")
        assert end == datetime(2026, 1, 1, 15, 0)

    def test_get_end_property_default_behavior(self) -> None:
        """Test get_end_property default behavior."""
        event = Event()
        event.add("UID", "test-default")
        event.add("DTSTART", date(2026, 1, 1))

        end = get_end_property(event, "DTEND")
        assert end == date(2026, 1, 2)

        event2 = Event()
        event2.add("UID", "test-default-2")
        event2.add("DTSTART", datetime(2026, 1, 1, 12, 0))

        end2 = get_end_property(event2, "DTEND")
        assert end2 == datetime(2026, 1, 1, 12, 0)

    def test_get_start_end_duration_validation_success(self) -> None:
        """Test get_start_end_duration_with_validation success case."""
        event = Event()
        event.add("UID", "test-validation")
        event.add("DTSTART", datetime(2026, 1, 1, 12, 0))
        event.add("DTEND", datetime(2026, 1, 1, 15, 0))

        start, end, duration = get_start_end_duration_with_validation(
            event,
            "DTSTART",
            "DTEND",
            "VEVENT",
        )
        assert start == datetime(2026, 1, 1, 12, 0)
        assert end == datetime(2026, 1, 1, 15, 0)
        assert duration is None

    def test_get_start_end_duration_validation_errors(self) -> None:
        """Test get_start_end_duration_with_validation error cases."""
        # Test both DTEND and DURATION
        event = Event()
        event.add("UID", "test-both")
        event.add("DTSTART", datetime(2026, 1, 1, 12, 0))
        event.add("DTEND", datetime(2026, 1, 1, 15, 0))
        event.add("DURATION", timedelta(hours=2))

        with pytest.raises(InvalidCalendar, match="Only one of DTEND and DURATION"):
            get_start_end_duration_with_validation(
                event,
                "DTSTART",
                "DTEND",
                "VEVENT",
            )

        # Test invalid duration for date DTSTART
        event2 = Event()
        event2.add("UID", "test-date-duration")
        event2.add("DTSTART", date(2026, 1, 1))
        event2.add("DURATION", timedelta(hours=2))

        with pytest.raises(InvalidCalendar, match="DURATION must be of days"):
            get_start_end_duration_with_validation(
                event2,
                "DTSTART",
                "DTEND",
                "VEVENT",
            )

        # Test type mismatch
        event3 = Event()
        event3.add("UID", "test-type-mismatch")
        event3.add("DTSTART", date(2026, 1, 1))
        event3.add("DTEND", datetime(2026, 1, 1, 15, 0))

        with pytest.raises(InvalidCalendar, match="must be of the same type"):
            get_start_end_duration_with_validation(
                event3,
                "DTSTART",
                "DTEND",
                "VEVENT",
            )

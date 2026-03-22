"""Tests for issue #860: Improved setters for start/duration/end.

This test suite defines the desired behavior for the improved setter implementations
as described in https://github.com/collective/icalendar/issues/860

The tests ensure RFC 5545 compliance, proper property locking mechanisms,
and backward compatibility with existing code.
"""

from datetime import date, datetime, timedelta

import pytest

from icalendar import Event, Todo
from icalendar.error import IncompleteComponent, InvalidCalendar


class TestDurationSetter:
    """Test the new duration setter functionality."""

    def test_event_duration_setter_with_start_locked(self):
        """Test setting duration with start locked (default behavior)."""
        event = Event()
        event.add("UID", "test-duration-setter")
        event.start = datetime(2026, 1, 1, 12, 0)
        event.end = datetime(2026, 1, 1, 14, 0)  # 2 hours initially

        # Setting duration should keep start locked and adjust end
        event.duration = timedelta(hours=3)

        assert event.start == datetime(2026, 1, 1, 12, 0)  # start unchanged
        assert event.end == datetime(2026, 1, 1, 15, 0)  # end adjusted
        assert event.duration == timedelta(hours=3)
        assert "DURATION" in event  # DURATION property should be set
        assert "DTEND" not in event  # DTEND should be removed

    def test_event_duration_setter_creates_duration_property(self):
        """Test that setting duration creates DURATION property and removes DTEND."""
        event = Event()
        event.add("UID", "test-duration-property")
        event.start = datetime(2026, 1, 1, 12, 0)
        event.end = datetime(2026, 1, 1, 14, 0)

        # Initially has DTEND
        assert "DTEND" in event
        assert "DURATION" not in event

        # Setting duration should switch to DURATION property
        event.duration = timedelta(hours=1)

        assert "DURATION" in event
        assert "DTEND" not in event
        assert event.duration == timedelta(hours=1)

    def test_todo_duration_setter_with_start_locked(self):
        """Test setting duration for Todo with start locked."""
        todo = Todo()
        todo.add("UID", "test-todo-duration")
        todo.start = datetime(2026, 1, 1, 12, 0)
        todo.end = datetime(2026, 1, 1, 14, 0)

        # Setting duration should keep start locked and adjust end
        todo.duration = timedelta(hours=4)

        assert todo.start == datetime(2026, 1, 1, 12, 0)  # start unchanged
        assert todo.end == datetime(2026, 1, 1, 16, 0)  # end adjusted
        assert todo.duration == timedelta(hours=4)
        assert "DURATION" in todo
        assert "DUE" not in todo

    def test_duration_setter_without_start_raises_error(self):
        """Test that setting duration without start raises appropriate error."""
        event = Event()
        event.add("UID", "test-no-start")

        with pytest.raises(IncompleteComponent):
            event.duration = timedelta(hours=2)


class TestExplicitLockingMethods:
    """Test the explicit locking methods set_start(), set_end(), set_duration()."""

    def test_set_duration_with_start_locked(self):
        """Test set_duration() with start locked (default)."""
        event = Event()
        event.add("UID", "test-set-duration")
        event.start = datetime(2026, 1, 1, 12, 0)
        event.end = datetime(2026, 1, 1, 14, 0)

        # Default behavior: lock start
        event.set_duration(timedelta(hours=3))

        assert event.start == datetime(2026, 1, 1, 12, 0)
        assert event.end == datetime(2026, 1, 1, 15, 0)
        assert event.duration == timedelta(hours=3)

    def test_set_duration_with_end_locked(self):
        """Test set_duration() with end locked."""
        event = Event()
        event.add("UID", "test-set-duration-end-locked")
        event.start = datetime(2026, 1, 1, 12, 0)
        event.end = datetime(2026, 1, 1, 14, 0)

        # Lock end, adjust start
        event.set_duration(timedelta(hours=3), locked="end")

        assert event.start == datetime(2026, 1, 1, 11, 0)  # start adjusted
        assert event.end == datetime(2026, 1, 1, 14, 0)  # end unchanged
        assert event.duration == timedelta(hours=3)

    def test_set_duration_convert_to_duration_property(self):
        """Test set_duration() with None to convert to DURATION property."""
        event = Event()
        event.add("UID", "test-convert-duration")
        event.start = datetime(2026, 1, 1, 12, 0)
        event.end = datetime(2026, 1, 1, 14, 0)

        # Convert to DURATION property
        event.set_duration(None)

        assert "DURATION" in event
        assert "DTEND" not in event
        assert event.duration == timedelta(hours=2)

    def test_set_start_with_duration_locked(self):
        """Test set_start() with duration locked."""
        event = Event()
        event.add("UID", "test-set-start")
        event.start = datetime(2026, 1, 1, 12, 0)
        event.add("DURATION", timedelta(hours=2))

        # Default behavior when DURATION exists: lock duration
        event.set_start(datetime(2026, 1, 1, 10, 0))

        assert event.start == datetime(2026, 1, 1, 10, 0)
        assert event.end == datetime(2026, 1, 1, 12, 0)  # end adjusted
        assert event.duration == timedelta(hours=2)  # duration unchanged

    def test_set_start_with_end_locked(self):
        """Test set_start() with end locked."""
        event = Event()
        event.add("UID", "test-set-start-end-locked")
        event.start = datetime(2026, 1, 1, 12, 0)
        event.end = datetime(2026, 1, 1, 14, 0)

        # Lock end, adjust duration
        event.set_start(datetime(2026, 1, 1, 10, 0), locked="end")

        assert event.start == datetime(2026, 1, 1, 10, 0)
        assert event.end == datetime(2026, 1, 1, 14, 0)  # end unchanged
        assert event.duration == timedelta(hours=4)  # duration adjusted

    def test_set_end_with_start_locked(self):
        """Test set_end() with start locked (default)."""
        event = Event()
        event.add("UID", "test-set-end")
        event.start = datetime(2026, 1, 1, 12, 0)
        event.end = datetime(2026, 1, 1, 14, 0)

        # Default behavior: lock start
        event.set_end(datetime(2026, 1, 1, 16, 0))

        assert event.start == datetime(2026, 1, 1, 12, 0)  # start unchanged
        assert event.end == datetime(2026, 1, 1, 16, 0)
        assert event.duration == timedelta(hours=4)  # duration adjusted

    def test_set_end_with_duration_locked(self):
        """Test set_end() with duration locked."""
        event = Event()
        event.add("UID", "test-set-end-duration-locked")
        event.start = datetime(2026, 1, 1, 12, 0)
        event.add("DURATION", timedelta(hours=2))

        # Lock duration, adjust start
        event.set_end(datetime(2026, 1, 1, 16, 0), locked="duration")

        assert event.start == datetime(2026, 1, 1, 14, 0)  # start adjusted
        assert event.end == datetime(2026, 1, 1, 16, 0)
        assert event.duration == timedelta(hours=2)  # duration unchanged


class TestImprovedPropertySetters:
    """Test the improved property setters with smart defaults."""

    def test_start_setter_with_duration_property(self):
        """Test start setter when DURATION property exists (should lock duration)."""
        event = Event()
        event.add("UID", "test-start-duration")
        event.start = datetime(2026, 1, 1, 12, 0)
        event.add("DURATION", timedelta(hours=2))

        # Smart default: lock duration when DURATION property exists
        event.start = datetime(2026, 1, 1, 10, 0)

        assert event.start == datetime(2026, 1, 1, 10, 0)
        assert event.end == datetime(2026, 1, 1, 12, 0)
        assert event.duration == timedelta(hours=2)

    def test_start_setter_with_dtend_property(self):
        """Test start setter when DTEND property exists (should lock end)."""
        event = Event()
        event.add("UID", "test-start-dtend")
        event.start = datetime(2026, 1, 1, 12, 0)
        event.end = datetime(2026, 1, 1, 14, 0)

        # Smart default: lock end when DTEND property exists
        event.start = datetime(2026, 1, 1, 10, 0)

        assert event.start == datetime(2026, 1, 1, 10, 0)
        assert event.end == datetime(2026, 1, 1, 14, 0)
        assert event.duration == timedelta(hours=4)

    def test_end_setter_with_duration_property(self):
        """Test end setter when DURATION property exists (should remove DURATION)."""
        event = Event()
        event.add("UID", "test-end-duration")
        event.start = datetime(2026, 1, 1, 12, 0)
        event.add("DURATION", timedelta(hours=2))

        # Setting end should remove DURATION and set DTEND
        event.end = datetime(2026, 1, 1, 16, 0)

        assert event.start == datetime(2026, 1, 1, 12, 0)
        assert event.end == datetime(2026, 1, 1, 16, 0)
        assert event.duration == timedelta(hours=4)
        assert "DTEND" in event
        assert "DURATION" not in event


class TestRFCCompliance:
    """Test that the improved setters maintain RFC 5545 compliance."""

    def test_dtend_and_duration_mutual_exclusion(self):
        """Test that DTEND and DURATION are mutually exclusive."""
        event = Event()
        event.add("UID", "test-mutual-exclusion")
        event.start = datetime(2026, 1, 1, 12, 0)
        event.end = datetime(2026, 1, 1, 14, 0)

        # Setting duration should remove DTEND
        event.duration = timedelta(hours=3)
        assert "DURATION" in event
        assert "DTEND" not in event

        # Setting end should remove DURATION
        event.end = datetime(2026, 1, 1, 16, 0)
        assert "DTEND" in event
        assert "DURATION" not in event

    def test_date_duration_validation(self):
        """Test that date DTSTART with time-based DURATION raises error."""
        event = Event()
        event.add("UID", "test-date-duration")
        event.start = date(2026, 1, 1)  # DATE type

        # Should raise error for non-day/week duration
        with pytest.raises(InvalidCalendar):
            event.duration = timedelta(hours=2)

        # Should work for day/week duration
        event.duration = timedelta(days=1)
        assert event.duration == timedelta(days=1)

    def test_datetime_type_consistency(self):
        """Test that DTSTART and DTEND must have same type."""
        event = Event()
        event.add("UID", "test-type-consistency")
        event.start = datetime(2026, 1, 1, 12, 0)  # datetime type

        # Should raise error for date end with datetime start
        event.end = date(2026, 1, 1)
        with pytest.raises(InvalidCalendar):
            _ = event.end  # Error occurs when accessing the property


class TestBackwardCompatibility:
    """Test that the improved setters maintain backward compatibility."""

    def test_existing_simple_usage_still_works(self):
        """Test that existing simple usage patterns still work."""
        event = Event()
        event.add("UID", "test-backward-compat")

        # Simple usage should still work
        event.start = datetime(2026, 1, 1, 12, 0)
        event.end = datetime(2026, 1, 1, 14, 0)

        assert event.start == datetime(2026, 1, 1, 12, 0)
        assert event.end == datetime(2026, 1, 1, 14, 0)
        assert event.duration == timedelta(hours=2)

    def test_property_access_compatibility(self):
        """Test that property access remains compatible."""
        event = Event()
        event.add("UID", "test-property-access")
        event.start = datetime(2026, 1, 1, 12, 0)
        event.add("DURATION", timedelta(hours=2))

        # Property access should work as before
        assert event.DTSTART is not None
        assert event.DURATION is not None
        assert event.DTEND is None

        # Computed properties should work
        assert event.start == datetime(2026, 1, 1, 12, 0)
        assert event.end == datetime(2026, 1, 1, 14, 0)
        assert event.duration == timedelta(hours=2)


class TestErrorConditions:
    """Test error conditions and edge cases for improved coverage."""

    def test_set_duration_invalid_locked_value(self):
        """Test that invalid locked values raise appropriate errors."""
        event = Event()
        event.add("UID", "test-invalid-locked")
        event.start = datetime(2026, 1, 1, 12, 0)

        with pytest.raises(
            ValueError, match="locked must be 'start' or 'end', not 'invalid'"
        ):
            event.set_duration(timedelta(hours=2), locked="invalid")

    def test_set_start_invalid_locked_value(self):
        """Test that invalid locked values raise appropriate errors."""
        event = Event()
        event.add("UID", "test-invalid-locked")
        event.start = datetime(2026, 1, 1, 12, 0)

        with pytest.raises(
            ValueError, match="locked must be 'duration', 'end', or None, not 'invalid'"
        ):
            event.set_start(datetime(2026, 1, 1, 14, 0), locked="invalid")

    def test_set_end_invalid_locked_value(self):
        """Test that invalid locked values raise appropriate errors."""
        event = Event()
        event.add("UID", "test-invalid-locked")
        event.start = datetime(2026, 1, 1, 12, 0)

        with pytest.raises(
            ValueError, match="locked must be 'start' or 'duration', not 'invalid'"
        ):
            event.set_end(datetime(2026, 1, 1, 14, 0), locked="invalid")

    def test_duration_setter_invalid_type(self):
        """Test that duration setter rejects invalid types."""
        event = Event()
        event.add("UID", "test-invalid-type")
        event.start = datetime(2026, 1, 1, 12, 0)

        with pytest.raises(TypeError, match="Use timedelta, not str"):
            event.duration = "2 hours"

    def test_set_duration_invalid_type(self):
        """Test that set_duration rejects invalid types."""
        event = Event()
        event.add("UID", "test-invalid-type")
        event.start = datetime(2026, 1, 1, 12, 0)

        with pytest.raises(TypeError, match="Use timedelta, not int"):
            event.set_duration(7200, locked="start")

    def test_todo_error_conditions(self):
        """Test error conditions for Todo class."""
        todo = Todo()
        todo.add("UID", "test-todo-errors")
        todo.start = datetime(2026, 1, 1, 12, 0)

        # Test invalid locked values
        with pytest.raises(
            ValueError, match="locked must be 'start' or 'end', not 'invalid'"
        ):
            todo.set_duration(timedelta(hours=2), locked="invalid")

        with pytest.raises(
            ValueError, match="locked must be 'duration', 'end', or None, not 'invalid'"
        ):
            todo.set_start(datetime(2026, 1, 1, 14, 0), locked="invalid")

        with pytest.raises(
            ValueError, match="locked must be 'start' or 'duration', not 'invalid'"
        ):
            todo.set_end(datetime(2026, 1, 1, 14, 0), locked="invalid")

    def test_set_start_auto_detect_no_existing_properties(self):
        """Test auto-detection when no existing properties exist."""
        event = Event()
        event.add("UID", "test-auto-detect")

        # When no DURATION or DTEND exists, should default to duration
        event.set_start(datetime(2026, 1, 1, 12, 0), locked=None)
        assert event.start == datetime(2026, 1, 1, 12, 0)

        # Adding end should trigger duration calculation
        event.end = datetime(2026, 1, 1, 14, 0)
        # The auto-detect should have preserved the end time calculation

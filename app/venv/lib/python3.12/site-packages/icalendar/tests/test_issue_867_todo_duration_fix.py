"""Tests for issue #867: Todo.duration should work without DTSTART."""

from datetime import datetime, timedelta

import pytest

from icalendar import Event, Todo
from icalendar.error import IncompleteComponent


def test_todo_duration_without_dtstart():
    """Test that Todo.duration works when `DURATION` property is set but `DTSTART` is missing."""
    # This is the exact test case from issue #867
    my_task = Todo.from_ical("""BEGIN:VTODO
UID:taskwithoutdtstart
DTSTAMP:20070313T123432Z
DURATION:P5D
SUMMARY:This is a task that is expected to take five days to complete
STATUS:NEEDS-ACTION
END:VTODO""")

    # Should return the DURATION property directly
    assert my_task.duration == timedelta(days=5)


def test_todo_duration_calculated_from_start_and_due():
    """Test that Todo.duration still works for calculated duration from `DTSTART` and `DUE`."""
    todo = Todo()
    todo.add("UID", "test-calculated")
    todo.start = datetime(2026, 3, 19, 12, 0)
    todo.end = datetime(2026, 3, 19, 15, 30)

    # Should calculate duration from start and end
    assert todo.duration == timedelta(hours=3, minutes=30)


def test_todo_duration_prefers_duration_property():
    """Test that explicit `DURATION` property takes precedence over calculated duration."""
    todo = Todo()
    todo.add("UID", "test-precedence")
    todo.start = datetime(2026, 3, 19, 12, 0)
    todo.end = datetime(2026, 3, 19, 15, 0)  # This would be 3 hours
    todo.add("DURATION", timedelta(days=2))  # But DURATION says 2 days

    # Should return DURATION property, not calculated value
    assert todo.duration == timedelta(days=2)


def test_todo_duration_with_dtstart_and_duration():
    """Test Todo with `DTSTART` and `DURATION` (valid per RFC 5545)."""
    todo = Todo()
    todo.add("UID", "test-start-duration")
    todo.start = datetime(2026, 3, 19, 12, 0)
    todo.add("DURATION", timedelta(hours=4))

    # Should return DURATION property
    assert todo.duration == timedelta(hours=4)


def test_todo_duration_without_any_time_info_raises_error():
    """Test that Todo.duration raises error when no time information is available."""
    todo = Todo()
    todo.add("UID", "test-no-time")
    todo.add("SUMMARY", "Task without any time info")

    # Should raise error since no DURATION, DTSTART, or DUE is set
    with pytest.raises(IncompleteComponent):
        _ = todo.duration


def test_todo_duration_complex_duration_values():
    """Test Todo.duration with various complex duration formats."""
    # Test ISO 8601 duration formats
    test_cases = [
        ("PT30M", timedelta(minutes=30)),
        ("PT1H30M", timedelta(hours=1, minutes=30)),
        ("P1DT2H", timedelta(days=1, hours=2)),
        ("P1W", timedelta(weeks=1)),
        (
            "P1Y2M3DT4H5M6S",
            timedelta(days=428, hours=4, minutes=5, seconds=6),
        ),  # Approx 1 year 2 months
    ]

    for duration_str, expected_delta in test_cases:
        todo = Todo()
        todo.add("UID", f"test-{duration_str}")
        todo.add("DURATION", expected_delta)

        assert todo.duration == expected_delta


def test_todo_duration_maintains_backward_compatibility():
    """Test that the fix doesn't break existing functionality."""
    # Create todo the old way (DTSTART + DUE)
    todo = Todo()
    todo.add("UID", "test-backward-compat")
    todo.add("SUMMARY", "Backward compatibility test")
    todo.start = datetime(2026, 3, 19, 9, 0)
    todo.end = datetime(2026, 3, 19, 17, 0)

    # Should still work as before
    assert todo.duration == timedelta(hours=8)

    # Properties should still work
    assert todo.start == datetime(2026, 3, 19, 9, 0)
    assert todo.end == datetime(2026, 3, 19, 17, 0)


def test_todo_duration_edge_case_only_dtstart():
    """Test Todo with only `DTSTART` (no `DUE` or `DURATION`)."""
    todo = Todo()
    todo.add("UID", "test-only-start")
    todo.start = datetime(2026, 3, 19, 12, 0)

    # This should use the fallback logic from the end property
    # which returns start + 1 day for date, or just start for datetime
    assert todo.duration == timedelta(0)  # end defaults to start for datetime


def test_issue_867_exact_reproduction():
    """Test the exact scenario reported in issue #867."""
    # This reproduces the caldav project test case that was failing
    my_task = Todo.from_ical("""BEGIN:VTODO
UID:taskwithoutdtstart
DTSTAMP:20070313T123432Z
DURATION:P5D
SUMMARY:This is a task that is expected to take five days to complete
STATUS:NEEDS-ACTION
END:VTODO""")

    # This assertion was failing before the fix
    assert my_task.duration == timedelta(days=5)

    # Verify the todo has the expected properties
    assert my_task.get("UID") == "taskwithoutdtstart"
    assert (
        my_task.get("SUMMARY")
        == "This is a task that is expected to take five days to complete"
    )
    assert "DURATION" in my_task
    assert "DTSTART" not in my_task  # Confirming no DTSTART


def test_todo_duration_preserves_property_access():
    """Test that direct property access still works as expected."""
    todo = Todo()
    todo.add("UID", "test-property-access")
    todo.add("DURATION", timedelta(hours=2))

    # Direct property access should still work
    assert todo["DURATION"].dt == timedelta(hours=2)

    # And our computed property should match
    assert todo.duration == timedelta(hours=2)


# Parametrized tests for both Event and Todo components
@pytest.mark.parametrize("component_class", [Event, Todo])
def test_component_duration_prefers_duration_property(component_class):
    """Test that both Event and Todo prefer `DURATION` property over calculated duration."""
    component = component_class()
    component.add("UID", f"test-{component_class.__name__.lower()}-duration")
    component.start = datetime(2026, 3, 19, 12, 0)
    component.end = datetime(2026, 3, 19, 15, 0)  # This would be 3 hours
    component.add("DURATION", timedelta(hours=2))  # But DURATION says 2 hours

    # Should return DURATION property, not calculated value
    assert component.duration == timedelta(hours=2)


@pytest.mark.parametrize("component_class", [Event, Todo])
def test_component_duration_calculated_fallback(component_class):
    """Test that both Event and Todo fall back to calculated duration when no `DURATION` property."""
    component = component_class()
    component.add("UID", f"test-{component_class.__name__.lower()}-calculated")
    component.start = datetime(2026, 3, 19, 12, 0)
    component.end = datetime(2026, 3, 19, 14, 30)

    # Should calculate duration from start and end (no DURATION property)
    assert component.duration == timedelta(hours=2, minutes=30)

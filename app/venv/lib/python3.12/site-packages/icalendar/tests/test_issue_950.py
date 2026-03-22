"""Test for Issue #950: with_uid method on Component."""

from icalendar import Calendar, Event


def test_with_uid_finds_event():
    """Test that with_uid finds components with matching UID."""
    cal = Calendar()
    event = Event()
    event.add("uid", "test-uid-12345")
    event.add("summary", "Test Event")
    cal.add_component(event)

    result = cal.with_uid("test-uid-12345")
    assert len(result) == 1
    assert result[0].get("uid") == "test-uid-12345"


def test_with_uid_returns_empty_when_not_found():
    """Test that with_uid returns empty list when UID not found."""
    cal = Calendar()
    event = Event()
    event.add("uid", "some-other-uid")
    cal.add_component(event)

    result = cal.with_uid("nonexistent-uid")
    assert result == []

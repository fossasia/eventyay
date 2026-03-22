"""Test that we have good examples."""

from icalendar import Event

SUMMARY = "This is a Unicode summary. Das müssen wir dekodieren. Русский. ↧"


def test_summary_is_text():
    """The summary should be a text."""
    event = Event.new(summary=SUMMARY)
    assert event.summary == SUMMARY
    event = Event.from_ical(event.to_ical())
    assert event.summary == SUMMARY

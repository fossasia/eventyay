from icalendar import vBoolean, vCalAddress
from icalendar.cal.event import Event


def test_vBoolean_can_be_used_as_parameter_issue_500(events):
    """https://github.com/collective/icalendar/issues/500"""
    attendee = vCalAddress("mailto:someone@example.com")
    attendee.params["rsvp"] = vBoolean(True)
    event = Event()
    event.add("attendee", attendee)
    assert event.to_ical() == events.event_with_rsvp.raw_ics

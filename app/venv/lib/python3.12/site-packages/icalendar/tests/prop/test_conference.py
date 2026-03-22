"""Test conference properties."""

import pytest

from icalendar import Calendar, Event, Todo, vUri
from icalendar.prop.conference import Conference


def test_from_empty_uri():
    """Test creation from a URI."""
    conference = Conference.from_uri(vUri("https://chat.example.com/audio?id=123456"))
    assert conference.uri == "https://chat.example.com/audio?id=123456"
    assert conference.feature is None
    assert conference.label is None
    assert conference.language is None


def test_from_example_uri():
    """Create a conference with lots of values."""
    conference = Conference.from_uri(
        vUri(
            "https://chat.example.com/audio?id=123456",
            params={
                "FEATURE": "PHONE,MODERATOR",
                "LABEL": "Moderator dial-in",
                "LANGUAGE": "EN",
            },
        )
    )
    assert conference.uri == "https://chat.example.com/audio?id=123456"
    assert conference.feature == "PHONE,MODERATOR"
    assert conference.label == "Moderator dial-in"
    assert conference.language == "EN"


def test_to_uri():
    """Test creating a vURI."""
    uri = vUri(
        "https://chat.example.com/audio?id=123456",
        params={
            "FEATURE": "PHONE",
            "LABEL": "Moderator",
            "LANGUAGE": "DE",
            "VALUE": "URI",
        },
    )
    conference = Conference.from_uri(uri)
    new_uri = conference.to_uri()
    assert new_uri == uri
    assert new_uri.params == uri.params


def test_conference_list_params_serialization():
    """Ensure list parameters are correctly serialized to comma-separated strings."""
    conf = Conference(
        uri="https://example.com", feature=["AUDIO", "VIDEO"], label="Meeting room"
    )

    vuri = conf.to_uri()

    assert isinstance(vuri.params["FEATURE"], str)
    assert vuri.params["FEATURE"] == "AUDIO,VIDEO"
    assert vuri.params["LABEL"] == "Meeting room"


@pytest.fixture
def conference_1():
    """Fixture for a conference with a URI."""
    return Conference.from_uri(vUri("https://chat.example.com/audio?id=123456"))


@pytest.fixture
def conference_2():
    """Fixture for a conference with a URI."""
    return Conference(
        vUri("https://chat.example.com/audio?id=123456"),
        feature="PHONE",
        label="Moderator dial-in",
        language="EN",
    )


@pytest.fixture(params=[Event, Todo])
def component_class(request):
    """Fixture to create a Conference component."""
    return request.param


@pytest.fixture
def component(component_class):
    """Create a component."""
    return component_class()


def test_no_conferences(component):
    """No conferences by default."""
    assert component.conferences == []
    assert "CONFERENCE" not in component


def test_add_conference(component, conference_1):
    """Add a new conference."""
    component.conferences = [conference_1]
    assert component["CONFERENCE"] == conference_1.to_uri()


def test_add_multiple_conferences(component, conference_1, conference_2):
    """Add a new conference."""
    component.conferences = [conference_1, conference_2]
    assert component["CONFERENCE"] == [conference_1.to_uri(), conference_2.to_uri()]


def test_new_component_with_conferences(component_class, conference_1, conference_2):
    """Create a new component with conferences."""
    component = component_class.new(conferences=[conference_1, conference_2])
    assert component.conferences == [conference_1, conference_2]


def test_uri_in_ical_(conference_2, component):
    """The URI start be in the ical string."""
    component.conferences = [conference_2]
    ical_str = component.to_ical().decode("utf-8")
    assert "CONFERENCE;" in ical_str
    assert "/audio?id=123456" in ical_str
    assert "PHONE" in ical_str


def get_event(calendar: Calendar) -> Event:
    """Get the event directly"""
    return calendar.events[0]


def get_serialized_event(calendar: Calendar) -> Event:
    """Get the event directly"""
    cal = Calendar.from_ical(calendar.to_ical())
    return cal.events[0]


@pytest.fixture(params=[get_event, get_serialized_event])
def event_with_conferences(request, calendars):
    """Return the event from the file."""
    calendar = calendars.rfc_7986_conferences
    return request.param(calendar)


def test_conferences_from_file(event_with_conferences):
    """The conferences should be in the calendar."""
    assert len(event_with_conferences.conferences) == 5
    assert event_with_conferences.conferences[0].uri == "tel:+1-412-555-0123,,,654321"
    assert event_with_conferences.conferences[1].uri == "tel:+1-412-555-0123,,,555123"
    assert event_with_conferences.conferences[2].uri == "tel:+1-888-555-0456,,,555123"
    assert (
        event_with_conferences.conferences[3].uri
        == "xmpp:chat-123@conference.example.com"
    )
    assert (
        event_with_conferences.conferences[4].uri
        == "https://chat.example.com/audio?id=123456"
    )
    assert event_with_conferences.conferences[4].feature == ["AUDIO", "VIDEO"]
    assert event_with_conferences.conferences[4].label == "Attendee dial-in"
    assert event_with_conferences.conferences[4].language is None


def test_conference_from_string():
    """Create a conference from a string."""
    conference = Conference.from_uri("tel:+1-412-555-0123")
    assert conference.uri == "tel:+1-412-555-0123"
    assert conference.feature is None
    assert conference.label is None
    assert conference.language is None


def test_from_uri_string_adds_value_type():
    """Conference created from a string should add the value type."""
    conference = Conference.from_uri("http://asd")
    uri = conference.to_uri()
    assert uri.VALUE == "URI"

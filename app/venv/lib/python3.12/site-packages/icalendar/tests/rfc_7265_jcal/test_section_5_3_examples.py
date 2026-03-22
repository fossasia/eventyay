"""Check that we convert the examples propertly."""

from pprint import pprint

import pytest

from icalendar import Calendar, Event, vText
from icalendar.parser_tools import to_unicode


def test_convert_coffee(calendars):
    """convert the unknown value property"""
    calendar = calendars.rfc_7265_example_2
    ical = calendar.to_ical().decode()
    print(to_unicode(ical))
    assert r"X-COFFEE-DATA:Stenophylla\;Guinea\\\,Africa" in ical


@pytest.mark.parametrize(
    ("prop_name", "value", "expected_value"),
    [
        ("SUMMARY", "TEXT", "TEXT"),
        ("SUMMARY", "URI", "URI"),
        ("DESCRIPTION", "URI", "URI"),
        ("X-ALT-DESC", "UNKNOWN", "UNKNOWN"),
        ("X-ALT-DESC", "TEXT", "UNKNOWN"),
        ("DESCRIPTION", "TEXT", "TEXT"),
    ],
)
def test_know_attributes_do_not_receive_a_VALUE(prop_name, value, expected_value):
    """If we do not know a certain attribute, we always use the unknown property type."""
    event = Event()
    prop = vText("XXX")
    prop.VALUE = value
    event[prop_name] = prop
    jcal = event.to_jcal()
    pprint(jcal)
    event2 = Event.from_jcal(jcal)
    pprint(event2.to_jcal())
    assert event2[prop_name].VALUE == expected_value


def test_conversion_from_ical(calendars):
    """Convert the example to jCal."""
    calendar: Calendar = calendars.rfc_7265_example_1
    jcal = calendar.to_jcal()
    assert jcal[1][0] == ["x-complaint-deadline", {}, "unknown", "20110512T120000Z"]


def test_example_3(calendars):
    """Test the 3rd example."""
    calendar = calendars.rfc_7265_example_3
    ical = calendar.to_ical().decode()
    assert "PERCENT-COMPLETE:95" in ical


def test_example_4(events):
    """Test the 4th example."""
    event = events.rfc_7265_example_4
    ical = event.to_jcal()
    assert ical[1][0] == ["dtstart", {"x-slack": "30.3"}, "date", "2011-05-12"]

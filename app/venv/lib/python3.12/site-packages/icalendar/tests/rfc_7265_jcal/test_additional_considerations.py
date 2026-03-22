"""These are tests for considerations that are specific to our implementation."""

import pytest

from icalendar import Calendar, Component, ComponentFactory, Event, vText


def test_adding_a_description_several_times_works():
    """We should be able to add valid parameters several times."""
    event = Event()
    en = vText("English description", params={"language": "en"})
    de = vText("Deutsche Beschreibung", params={"language": "de"})
    event.add("DESCRIPTION", en)
    event.add("DESCRIPTION", de)
    jcal = event.to_jcal()
    assert jcal[1][0] == [
        "description",
        {"language": "en"},
        "text",
        "English description",
    ]
    assert jcal[1][1] == [
        "description",
        {"language": "de"},
        "text",
        "Deutsche Beschreibung",
    ]


def test_get_new_component_class():
    """A new component class should be created."""
    factory = ComponentFactory()
    cls1 = factory.get_component_class("VUNKNOWN")
    cls2 = factory.get_component_class("VUNKNOWN")
    assert cls1 is cls2
    assert cls1.name == "VUNKNOWN"
    assert cls1 is not Component


def test_text_from_jcal_does_not_add_backslashes():
    """It is possible that backslashes are added.

    see https://github.com/collective/icalendar/pull/979#issuecomment-3568261726
    """
    v_text = vText.from_jcal(["name", {}, "unknown", "8 backslash \\\\\\\\"])
    assert v_text.ical_value == "8 backslash \\\\\\\\"


CALENDAR_NAME = "8 backslash \\\\\\\\"


@pytest.fixture
def calendar_with_name():
    """The calendar for escape tests."""
    cal = Calendar()
    cal.calendar_name = CALENDAR_NAME
    assert cal.calendar_name == CALENDAR_NAME, "Setter ad Getter work."
    return cal


def test_backslash_escape_ics(calendar_with_name):
    """Test for properly escaped backslashes."""
    ics = calendar_with_name.to_ical()
    cal2: Calendar = Calendar.from_ical(ics)
    assert CALENDAR_NAME == cal2.calendar_name, "ics works"


def test_backslash_escape_jCal(calendar_with_name):
    """Test for properly escaped backslashes."""
    jcal = calendar_with_name.to_jcal()
    cal3: Calendar = Calendar.from_jcal(jcal)
    assert cal3.calendar_name == CALENDAR_NAME, "jcal works"

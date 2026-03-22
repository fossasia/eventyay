"""Test the conversion of components."""

import json

import pytest

from icalendar import Calendar, Event, Journal, Todo


@pytest.mark.parametrize(
    "component_class",
    [
        Calendar,
        Event,
        Todo,
        Journal,
    ],
)
def test_component_conversion(component_class):
    """test conversion of components to jCal."""
    component = component_class()
    jcal = component.to_jcal()
    assert len(jcal) == 3
    assert jcal[0] == component_class.name.lower()
    assert jcal[1] == []
    assert jcal[2] == []


@pytest.mark.parametrize(
    "component_class",
    [
        Event,
        Todo,
        Journal,
    ],
)
def test_nesting(component_class):
    """Nested components turn up in an sub array."""
    calendar = Calendar()
    calendar.add_component(component_class())
    jcal = calendar.to_jcal()
    assert len(jcal) == 3
    assert jcal[0] == "vcalendar"
    assert jcal[1] == []
    assert len(jcal[2]) == 1
    assert jcal[2][0] == [
        component_class.name.lower(),
        [],
        [],
    ]


def test_apply_json_serialization():
    """Check that we can convert to JSON."""
    calendar = Calendar()
    calendar.add_component(Event())
    assert calendar.to_json() == json.dumps(calendar.to_jcal())

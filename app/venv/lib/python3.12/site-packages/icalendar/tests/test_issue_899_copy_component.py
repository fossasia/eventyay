"""Tests for copying components.

See https://github.com/collective/icalendar/issues/899
"""

import pytest

from icalendar import Calendar, Event


@pytest.fixture
def component_with_subcomponent() -> Calendar:
    event = Event.new(description="Test")
    return Calendar.new(subcomponents=[event])


def test_shallow_copy_without_subcomponent(component_with_subcomponent):
    """We can copy a component and lose the subcomponent"""
    calendar2 = component_with_subcomponent.copy()
    assert len(calendar2.subcomponents) == 0
    assert calendar2 is not component_with_subcomponent


def test_full_copy_with_subcomponent(component_with_subcomponent):
    """We can copy a component with a child."""
    calendar2 = component_with_subcomponent.copy(recursive=True)
    assert len(calendar2.subcomponents) == 1
    assert calendar2 is not component_with_subcomponent
    event1 = component_with_subcomponent.subcomponents[0]
    event2 = calendar2.subcomponents[0]
    assert event1 is not event2
    assert event1.uid is not event2.uid


def test_full_copy_with_parameters():
    """We can copy a component with a child."""
    event1 = Event.new(description="Test")
    event1["description"].LANGUAGE = "en"
    event2 = event1.copy(recursive=True)
    assert event2["description"].LANGUAGE == "en"
    assert event2["description"].params == event1["description"].params
    assert event2["description"].params is not event1["description"].params

"""Test the sequence and other int properies.

https://www.rfc-editor.org/rfc/rfc5545#section-3.8.7.4
https://github.com/collective/icalendar/issues/802

"""

import pytest

from icalendar.cal.component import Component
from icalendar.cal.event import Event
from icalendar.cal.journal import Journal
from icalendar.cal.todo import Todo


@pytest.fixture(params=[0, None])
def default_sequence(request):
    return request.param


@pytest.fixture(params=[Event, Journal, Todo])
def component(request, default_sequence) -> Component:
    """Return a component."""
    component: Component = request.param()
    if default_sequence is not None:
        component["SEQUENCE"] = default_sequence
    return component


def test_sequence_is_0(component: Component):
    """Check the default value."""
    assert component.sequence == 0


def test_increase_sequence(component: Component):
    """Check the default value."""
    component.sequence += 1
    assert component.sequence == 1
    assert component["SEQUENCE"] == 1


def test_set_sequence(component: Component):
    """Check the default value."""
    component.sequence = 400
    assert component.sequence == 400
    assert component["SEQUENCE"] == 400


def test_delete_sequence_default(component: Component):
    """Delete the value."""
    del component.sequence
    assert component.sequence == 0


def test_delete_sequence_with_value(component: Component):
    """Delete the value."""
    component.sequence = 400
    del component.sequence
    assert component.sequence == 0

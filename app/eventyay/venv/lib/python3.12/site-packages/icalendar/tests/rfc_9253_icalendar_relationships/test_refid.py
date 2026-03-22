"""Test the REFID property."""

import pytest

from icalendar import Component


@pytest.fixture
def component():
    """Return a basic component for testing."""
    return Component()


def test_new_component_with_concept():
    """We can use new with just a string."""
    component = Component.new(refids="refid-1")
    assert len(component.refids) == 1
    assert component.refids[0] == "refid-1"
    assert isinstance(component.refids[0], str)


def test_delete_refids(component: Component):
    del component.refids
    component.refids = ["asd"]
    del component.refids
    assert component.refids == []


def test_delete_refids_with_none(component: Component):
    component.refids = ["123"]
    component.refids = None
    assert component.refids == []

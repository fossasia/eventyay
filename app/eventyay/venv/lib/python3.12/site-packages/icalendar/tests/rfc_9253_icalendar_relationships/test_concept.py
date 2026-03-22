"""Test the CONCEPT property."""

import pytest

from icalendar import Component, vUri


@pytest.fixture
def component():
    """Return a basic component for testing."""
    return Component()


def test_concept_is_converted_to_a_vUri(component):
    """We want a vUri list!"""
    component.concepts = ["file://a/concept"]
    assert len(component.concepts) == 1
    assert component.concepts[0].uri == "file://a/concept"
    assert isinstance(component.concepts[0], vUri)


def test_new_component_with_concept():
    """We can use new with just a string."""
    component = Component.new(concepts="https://gihub.com/collective/icalendar/issues")
    assert len(component.concepts) == 1
    assert component.concepts[0].uri == "https://gihub.com/collective/icalendar/issues"
    assert isinstance(component.concepts[0], vUri)


def test_delete_concepts(component: Component):
    del component.concepts
    component.concepts = ["ftp://asd"]
    del component.concepts
    assert component.concepts == []


def test_delete_concepts_with_none(component: Component):
    component.concepts = ["ftp://asd"]
    component.concepts = None
    assert component.concepts == []

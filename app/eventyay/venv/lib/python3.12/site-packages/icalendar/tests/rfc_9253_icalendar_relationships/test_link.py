"""Tests for icalendar relationships as per RFC 9253."""

import pytest

from icalendar import (
    Alarm,
    Availability,
    Available,
    Calendar,
    Event,
    FreeBusy,
    Journal,
    Timezone,
    TimezoneDaylight,
    TimezoneStandard,
    Todo,
)
from icalendar.prop import vUri


@pytest.fixture(
    params=(
        Alarm,
        Availability,
        Available,
        Calendar,
        Event,
        FreeBusy,
        Journal,
        Timezone,
        TimezoneDaylight,
        TimezoneStandard,
        Todo,
    )
)
def link_component_class(request):
    """The classes to test.

    rfc:`9253`::

        Conformance: Link: This property can be specified zero or
        more times in any iCalendar component.

    """
    return request.param


@pytest.fixture
def link_component(link_component_class):
    """An instance of the component class to test."""
    return link_component_class()


def test_no_links_by_default(link_component):
    """By default, components have no LINK properties."""
    assert "LINK" not in link_component
    assert link_component.links == []


def test_strings_are_converted_to_vUri(link_component):
    """We set the URI."""
    link_component.links = ["https://example.com"]
    assert link_component.links == [vUri("https://example.com")]
    assert isinstance(link_component.links[0], vUri)
    assert link_component.links[0].VALUE == "URI"

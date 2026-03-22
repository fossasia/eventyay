"""The RALATED-TO property is extended by :rfc:`9253`.

These are the tests for related_to.
"""

import pytest

from icalendar import (
    RELTYPE,
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
    vText,
    vUid,
    vUri,
)


def test_examples_from_rfc_9253(calendars):
    """Section 9.1 provides some examples."""
    calendar: Calendar = calendars.rfc_9253_related_to
    event = calendar.events[0]
    related_to = event.related_to

    assert len(related_to) == 3

    assert (
        related_to[0].ical_value == "jsmith.part7.19960817T083000.xyzMail@example.com"
    )
    assert related_to[0].RELTYPE == "PARENT", "default"
    assert isinstance(related_to[0], vText)

    assert related_to[1].uid == "19960401-080045-4000F192713-0052@example.com"
    assert related_to[1].ical_value == "19960401-080045-4000F192713-0052@example.com"
    assert related_to[1].RELTYPE == "PARENT", "default"
    assert isinstance(related_to[1], vUid)

    assert (
        related_to[2].uri
        == "https://example.com/caldav/user/jb/cal/19960401-080045-4000F192713.ics"
    )
    assert (
        related_to[2].ical_value
        == "https://example.com/caldav/user/jb/cal/19960401-080045-4000F192713.ics"
    )
    assert related_to[2].RELTYPE == RELTYPE.STARTTOFINISH
    assert isinstance(related_to[2], vUri)


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
def related_to_component_class(request):
    """The classes to test.

    rfc:`9253`::

        Conformance: RELATED-TO: This property can be specified zero or
        more times in any iCalendar component.

    """
    return request.param


@pytest.fixture
def related_to_component(related_to_component_class):
    """An instance of the component class to test."""
    return related_to_component_class()


def test_no_related_to_by_default(related_to_component):
    """By default, components have no RELATED-TO properties."""
    assert "RELATED-TO" not in related_to_component
    assert related_to_component.related_to == []


def test_strings_are_converted_to_the_default_value_type(related_to_component):
    """We set the URI.

    According to :rfc:`5545`, this should be vText.
    """
    related_to_component.related_to = ["https://example.com"]
    assert related_to_component.related_to == [vText("https://example.com")]
    assert isinstance(related_to_component.related_to[0], vText)
    assert related_to_component.related_to[0].params.value is None, (
        "We do not need to specify the default value."
    )

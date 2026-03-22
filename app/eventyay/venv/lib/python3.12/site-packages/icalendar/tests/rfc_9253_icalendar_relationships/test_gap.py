"""The GAP parameter can be defined on RELATED-TO properties."""

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from icalendar import Journal
from icalendar.error import InvalidCalendar
from icalendar.prop import vText, vUid, vUri

if TYPE_CHECKING:
    from icalendar import Calendar


@pytest.fixture
def component():
    """Return a basic component for testing."""
    return Journal()


def test_get_gap_example(calendars):
    """Get the gap from an example calendar."""
    calendar: Calendar = calendars.rfc_9253_gap
    event1 = calendar.events[0]
    event2 = calendar.events[1]
    assert event1.related_to == []
    relation: vUri = event2.related_to[0]
    assert relation.params["GAP"]
    assert relation.GAP == timedelta(weeks=1)
    assert relation.uid == "1"


@pytest.fixture(params=[vText, vUid, vUri])
def related_to_prop(request):
    """The RELATED-TO property classes to test."""
    return request.param("uid-text-or-url")


@pytest.mark.parametrize(
    ("gap_input", "value"),
    [
        (timedelta(days=3), timedelta(days=3)),
        ("P15D", timedelta(days=15)),
        ("-PT6H", timedelta(hours=-6)),
    ],
)
def test_get_and_set_gap(gap_input, value, related_to_prop):
    """Check that we can get the GAP parameter."""
    related_to_prop.GAP = gap_input
    assert related_to_prop.GAP == value
    assert related_to_prop.params["GAP"]


def test_serialize(component, related_to_prop):
    """Check that we can serialize the GAP parameter."""
    related_to_prop.GAP = timedelta(days=10)
    component.add("RELATED-TO", related_to_prop)
    ical = component.to_ical().decode()
    assert "GAP=P10D" in ical


def test_delete_gap(related_to_prop):
    """Check that we can delete the GAP parameter."""
    related_to_prop.GAP = timedelta(days=5)
    del related_to_prop.GAP
    assert related_to_prop.GAP is None


def test_delete_gap_by_setting_to_None(related_to_prop):
    """Check that we can delete the GAP parameter."""
    related_to_prop.GAP = timedelta(days=5)
    related_to_prop.GAP = None
    assert related_to_prop.GAP is None


def test_set_invalid_value(related_to_prop):
    """Check setting invalid values."""
    with pytest.raises(ValueError):
        related_to_prop.GAP = "invalid"
    with pytest.raises(TypeError):
        related_to_prop.GAP = object()


def test_get_malformed_value(related_to_prop):
    """What if the value is a string?"""
    related_to_prop.params["GAP"] = "invalid"
    with pytest.raises(InvalidCalendar):
        related_to_prop.GAP  # noqa: B018, RUF100


def test_gap_invalid_value(related_to_prop):
    """Other value types could be there but are problematic."""
    related_to_prop.params["GAP"] = object()
    with pytest.raises(TypeError):
        related_to_prop.GAP  # noqa: B018, RUF100

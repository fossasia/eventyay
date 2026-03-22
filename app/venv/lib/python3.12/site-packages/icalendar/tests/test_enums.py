"""Test the enums for values."""

import pytest

import icalendar
from icalendar import enums

ENUMS = [name for name in dir(enums) if name.isupper()]


@pytest.fixture(params=ENUMS)
def enum_name(request):
    """The name of an enum"""
    return request.param


@pytest.fixture
def enum(enum_name):
    """An enum."""
    return getattr(enums, enum_name)


def test_all_enums_are_exported(enum_name):
    """All enums should be exported."""
    assert enum_name in enums.__all__


def test_all_enums_are_public(enum_name):
    """All enums should be exported."""
    assert enum_name in icalendar.__all__, f"icalendar.__all__ is missing {enum_name}"


def test_enum_has_description(enum):
    """We should have a docstring."""
    assert "Description:" in enum.__doc__

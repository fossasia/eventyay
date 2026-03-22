"""Create a new method for the Calendar class.

See https://github.com/collective/icalendar/issues/596
"""

import pytest

from icalendar import Calendar, __version__


@pytest.mark.parametrize(
    ("name", "default_value"),
    [
        ("name", None),
        ("description", None),
        ("prodid", f"-//collective//icalendar//{__version__}//EN"),
        ("version", "2.0"),
        ("calscale", None),
        ("method", None),
        ("color", None),
    ],
)
def test_new_calendar_has_some_values(name, default_value):
    """When we create a new calendar, we want to have these values as default."""
    c = Calendar.new()
    assert c.get(name) == default_value
    assert default_value is None or name in c


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("name", "foo"),
        ("description", "bar"),
        ("prodid", "my-product"),
        ("version", "2.1"),
        ("calscale", "GREGORIAN"),
        ("method", "PUBLISH"),
        ("color", "#ff0000"),
    ],
)
def test_override_default_values(name, value):
    c = Calendar.new(**{name: value})
    assert c.get(name) == value


def test_default_getters():
    c = Calendar.new()
    assert c.calendar_name is None
    assert c.description is None
    assert c.version == "2.0"
    assert c.prodid == f"-//collective//icalendar//{__version__}//EN"
    assert c.calscale == "GREGORIAN"
    assert c.method == ""
    assert c.color == ""
    assert c.categories == []
    assert c.subcomponents == []


def test_categories():
    c = Calendar.new(categories=["foo", "bar"])
    assert c.categories == ["foo", "bar"]

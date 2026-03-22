"""This tests additional attributes from :rfc:`7986`.

Some attributes are also available as ``X-*`` attributes.
They are also considered.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest

from icalendar import Calendar, Event, Journal, Todo, vText, vUri

UTC = timezone.utc


@pytest.fixture
def calendar() -> Calendar:
    """Empty calendar"""
    return Calendar()


param_name = pytest.mark.parametrize("name", ["Company Vacation Days", "Calendar Name"])
param_prop = pytest.mark.parametrize("prop", ["NAME", "X-WR-CALNAME"])


@param_prop
@param_name
def test_get_calendar_name(prop, name, calendar):
    """Get the name of the calendar."""
    calendar.add(prop, name)
    assert calendar.calendar_name == name


@param_name
def test_set_calendar_name(name, calendar):
    """Setting the name overrides the old attributes and sets both NAME and X-WR-CALNAME."""
    calendar.calendar_name = name
    assert calendar.calendar_name == name
    assert calendar["NAME"] == name
    assert calendar["X-WR-CALNAME"] == name


@param_name
@param_prop
def test_replace_name(name, prop, calendar):
    """Setting the name overrides the old attributes."""
    calendar[prop] = "Other Name"
    calendar.calendar_name = name
    assert calendar.calendar_name == name


@param_name
@param_prop
def test_del_name(name, calendar, prop):
    """Delete the name."""
    calendar.add(prop, name)
    del calendar.calendar_name
    assert calendar.calendar_name is None


def test_default_name(calendar):
    """We have no name by default."""
    assert calendar.calendar_name is None


@param_name
def test_setting_the_name_sets_both_properties(calendar, name):
    """Setting calendar_name sets both NAME and X-WR-CALNAME for compatibility."""
    calendar.calendar_name = name
    assert calendar.calendar_name == name
    assert calendar["NAME"] == name
    assert calendar["X-WR-CALNAME"] == name


@param_name
@pytest.mark.parametrize("order", [1, 2])
def test_multiple_names_use_the_one_without_a_language(calendar, name, order):
    """Add several names and use the one without a language param."""
    if order == 1:
        calendar.add("NAME", name)
    calendar.add("NAME", vText("Kalendername", params={"LANGUAGE": "de"}))
    if order == 2:
        calendar.add("NAME", name)
    assert calendar.calendar_name == name


@param_name
def test_name_is_preferred(calendar, name):
    """NAME is more important that X-WR-CALNAME"""
    calendar.add("NAME", name)
    calendar.add("X-WR-CALNAME", "asd")
    assert calendar.calendar_name == name


# For description, we would use the same tests as name, but we also use the
# same code, so it is all right.

param_color = pytest.mark.parametrize("desc", ["DESCRIPTION", "X-WR-CALDESC"])


@param_color
@param_name
def test_description(calendar, desc, name):
    """Get the value"""
    calendar.add(desc, name)
    assert calendar.description == name


# For color, we would use the same tests as name, but we also use the
# same code, so it is all right.

param_color = pytest.mark.parametrize(
    "color_param", ["COLOR", "X-APPLE-CALENDAR-COLOR"]
)


@param_color
def test_get_calendar_color(calendar, color_param, color):
    """Get the value"""
    calendar.add(color_param, color)
    assert calendar.color == color


@param_color
def test_delete_calendar_color(calendar, color_param, color):
    """Delete the value"""
    calendar.add(color_param, color)
    del calendar.color
    assert calendar.color == ""
    assert color_param not in calendar


@param_color
def test_set_calendar_color(calendar, color_param, color):
    """Set the color and it replaces what is there."""
    calendar.add(color_param, "green")
    calendar.color = color
    assert calendar.color == color
    assert calendar["COLOR"] == color


def test_get_COLOR_first(calendar, color):
    """We prefer COLOR over X-APPLE-CALENDAR-COLOR"""
    calendar.add("COLOR", color)
    calendar.add("X-APPLE-CALENDAR-COLOR", "green")
    assert calendar.color == color


# The color of the event is a bit different
# It only appears once and does not have a backup.


@pytest.fixture(params=[Calendar, Event, Todo, Journal])
def color_component(request) -> Calendar | Event | Todo | Journal:
    """An empty component that should have a color attribute."""
    return request.param()


@pytest.fixture(params=["blue", "#123456"])
def color(request) -> str:
    """Return a color."""
    return request.param


def test_default_color(color_component: Calendar | Event | Todo | Journal):
    """There is no color by default."""
    assert color_component.color == ""


def test_set_the_color(color: str, color_component: Calendar | Event | Todo | Journal):
    """We set the value and get it."""
    color_component.color = color
    assert color_component.color == color
    assert color_component["COLOR"] == color


def test_replace_color(color: str, color_component: Calendar | Event | Todo | Journal):
    """Replace the color."""
    color_component.color = "blue"
    color_component.color = color
    assert color_component.color == color
    assert color_component["COLOR"] == color


def test_multiple_colors(color_component: Calendar | Event | Todo | Journal):
    """Add several colors and use the first one."""
    color_component.add("COLOR", "blue")
    color_component.add("COLOR", "green")
    assert color_component.color == "blue"


def test_delete_the_color(color_component: Calendar | Event | Todo | Journal):
    """Delete the color."""
    color_component.color = "blue"
    del color_component.color
    assert "COLOR" not in color_component
    assert color_component.color == ""


def test_set_if_multiple_colors(
    color: str, color_component: Calendar | Event | Todo | Journal
):
    """Add several colors and use the first one."""
    color_component.add("COLOR", "blue")
    color_component.add("COLOR", "green")
    color_component.color = color
    assert color_component.color == color


def test_refresh_interval_default(calendar: Calendar):
    """REFRESH-INTERVAL default."""
    assert calendar.get("REFRESH-INTERVAL") is None
    assert calendar.refresh_interval is None


@pytest.mark.parametrize(
    "invalid_value",
    [
        datetime(2020, 1, 1),
        date(2020, 1, 1),
        "invalid",
        (date(2020, 1, 1), timedelta(days=1)),
        time(12, 0),
    ],
)
def test_invalid_refresh_interval_type(calendar: Calendar, invalid_value):
    """Invalid REFRESH-INTERVAL"""
    calendar.refresh_interval = timedelta(hours=1)
    with pytest.raises(TypeError):
        calendar.refresh_interval = invalid_value
    assert calendar.refresh_interval == timedelta(hours=1)


@pytest.mark.parametrize("invalid_value", [timedelta(seconds=-1), timedelta(seconds=0)])
def test_invalid_refresh_interval(calendar: Calendar, invalid_value):
    """Invalid REFRESH-INTERVAL.

    Test:
    - value validation
    - no deletion of the current value
    """
    calendar.refresh_interval = timedelta(hours=2)
    with pytest.raises(ValueError):
        calendar.refresh_interval = invalid_value
    assert calendar.refresh_interval == timedelta(hours=2)


def test_refresh_interval_set_to_value(calendar: Calendar):
    """REFRESH-INTERVAL setting."""
    calendar.refresh_interval = timedelta(hours=1)
    assert calendar.refresh_interval == timedelta(hours=1)
    assert calendar["REFRESH-INTERVAL"].td == timedelta(hours=1)


def test_refresh_interval_set_to_value_by_dict(calendar: Calendar):
    """REFRESH-INTERVAL setting."""
    calendar.add("REFRESH-INTERVAL", timedelta(days=1, hours=2))
    assert calendar.refresh_interval == timedelta(days=1, hours=2)
    assert calendar["REFRESH-INTERVAL"].dt == timedelta(days=1, hours=2)


def get_rfc_7986_properties_calendar(calendars):
    """ICS -> obj"""
    return calendars.rfc_7986_properties


def get_rfc_7986_properties_calendar_serialized(calendars):
    """ICS -> obj -> ICS -> obj"""
    cal = calendars.rfc_7986_properties
    return Calendar.from_ical(cal.to_ical())


@pytest.mark.parametrize(
    "get_calendar",
    [get_rfc_7986_properties_calendar, get_rfc_7986_properties_calendar_serialized],
)
def test_attributes_from_calendar(calendars, get_calendar):
    """Check that the attributes have a certain value."""
    calendar: Calendar = get_calendar(calendars)
    assert calendar.calendar_name == "RFC 7986 calendar"
    assert calendar.color == "black"
    assert calendar.refresh_interval == timedelta(hours=3)
    assert calendar.last_modified == datetime(2016, 10, 29, 12, 12, 29, tzinfo=UTC), (
        "20161029T121229Z"
    )
    assert calendar.uid == "5FC53010-1267-4F8E-BC28-1D7AE55A7C99"
    assert calendar.description == "We want a lot of RFC 7986 parameters in here!"
    assert (
        calendar.source
        == "https://github.com/collective/icalendar/tree/main/src/icalendar/tests/calendars/rfc_7986_properties.ics"
    )
    assert isinstance(calendar.source, vUri)

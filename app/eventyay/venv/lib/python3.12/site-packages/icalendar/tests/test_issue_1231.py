from datetime import date, datetime, timezone

import pytest

from icalendar import Available, Calendar, Event, Journal, Todo
from icalendar.attr import RECURRENCE_ID
from icalendar.error import InvalidCalendar
from icalendar.prop import vText


@pytest.fixture(params=[Event, Todo, Journal, Available])
def component_cls(request):
    return request.param


@pytest.fixture
def component(component_cls):
    return component_cls({})


def test_recurrence_id_absent_returns_none(component):
    """If RECURRENCE-ID is absent, RECURRENCE_ID getter returns None."""
    assert "RECURRENCE-ID" not in component

    assert component.RECURRENCE_ID is None


@pytest.mark.parametrize(
    "value",
    [
        datetime(2025, 4, 28, 16, 5, tzinfo=timezone.utc),
        datetime(2025, 4, 28, 16, 5),
    ],
)
def test_recurrence_id_returns_datetime(component, value):
    """RECURRENCE-ID set to datetime is returned as datetime."""
    RECURRENCE_ID.__set__(component, value)
    assert "RECURRENCE-ID" in component

    result = component.RECURRENCE_ID
    assert isinstance(result, datetime)
    assert result == value


def test_recurrence_id_returns_date(component):
    """RECURRENCE-ID set to date is returned as date."""
    value = date(2025, 4, 28)
    component.RECURRENCE_ID = value
    assert "RECURRENCE-ID" in component

    result = component.RECURRENCE_ID
    assert isinstance(result, date)
    assert not isinstance(result, datetime)
    assert result == value


@pytest.mark.parametrize("invalid", [42, object(), "not-a-date"])
def test_recurrence_id_invalid_type_raises(component, invalid):
    """Setting RECURRENCE-ID to an invalid Python type raises TypeError."""
    with pytest.raises(TypeError):
        component.RECURRENCE_ID = invalid


@pytest.mark.parametrize("raw", [vText("some text"), vText(b"some text")])
def test_recurrence_id_invalid_raw_value_raises_invalid_calendar(component_cls, raw):
    """Invalid raw vProp in RECURRENCE-ID raises InvalidCalendar on access."""
    component = component_cls({"RECURRENCE-ID": raw})

    with pytest.raises(InvalidCalendar):
        _ = component.RECURRENCE_ID


def test_recurrence_id_invalid_vprop_raises_invalid_calendar(component_cls):
    """Invalid vProp object in RECURRENCE-ID raises InvalidCalendar."""
    component = component_cls({"RECURRENCE-ID": vText("some text")})

    with pytest.raises(InvalidCalendar):
        _ = component.RECURRENCE_ID


def test_recurrence_id_set_none_deletes_property(component):
    """Setting RECURRENCE-ID to None removes the property."""
    dt = datetime(2025, 4, 28, 16, 5)
    component.RECURRENCE_ID = dt

    assert "RECURRENCE-ID" in component

    component.RECURRENCE_ID = None
    assert "RECURRENCE-ID" not in component


def test_recurrence_id_del_deletes_property(component):
    """Deleting RECURRENCE-ID removes the property."""
    dt = datetime(2025, 4, 28, 16, 5)
    component.RECURRENCE_ID = dt

    assert "RECURRENCE-ID" in component

    del component.RECURRENCE_ID
    assert "RECURRENCE-ID" not in component

    assert component.RECURRENCE_ID is None


def test_recurrence_id_with_timezone_in_to_ical(component_cls):
    """RECURRENCE-ID with timezone is preserved in to_ical()."""
    component = component_cls({})
    dt = datetime(2025, 4, 28, 16, 5, tzinfo=timezone.utc)

    component.RECURRENCE_ID = dt
    ical_bytes = component.to_ical()
    lines = ical_bytes.splitlines()

    assert any(
        line.startswith((b"RECURRENCE-ID;TZID=", b"RECURRENCE-ID:20250428T160500Z"))
        for line in lines
    )


@pytest.mark.parametrize("tz_backend", ["pytz", "zoneinfo"])
def test_recurrence_id_parsed_from_calendar(tz_backend, calendars):
    """RECURRENCE-ID is correctly parsed from existing calendars."""
    cal: Calendar = calendars["issue_1231_recurrence"]
    components = [
        c
        for c in cal.walk()
        if c.name in {"VEVENT", "VTODO", "VJOURNAL"} and "RECURRENCE-ID" in c
    ]

    assert components, "Expected at least one component with RECURRENCE-ID"

    comp = components[0]
    expected = datetime(2025, 4, 28, 16, 5, tzinfo=timezone.utc)

    result = comp.RECURRENCE_ID
    assert isinstance(result, datetime)
    assert result == expected

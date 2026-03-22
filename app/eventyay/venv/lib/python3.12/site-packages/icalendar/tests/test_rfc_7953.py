"""This tests the parsing of the VAVAILABILITY component as defined in :rfc:`7953`."""

from datetime import date, datetime, timedelta, timezone

import pytest

from icalendar import BUSYTYPE, Availability, Available, Calendar
from icalendar.error import IncompleteComponent


@pytest.fixture(params=[Availability, Available])
def rfc_7953_component_class(request):
    """The component class."""
    return request.param


@pytest.fixture
def rfc_7953_component(rfc_7953_component_class):
    """The component class."""
    return rfc_7953_component_class()


def test_uid(availabilities):
    """Test the UID property."""
    availability: Availability = availabilities.rfc_7953_1
    assert availability.uid == "0428C7D2-688E-4D2E-AC52-CD112E2469DF"


def test_organizer(availabilities):
    """Test the ORGANIZER property."""
    availability: Availability = availabilities.rfc_7953_1
    assert availability.organizer == "mailto:bernard@example.com"
    assert availability.organizer.email == "bernard@example.com"


def test_dtstamp(availabilities, tzp):
    """Test the DTSTAMP property."""
    availability: Availability = availabilities.rfc_7953_1
    assert availability.DTSTAMP == tzp.localize_utc(datetime(2011, 10, 5, 13, 32, 25))


def test_subcomponents(availabilities):
    """Test the subcomponents."""
    availability: Availability = availabilities.rfc_7953_1
    assert len(availability.subcomponents) == 1
    assert availability.available == availability.subcomponents


def test_busy_type_default():
    assert Availability().busy_type == BUSYTYPE.BUSY_UNAVAILABLE


def test_set_busy_type():
    availability = Availability()
    availability.busy_type = BUSYTYPE.BUSY
    assert availability.busy_type == BUSYTYPE.BUSY
    assert availability["BUSYTYPE"] == "BUSY"


def test_new_sets_default(test_uid):
    availability = Availability.new()
    assert availability.busy_type == BUSYTYPE.BUSY_UNAVAILABLE
    assert availability.uid == test_uid


def test_create_new_availability_with_subsomponents(dont_validate_new):
    avaiable = Available.new(summary="Available1")
    availability = Availability.new(busy_type=BUSYTYPE.BUSY, components=[avaiable])
    assert len(availability.available) == 1
    assert availability.available[0].summary == "Available1"


def test_avaiable_needs_start():
    """Start is required and not set automatically"""
    with pytest.raises(ValueError) as e:
        Available.new()
    assert "Available start must be a datetime with a timezone" in str(e.value)


@pytest.mark.parametrize("key", ["start", "end"])
@pytest.mark.parametrize(
    "value", [datetime(2011, 10, 5, 13, 32, 25), date(2011, 10, 5)]
)
def test_avaiable_needs_timezone(key, value, rfc_7953_component_class):
    """Start is required and not set automatically"""
    kw = {key: value}
    with pytest.raises(ValueError) as e:
        rfc_7953_component_class.new(**kw)
    assert f"{key} must be a datetime with a timezone" in str(e.value)


def test_create_with_start(tzp):
    """Create with a valid start."""
    start = tzp.localize_utc(datetime(2011, 10, 5, 13, 32, 25))
    available = Available.new(start=start)
    assert available.start == start


def test_create_with_start_and_end(tzp):
    """Create with a valid start and end."""
    start = tzp.localize_utc(datetime(2011, 10, 5, 13, 32, 25))
    end = tzp.localize_utc(datetime(2011, 10, 5, 14, 32, 25))
    available = Available.new(start=start, end=end)
    assert available.start == start
    assert available.end == end


def test_duration_from_end(rfc_7953_component, tzp):
    """Check the computation of end and duration."""
    rfc_7953_component.start = tzp.localize_utc(datetime(2011, 10, 5, 13, 32, 25))
    rfc_7953_component.end = tzp.localize_utc(datetime(2011, 10, 5, 14, 32, 25))
    assert rfc_7953_component.duration == timedelta(hours=1)


def test_duration_and_end_from_duration(rfc_7953_component, tzp):
    """Check the computation of end and duration."""
    rfc_7953_component.start = tzp.localize_utc(datetime(2011, 10, 5, 13, 32, 25))
    rfc_7953_component.DURATION = timedelta(hours=1)
    assert rfc_7953_component.duration == timedelta(hours=1)
    assert rfc_7953_component.end == tzp.localize_utc(datetime(2011, 10, 5, 14, 32, 25))


def test_start_only_has_no_duration(rfc_7953_component, tzp):
    """Check the computation of end and duration."""
    rfc_7953_component.start = tzp.localize_utc(datetime(2011, 10, 5, 13, 32, 25))
    assert rfc_7953_component.duration is None
    assert rfc_7953_component.end is None


def test_missing_info_for_end(rfc_7953_component):
    """We miss information and cannot compute the end."""
    rfc_7953_component.DURATION = timedelta(hours=1)
    with pytest.raises(IncompleteComponent) as e:
        rfc_7953_component.end  # noqa: B018, RUF100
    assert "Cannot compute end without start" in str(e.value)


def test_missing_info_for_duration(rfc_7953_component, tzp):
    """We only have a duration."""
    rfc_7953_component.end = tzp.localize_utc(datetime(2011, 10, 5, 13, 32, 25))
    with pytest.raises(IncompleteComponent) as e:
        rfc_7953_component.duration  # noqa: B018, RUF100
    assert "Cannot compute duration without start" in str(e.value)


def test_example_2(availabilities, tzp):
    """Test that we get all the right values after parsing."""
    a: Availability = availabilities.rfc_7953_2
    assert a.organizer == "mailto:bernard@example.com"
    assert a.uid == "84D0F948-7FC6-4C1D-BBF3-BA9827B424B5"
    assert a.stamp == datetime(2011, 10, 5, 13, 32, 25, tzinfo=timezone.utc)
    assert a.start == tzp.localize(datetime(2011, 10, 2), "America/Montreal")
    assert a.end == tzp.localize(datetime(2011, 12, 2), "America/Montreal")
    a1 = a.available[0]
    assert a1.uid == "7B33093A-7F98-4EED-B381-A5652530F04D"
    assert a1.summary == "Monday to Thursday from 9:00 to 17:00"
    assert a1.start == tzp.localize(datetime(2011, 10, 2, 9), "America/Montreal")
    assert a1.end == tzp.localize(datetime(2011, 10, 2, 17), "America/Montreal")
    assert len(a1.rrules) == 1
    assert a1.rrules[0]["freq"] == ["WEEKLY"]
    assert a1.rrules[0]["byday"] == ["MO", "TU", "WE", "TH"]
    assert a1.location == "Main Office"
    assert a1.exdates == []
    a2 = a.available[1]
    assert a2.uid == "DF39DC9E-D8C3-492F-9101-0434E8FC1896"
    assert a2.summary == "Friday from 9:00 to 12:00"
    assert a2.start == tzp.localize(datetime(2011, 10, 6, 9), "America/Montreal")
    assert a2.end == tzp.localize(datetime(2011, 10, 6, 12), "America/Montreal")
    assert len(a2.rrules) == 1
    assert a2.rrules[0]["freq"] == ["WEEKLY"]
    assert a2.location == "Branch Office"
    assert a2.exdates == []


def test_example_3(calendars, tzp):
    """Test that we get all the right values after parsing."""
    calendar: Calendar = calendars.rfc_7953_3
    a: Availability = calendar.availabilities[0]
    assert a.organizer == "mailto:bernard@example.com"
    assert a.uid == "BE082249-7BDD-4FE0-BDBA-DE6598C32FC9"
    assert a.stamp == datetime(2011, 10, 5, 13, 32, 25, tzinfo=timezone.utc)
    assert a.start == tzp.localize(datetime(2011, 10, 2), "America/Montreal")
    assert a.end == tzp.localize(datetime(2011, 10, 23, 3), "America/Montreal")
    a1 = a.available[0]
    assert a1.uid == "54602321-CEDB-4620-9099-757583263981"
    assert a1.summary == "Monday to Friday from 9:00 to 17:00"
    assert a1.start == tzp.localize(datetime(2011, 10, 2, 9), "America/Montreal")
    assert a1.end == tzp.localize(datetime(2011, 10, 2, 17), "America/Montreal")
    assert len(a1.rrules) == 1
    assert a1.rrules[0]["freq"] == ["WEEKLY"]
    assert a1.rrules[0]["byday"] == ["MO", "TU", "WE", "TH", "FR"]
    assert a1.location == "Montreal"
    assert a1.exdates == []
    assert len(calendar.availabilities) == 3

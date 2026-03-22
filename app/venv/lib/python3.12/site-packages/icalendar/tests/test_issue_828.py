"""Events differ although their times are equal.

See https://github.com/collective/icalendar/issues/828
"""

import contextlib
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from icalendar import Event, Journal, vDate, vDatetime, vDDDLists, vDDDTypes


def to_dt(a: date) -> date:
    return a


def to_event(a):
    e = Event()
    e.start = a
    e.end = a + timedelta(days=1)
    e.add("RECURRENCE-ID", a - timedelta(days=1))
    return e


def to_journal(a):
    """return a journal for testing"""
    j = Journal()
    j.start = a
    j.end = a + timedelta(days=1)
    j.add("RECURRENCE-ID", a - timedelta(days=1))
    return j


def to_vDD(a):
    """Return a value type."""
    if isinstance(a, datetime):
        return vDatetime(a)
    return vDate(a)


def to_vDDDTypes(a):
    return vDDDTypes(a)


def to_vDDDLists(a):
    return vDDDLists([a])


equal_dt_pairs = [
    (date(1998, 10, 1), date(1998, 10, 1)),
    (datetime(2023, 12, 31), datetime(2023, 12, 31)),
    (
        datetime(2023, 12, 31, tzinfo=timezone.utc),
        datetime(2023, 12, 31, tzinfo=ZoneInfo("UTC")),
    ),
    (
        datetime(2023, 12, 31, tzinfo=ZoneInfo("UTC")),
        datetime(2023, 12, 31, tzinfo=ZoneInfo("UTC")),
    ),
    (
        datetime(2025, 12, 31, tzinfo=ZoneInfo("UTC")),
        datetime(2025, 12, 31, tzinfo=ZoneInfo("GMT+0")),
    ),
    (
        datetime(2025, 12, 31, 12, tzinfo=ZoneInfo("Europe/Zurich")),
        datetime(2025, 12, 31, 11, tzinfo=ZoneInfo("UTC")),
    ),
]


param_equal_dts = pytest.mark.parametrize(("d1", "d2"), equal_dt_pairs)

param_transform = pytest.mark.parametrize(
    "transform", [to_dt, to_event, to_journal, to_vDD, to_vDDDTypes, to_vDDDLists]
)


@param_equal_dts
@param_transform
def test_equality_of_equal_datetimes(d1, d2, transform):
    """Check that the values are equal."""
    a = transform(d1)
    b = transform(d2)
    assert_equal(a, b)


def assert_equal(a, b):
    """Check all equality tests."""
    assert a == b, f"1 equal: {a} == {b}"
    assert b == a, f"2 equal reversed: {b} == {a}"
    assert not a != b, f"3 not equal: {a} != {b}"  # noqa: SIM202
    assert not b != a, f"4 not equal reversed: {b} != {a}"  # noqa: SIM202
    assert bool(a) == bool(b), f"5 equal bool: {bool(a)} == {bool(b)}"
    with contextlib.suppress(TypeError):
        assert hash(a) == hash(b)


def assert_not_eq(a, b):
    """Check all equality tests."""
    assert a != b, f"1 unequal: {a} == {b}"
    assert b != a, f"2 unequal reversed: {b} == {a}"
    assert not a == b, f"3 not unequal: {a} != {b}"  # noqa: SIM201
    assert not b == a, f"4 not unequal reversed: {b} != {a}"  # noqa: SIM201


dts = [to_dt, to_vDD, to_vDDDTypes, to_vDDDLists]


@pytest.mark.parametrize("transform1", dts)
@pytest.mark.parametrize("transform2", dts)
@param_equal_dts
def test_property_times_for_date_and_datetime(d1, d2, transform1, transform2):
    """Check the equality of the date and date implementations."""
    a = transform1(d1)
    b = transform2(d2)
    assert_equal(a, b)


def test_datetime_is_in_list_representation():
    dt = datetime(2023, 12, 31)
    assert str(dt) in str(vDDDLists([dt]))


unequal_pairs = [(a, b) for a, b in equal_dt_pairs if a != b]


@pytest.mark.parametrize(("d1", "d2"), unequal_pairs)
@param_transform
def test_inequality(d1, d2, transform):
    """The values are not equal."""
    a = transform(d1)
    b = transform(d2)
    assert_not_eq(a, b)


@pytest.mark.parametrize("ddd_type", [to_vDD, to_vDDDTypes])
@param_equal_dts
def test_not_equal_if_parameters_differ(d1, d2, ddd_type):
    """If the items are equal but the parameters differ, they should not be equal."""
    d1 = ddd_type(d1)
    d2 = ddd_type(d2)
    d1.params["foo"] = "bar"
    assert_not_eq(d1, d2)


@pytest.mark.parametrize("ddd_type", [to_vDD, to_vDDDTypes])
@param_equal_dts
def test_equal_ignoring_x_params(d1, d2, ddd_type):
    """RFC 5545: Applications MUST ignore x-param and iana-param values they don't recognize."""
    d1 = ddd_type(d1)
    d2 = ddd_type(d2)
    d1.params["x-foo"] = "bar"
    assert_equal(d1, d2)


def test_list_is_not_hashable():
    """We cannot hash a list because it changes."""
    with pytest.raises(TypeError):
        hash(vDDDLists([datetime(2023, 12, 31)]))

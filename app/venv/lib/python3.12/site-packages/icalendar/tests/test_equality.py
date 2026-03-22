"""Test the equality and inequality of components."""

import contextlib
import copy

try:
    from pytz import UnknownTimeZoneError
except ImportError:

    class UnknownTimeZoneError(Exception):
        pass


from datetime import date, datetime, time, timedelta

import pytest

from icalendar import (
    Component,
    vBinary,
    vBoolean,
    vCategory,
    vDate,
    vDatetime,
    vDDDLists,
    vDDDTypes,
    vDuration,
    vGeo,
    vPeriod,
    vRecur,
    vText,
    vTime,
)


def assert_equal(actual_value, expected_value):
    """Make sure both values are equal"""
    assert actual_value == expected_value
    assert expected_value == actual_value


def assert_not_equal(actual_value, expected_value):
    """Make sure both values are not equal"""
    assert actual_value != expected_value
    assert expected_value != actual_value


def test_parsed_calendars_are_equal_if_parsed_again(source_file, tzp):
    """Ensure that a calendar equals the same calendar.

    source -> calendar -> ics -> same calendar
    """
    copy_of_calendar = source_file.__class__.from_ical(source_file.to_ical())
    assert_equal(copy_of_calendar, source_file)


def test_parsed_calendars_are_equal_if_parsed_again_jcal(source_file, tzp):
    """Ensure that a calendar equals the same calendar.

    source -> calendar -> jcal -> same calendar
    """
    if source_file.source_file == "issue_464_invalid_rdate.ics":
        pytest.skip(
            "Invalid RDATE falls back to vBroken, which can't round-trip to jCal."
        )
    copy_of_calendar = Component.from_jcal(source_file.to_jcal())
    assert_equal(copy_of_calendar, source_file)


def test_parsed_calendars_are_equal_if_from_same_source(ics_file, tzp):
    """Ensure that a calendar equals the same calendar.

    ics -> calendar
    ics -> same calendar
    """
    cal1 = ics_file.__class__.from_ical(ics_file.raw_ics)
    cal2 = ics_file.__class__.from_ical(ics_file.raw_ics)
    assert_equal(cal1, cal2)


def test_parsed_calendars_are_equal_if_from_same_source_jcal(jcal_file, tzp):
    """Ensure that a calendar equals the same calendar.

    jcal -> calendar
    jcal -> same calendar
    """
    cal1 = Component.from_jcal(jcal_file.raw_jcal)
    cal2 = Component.from_jcal(jcal_file.raw_jcal)
    assert_equal(cal1, cal2)


def test_copies_are_equal(source_file, tzp):
    """Ensure that copies are equal."""
    copy1 = source_file.copy()
    copy1.subcomponents = source_file.subcomponents
    copy2 = source_file.copy()
    copy2.subcomponents = source_file.subcomponents[:]
    assert_equal(copy1, copy2)
    assert_equal(copy1, source_file)
    assert_equal(copy2, source_file)


def test_copy_does_not_copy_subcomponents(calendars, tzp):
    """If we copy the subcomponents, assumptions around copies will be broken."""
    assert calendars.timezoned.subcomponents
    assert not calendars.timezoned.copy().subcomponents


def test_deep_copies_are_equal(source_file, tzp):
    """Ensure that deep copies are equal.

    Ignore errors when a custom time zone is used.
    This is still covered by the parsing test.
    """
    if (
        source_file.source_file == "issue_722_timezone_transition_ambiguity.ics"
        and tzp.uses_zoneinfo()
    ):
        pytest.skip("This test fails for now.")
    with contextlib.suppress(UnknownTimeZoneError):
        assert_equal(copy.deepcopy(source_file), copy.deepcopy(source_file))
    with contextlib.suppress(UnknownTimeZoneError):
        assert_equal(copy.deepcopy(source_file), source_file)


def test_vGeo():
    """Check the equality of vGeo."""
    assert_equal(vGeo(("100", "12.33")), vGeo(("100.00", "12.330")))
    assert_not_equal(vGeo(("100", "12.331")), vGeo(("100.00", "12.330")))
    assert_not_equal(vGeo(("10", "12.33")), vGeo(("100.00", "12.330")))


def test_vBinary():
    assert_equal(vBinary("asd"), vBinary("asd"))
    assert_not_equal(vBinary("asdf"), vBinary("asd"))


def test_vBoolean():
    assert_equal(vBoolean.from_ical("TRUE"), vBoolean.from_ical("TRUE"))
    assert_equal(vBoolean.from_ical("FALSE"), vBoolean.from_ical("FALSE"))
    assert_not_equal(vBoolean.from_ical("TRUE"), vBoolean.from_ical("FALSE"))


def test_vCategory():
    assert_equal(vCategory("HELLO"), vCategory("HELLO"))
    assert_equal(vCategory(["a", "b"]), vCategory(["a", "b"]))
    assert_not_equal(vCategory(["a", "b"]), vCategory(["a", "b", "c"]))


def test_vText():
    assert_equal(vText("HELLO"), vText("HELLO"))
    assert_not_equal(vText("HELLO1"), vText("HELLO"))


@pytest.mark.parametrize(
    ("v_type", "v1", "v2"),
    [
        (vDatetime, datetime(2023, 11, 1, 10, 11), datetime(2023, 11, 1, 10, 10)),
        (vDate, date(2023, 11, 1), date(2023, 10, 31)),
        (vDuration, timedelta(3, 11, 1), timedelta(23, 10, 31)),
        (
            vPeriod,
            (datetime(2023, 11, 1, 10, 11), timedelta(3, 11, 1)),
            (datetime(2023, 11, 1, 10, 11), timedelta(23, 10, 31)),
        ),
        (
            vPeriod,
            (datetime(2023, 11, 1, 10, 1), timedelta(3, 11, 1)),
            (datetime(2023, 11, 1, 10, 11), timedelta(3, 11, 1)),
        ),
        (
            vPeriod,
            (datetime(2023, 11, 1, 10, 1), datetime(2023, 11, 1, 10, 3)),
            (datetime(2023, 11, 1, 10, 1), datetime(2023, 11, 1, 10, 2)),
        ),
        (vTime, time(10, 10, 10), time(10, 10, 11)),
    ],
)
@pytest.mark.parametrize("eq", ["==", "!="])
@pytest.mark.parametrize("cls1", [0, 1])
@pytest.mark.parametrize("cls2", [0, 1])
@pytest.mark.parametrize("hash", [lambda x: x, hash])
def test_vDDDTypes_and_others(v_type, v1, v2, cls1, cls2, eq, hash):  # noqa: A002
    """Check equality and inequality."""
    t1 = (v_type, vDDDTypes)[cls1]
    t2 = (v_type, vDDDTypes)[cls2]
    if eq == "==":
        assert hash(v1) == hash(v1)
        assert hash(t1(v1)) == hash(t2(v1))
        assert hash(t1(v1)) == hash(t2(v1))
    else:
        assert hash(v1) != hash(v2)
        assert hash(t1(v1)) != hash(t2(v2))


def test_repr_vDDDTypes():
    assert "vDDDTypes" in repr(vDDDTypes(timedelta(3, 11, 1)))


vDDDLists_examples = [  # noqa: N816
    vDDDLists([]),
    vDDDLists([datetime(2023, 11, 1, 10, 1)]),
    vDDDLists([datetime(2023, 11, 1, 10, 1), date(2023, 11, 1)]),
]


@pytest.mark.parametrize("l1", vDDDLists_examples)
@pytest.mark.parametrize("l2", vDDDLists_examples)
def test_vDDDLists(l1, l2):
    """Check the equality functions of vDDDLists."""
    equal = l1 is l2
    l2 = copy.deepcopy(l2)
    assert equal == (l1 == l2)
    assert equal != (l1 != l2)


@pytest.mark.parametrize("index", [1, 2])
def test_rfc_7265_equivalence_of_example_from_appendix(calendars, index):
    """jcal and ical should be the same"""
    ical = calendars[f"rfc_7265_appendix_example_{index}_ical"]
    jcal = calendars[f"rfc_7265_appendix_example_{index}_jcal"]
    assert_equal(ical.to_jcal(), jcal.to_jcal())
    assert_equal(ical, jcal)


@pytest.mark.parametrize(
    ("v1", "v2", "equal"),
    [
        ({}, {}, True),
        ({"BYDAY": "1SU"}, {}, False),
        ({"BYDAY": "1SU"}, {"BYDAY": "1SU"}, True),
        ({"BYDAY": "1SU"}, {"BYDAY": ["1SU"]}, True),
        ({"byday": "1SU"}, {"BYDAY": "1SU"}, True),
        ({"byday": "1SU", "count": 1}, {"BYDAY": "1SU"}, False),
        ({"count": 1}, {"BYDAY": "1SU"}, False),
    ],
)
def test_v_recur_equal(v1, v2, equal):
    """Check the equality functions of vRecur."""
    recur1 = vRecur(v1)
    recur2 = vRecur(v2)
    if equal:
        assert_equal(recur1, recur2)
    else:
        assert_not_equal(recur1, recur2)

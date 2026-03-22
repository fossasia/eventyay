"""Test the identity and equality between properties."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from icalendar import vDDDTypes

try:
    import pytz
except ImportError:
    pytz = None
from copy import deepcopy

import pytest
from dateutil import tz

v_ddd_types_list = [
    vDDDTypes(
        datetime(
            year=2022,
            month=7,
            day=22,
            hour=12,
            minute=7,
            tzinfo=ZoneInfo("Europe/London"),
        )
    ),
    vDDDTypes(datetime(year=2022, month=7, day=22, hour=12, minute=7)),
    vDDDTypes(datetime(year=2022, month=7, day=22, hour=12, minute=7, tzinfo=tz.UTC)),
    vDDDTypes(date(year=2022, month=7, day=22)),
    vDDDTypes(date(year=2022, month=7, day=23)),
    vDDDTypes(time(hour=22, minute=7, second=2)),
]
if pytz:
    v_ddd_types_list.append(
        vDDDTypes(
            pytz.timezone("EST").localize(
                datetime(year=2022, month=7, day=22, hour=12, minute=7)
            )
        ),
    )


def identity(x):
    return x


@pytest.mark.parametrize(
    "transform",
    [
        deepcopy,
        identity,
        hash,
    ],
)
@pytest.mark.parametrize("v_type", v_ddd_types_list)
@pytest.mark.parametrize("other", v_ddd_types_list)
def test_vDDDTypes_equivalance(transform, v_type, other):
    if v_type is other:
        assert transform(v_type) == transform(other), (
            f"identity implies equality: {transform.__name__}()"
        )
        assert transform(v_type) == transform(other), (
            f"identity implies equality: {transform.__name__}()"
        )
    else:
        assert transform(v_type) != transform(other), (
            f"expected inequality: {transform.__name__}()"
        )
        assert transform(v_type) != transform(other), (
            f"expected inequality: {transform.__name__}()"
        )


@pytest.mark.parametrize("v_type", v_ddd_types_list)
def test_inequality_with_different_types(v_type):
    assert v_type != 42
    assert v_type != "test"

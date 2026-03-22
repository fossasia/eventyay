import datetime

import pytest

from icalendar.prop import (
    vBoolean,
    vCalAddress,
    vCategory,
    vDatetime,
    vDuration,
    vFloat,
    vFrequency,
    vGeo,
    vInline,
    vInt,
    vMonth,
    vRecur,
    vText,
    vUri,
    vUTCOffset,
    vWeekday,
)


def test_param_vCategory():
    obj = vCategory(["Work", "Personal"], params={"SOME_PARAM": "VALUE"})
    assert isinstance(obj, vCategory)
    assert obj.params["SOME_PARAM"] == "VALUE"


def test_param_vCalAddress():
    obj = vCalAddress("mailto:jane_doe@example.com", params={"SOME_PARAM": "VALUE"})
    assert isinstance(obj, vCalAddress)
    assert obj.params["SOME_PARAM"] == "VALUE"


def test_param_vWeekday():
    obj = vWeekday("2FR", params={"SOME_PARAM": "VALUE"})
    assert isinstance(obj, vWeekday)
    assert obj.params["SOME_PARAM"] == "VALUE"


def test_param_vBoolean():
    obj = vBoolean(True, params={"SOME_PARAM": "VALUE"})
    assert isinstance(obj, vBoolean)
    assert obj.params["SOME_PARAM"] == "VALUE"


def test_param_vDuration():
    td = datetime.timedelta(days=15, seconds=18020)
    obj = vDuration(td, params={"SOME_PARAM": "VALUE"})
    assert isinstance(obj, vDuration)
    assert obj.params["SOME_PARAM"] == "VALUE"


def test_param_vFloat():
    obj = vFloat("1.333", params={"SOME_PARAM": "VALUE"})
    assert isinstance(obj, vFloat)
    assert obj.params["SOME_PARAM"] == "VALUE"


def test_param_vGeo():
    obj = vGeo((37.386013, -122.082932), params={"SOME_PARAM": "VALUE"})
    assert isinstance(obj, vGeo)
    assert obj.params["SOME_PARAM"] == "VALUE"


def test_param_vInt():
    obj = vInt("87", params={"SOME_PARAM": "VALUE"})
    assert isinstance(obj, vInt)
    assert obj.params["SOME_PARAM"] == "VALUE"


def test_param_vInline():
    obj = vInline("sometxt", params={"SOME_PARAM": "VALUE"})
    assert isinstance(obj, vInline)
    assert obj.params["SOME_PARAM"] == "VALUE"


def test_param_vText():
    obj = vText("sometxt", params={"SOME_PARAM": "VALUE"})
    assert isinstance(obj, vText)
    assert obj.params["SOME_PARAM"] == "VALUE"


def test_param_vMonth():
    obj = vMonth(1, params={"SOME_PARAM": "VALUE"})
    assert isinstance(obj, vMonth)
    assert obj.params["SOME_PARAM"] == "VALUE"


def test_vMonth_validation():
    """Test validation of vMonth with leap month format."""
    # Valid cases
    assert vMonth(1) == 1
    assert vMonth("1") == 1
    assert vMonth("5L") == 5
    assert vMonth("5L").leap

    # Invalid cases
    with pytest.raises(ValueError, match="Invalid month"):
        vMonth("L")  # Just L without digits

    with pytest.raises(ValueError, match="Invalid month"):
        vMonth("1LL")  # Double L

    with pytest.raises(ValueError, match="Invalid month"):
        vMonth("abc")  # Letters not in valid format

    with pytest.raises(ValueError, match="Invalid month"):
        vMonth("")  # Empty string


def test_param_vUTCOffset():
    obj = vUTCOffset(
        datetime.timedelta(days=-1, seconds=68400), params={"SOME_PARAM": "VALUE"}
    )
    assert isinstance(obj, vUTCOffset)
    assert obj.params["SOME_PARAM"] == "VALUE"


def test_param_vFrequency():
    obj = vFrequency("DAILY", params={"SOME_PARAM": "VALUE"})
    assert isinstance(obj, vFrequency)
    assert obj.params["SOME_PARAM"] == "VALUE"


def test_param_vRecur():
    obj = vRecur({"FREQ": ["DAILY"], "COUNT": [10]}, params={"SOME_PARAM": "VALUE"})
    assert isinstance(obj, vRecur)
    assert obj.params["SOME_PARAM"] == "VALUE"


def test_param_vDatetime():
    dt = datetime.datetime(2025, 3, 16, 14, 30, 0, tzinfo=datetime.timezone.utc)
    obj = vDatetime(dt, params={"SOME_PARAM": "VALUE"})
    assert isinstance(obj, vDatetime)
    assert obj.params["SOME_PARAM"] == "VALUE"


def test_param_vUri():
    obj = vUri("WWW.WESBITE.COM", params={"SOME_PARAM": "VALUE"})
    assert isinstance(obj, vUri)
    assert obj.params["SOME_PARAM"] == "VALUE"

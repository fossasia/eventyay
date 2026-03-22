"""This tests the switch to different timezone implementations.

These are mostly located in icalendar.timezone.
"""

try:
    import pytz

    from icalendar.timezone.pytz import PYTZ
except ImportError:
    pytz = None
import copy
import pickle
from datetime import datetime

import pytest
from dateutil.rrule import MONTHLY, rrule
from dateutil.tz.tz import _tzicalvtz

from icalendar.timezone.zoneinfo import ZONEINFO, zoneinfo

if pytz:
    PYTZ_TIMEZONES = pytz.all_timezones
    TZP_ = [PYTZ(), ZONEINFO()]
    NEW_TZP_NAME = ["pytz", "zoneinfo"]
else:
    PYTZ_TIMEZONES = []
    TZP_ = [ZONEINFO()]
    NEW_TZP_NAME = ["zoneinfo"]


@pytest.mark.parametrize(
    "tz_name", PYTZ_TIMEZONES + list(zoneinfo.available_timezones())
)
@pytest.mark.parametrize("tzp_", TZP_)
def test_timezone_names_are_known(tz_name, tzp_):
    """Make sure that all timezones are understood."""
    if tz_name in ("Factory", "localtime"):
        pytest.skip()
    assert tzp_.knows_timezone_id(tz_name), (
        f"{tzp_.__class__.__name__} should know {tz_name}"
    )


@pytest.mark.parametrize("func", [pickle.dumps, copy.copy, copy.deepcopy])
@pytest.mark.parametrize(
    "obj",
    [
        _tzicalvtz("id"),
        rrule(freq=MONTHLY, count=4, dtstart=datetime(2028, 10, 1), cache=True),
    ],
)
def test_can_pickle_timezone(func, tzp, obj):
    """Check that we can serialize and copy timezones."""
    func(obj)


def test_copied_rrule_is_the_same():
    """When we copy an rrule, we want it to be the same after this."""
    r = rrule(freq=MONTHLY, count=4, dtstart=datetime(2028, 10, 1), cache=True)
    assert str(copy.deepcopy(r)) == str(r)


def test_tzp_properly_switches(tzp, tzp_name):
    """We want the default implementation to switch."""
    assert (tzp_name == "pytz") == tzp.uses_pytz()


def test_tzp_is_pytz_only(tzp, tzp_name, pytz_only):
    """We want the default implementation to switch."""
    assert tzp_name == "pytz"
    assert tzp.uses_pytz()


def test_cache_reuse_timezone_cache(tzp, timezones):
    """Make sure we do not cache the timezones twice and change them."""
    tzp.cache_timezone_component(timezones.pacific_fiji)
    tzp1 = tzp.timezone("custom_Pacific/Fiji")
    assert tzp1 is tzp.timezone("custom_Pacific/Fiji")
    tzp.cache_timezone_component(timezones.pacific_fiji)
    assert tzp1 is tzp.timezone("custom_Pacific/Fiji"), "Cache is not replaced."


@pytest.mark.parametrize("new_tzp_name", NEW_TZP_NAME)
def test_cache_is_emptied_when_tzp_is_switched(tzp, timezones, new_tzp_name):
    """Make sure we do not reuse the timezones created when we switch the provider."""
    tzp.cache_timezone_component(timezones.pacific_fiji)
    tz1 = tzp.timezone("custom_Pacific/Fiji")
    tzp.use(new_tzp_name)
    tzp.cache_timezone_component(timezones.pacific_fiji)
    tz2 = tzp.timezone("custom_Pacific/Fiji")
    assert tz1 is not tz2


def test_invalid_name(tzp):
    """Check that the provider name is OK."""
    provider = "invalid_provider"
    with pytest.raises(ValueError) as e:
        tzp.use(provider)
    # f"Unknown provider {provider}. Use 'pytz' or 'zoneinfo'."
    message = e.value.args[0]
    assert f"Unknown provider {provider}." in message
    assert "zoneinfo" in message
    assert "pytz" in message

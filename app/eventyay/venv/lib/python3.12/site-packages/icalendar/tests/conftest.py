"""Test configuration"""

import itertools
import sys
import uuid
import zoneinfo
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from dateutil import tz

from icalendar import (
    Alarm,
    Availability,
    Calendar,
    Component,
    ComponentFactory,
    Event,
    Timezone,
    Todo,
    TypesFactory,
    prop,
    vUTCOffset,
)
from icalendar.tests.data import PROPERTY_NAMES
from icalendar.timezone import TZP
from icalendar.timezone import tzp as _tzp

from . import timezone_ids

try:
    import pytz
except ImportError:
    pytz = None

HAS_PYTZ = pytz is not None
if HAS_PYTZ:
    PYTZ_UTC = [
        pytz.utc,
        pytz.timezone("UTC"),
    ]
    PYTZ_IN_TIMEZONE = [
        lambda dt, tzname: pytz.timezone(tzname).localize(dt),
    ]
    PYTZ_TZP = ["pytz"]
else:
    PYTZ_UTC = []
    PYTZ_IN_TIMEZONE = []
    PYTZ_TZP = []


class DataSource:
    """A collection of parsed ICS elements (e.g calendars, timezones, events)"""

    extensions = [".ics", ".jcal"]

    def __init__(self, data_source_folder: Path, parser):
        self._parser = parser
        self._data_source_folder = data_source_folder

    def keys(self):
        """Return all the files that could be used."""
        return [
            p.stem
            for p in self._data_source_folder.iterdir()
            if p.suffix.lower() in self.extensions
        ]

    def __getitem__(self, attribute):
        """Parse a file and return the result stored in the attribute."""
        extensions = self.extensions
        if "." in attribute:
            # we have a file ending
            attribute, extension = attribute.rsplit(".", 1)
            extensions = ["." + extension]
        for extension in extensions:
            source_file = attribute + extension
            source_path = self._data_source_folder / source_file
            if source_path.is_file():
                break
        if not source_path.is_file():
            # usually only raised if the test is wrong
            raise AttributeError(
                f"{attribute} does not exist with these extensions: {', '.join(extensions)}."
            )
        if extension == ".jcal":
            raw_jcal = source_path.read_text()
            source = Component.from_jcal(raw_jcal)
            raw_ics = None
        else:
            raw_ics = source_path.read_bytes()
            source = self._parser(raw_ics)
            raw_jcal = None
        if not isinstance(source, list):
            source.raw_ics = raw_ics
            source.raw_jcal = raw_jcal
            source.source_file = source_file
        self.__dict__[attribute] = source  # required for speed but creates side effects
        return source

    def __contains__(self, key):
        """key in self.keys()"""
        key = key.rsplit(".", 1)[0]
        return key in self.keys()

    def __getattr__(self, key):
        return self[key]

    def __repr__(self):
        return repr(self.__dict__)

    @property
    def multiple(self):
        """Return a list of all components parsed."""
        return self.__class__(
            self._data_source_folder, lambda data: self._parser(data, multiple=True)
        )


HERE = Path(__file__).parent
CALENDARS_FOLDER = HERE / "calendars"
TIMEZONES_FOLDER = HERE / "timezones"
EVENTS_FOLDER = HERE / "events"
ALARMS_FOLDER = HERE / "alarms"
AVAILABILITIES_FOLDER = HERE / "availabilities"
TODOS_FOLDER = HERE / "todos"


@pytest.fixture(scope="module")
def calendars(tzp):
    return DataSource(CALENDARS_FOLDER, Calendar.from_ical)


@pytest.fixture(scope="module")
def timezones(tzp):
    return DataSource(TIMEZONES_FOLDER, Timezone.from_ical)


@pytest.fixture(scope="module")
def events(tzp):
    return DataSource(EVENTS_FOLDER, Event.from_ical)


@pytest.fixture(scope="module")
def alarms(tzp):
    return DataSource(ALARMS_FOLDER, Alarm.from_ical)


@pytest.fixture(scope="module")
def availabilities(tzp):
    return DataSource(AVAILABILITIES_FOLDER, Availability.from_ical)


@pytest.fixture(scope="module")
def todos(tzp):
    return DataSource(TODOS_FOLDER, Todo.from_ical)


@pytest.fixture(
    params=PYTZ_UTC + [ZoneInfo("UTC"), tz.UTC, tz.gettz("UTC"), timezone.utc]
)
def utc(request, tzp):
    return request.param


@pytest.fixture(
    params=PYTZ_IN_TIMEZONE
    + [
        lambda dt, tzname: dt.replace(tzinfo=tz.gettz(tzname)),
        lambda dt, tzname: dt.replace(tzinfo=ZoneInfo(tzname)),
    ]
)
def in_timezone(request, tzp):
    return request.param


FUZZ_TESTCASES_BROKEN_CALENDARS = "fuzz_testcase"

# exclude broken calendars here
BROKEN_SOURCE_FILES = (
    "big_bad_calendar.ics",
    "issue_104_broken_calendar.ics",
    "small_bad_calendar.ics",
    "multiple_calendar_components.ics",
    "pr_480_summary_with_colon.ics",
    "parsing_error_in_UTC_offset.ics",
    "parsing_error.ics",
)
SOURCE_FILES = [
    file.name
    for file in itertools.chain(
        CALENDARS_FOLDER.iterdir(), TIMEZONES_FOLDER.iterdir(), EVENTS_FOLDER.iterdir()
    )
    if file.name not in BROKEN_SOURCE_FILES
    and file.suffix in (".ics", ".jcal")
    and FUZZ_TESTCASES_BROKEN_CALENDARS not in file.name
]

ICS_FILES = [
    file.name
    for file in itertools.chain(
        CALENDARS_FOLDER.iterdir(), TIMEZONES_FOLDER.iterdir(), EVENTS_FOLDER.iterdir()
    )
    if file.name not in BROKEN_SOURCE_FILES
    and file.suffix == ".ics"
    and FUZZ_TESTCASES_BROKEN_CALENDARS not in file.name
]

JCAL_FILES = [
    file.name
    for file in itertools.chain(
        CALENDARS_FOLDER.iterdir(), TIMEZONES_FOLDER.iterdir(), EVENTS_FOLDER.iterdir()
    )
    if file.name not in BROKEN_SOURCE_FILES
    and file.suffix == ".jcal"
    and FUZZ_TESTCASES_BROKEN_CALENDARS not in file.name
]


def get_source_file(calendars, timezones, events, request) -> Component:
    source_file = request.param
    print("example file:", source_file)
    for data in calendars, timezones, events:
        if source_file in data:
            return data[source_file]
    raise ValueError(f"Could not find file {source_file}.")


@pytest.fixture(params=SOURCE_FILES)
def source_file(tzp, calendars, timezones, events, request) -> Component:
    """An example file.

    source_file.raw_ics - bytes if .ics file
    source_file.raw_jcal - str if .jcal file

    """
    return get_source_file(calendars, timezones, events, request)


@pytest.fixture(params=ICS_FILES)
def ics_file(tzp, calendars, timezones, events, request) -> Component:
    """An example .ica file.

    source_file.raw_ics - bytes
    source_file.raw_jcal - None
    """
    return get_source_file(calendars, timezones, events, request)


@pytest.fixture(params=JCAL_FILES)
def jcal_file(tzp, calendars, timezones, events, request) -> Component:
    """An example .jcal file.

    source_file.raw_ics - None
    source_file.raw_jcal - str
    """
    return get_source_file(calendars, timezones, events, request)


FUZZ_V1 = [
    key
    for key in CALENDARS_FOLDER.iterdir()
    if FUZZ_TESTCASES_BROKEN_CALENDARS in str(key)
]


@pytest.fixture(params=FUZZ_V1)
def fuzz_v1_calendar_path(request):
    """Clusterfuzz calendars."""
    return request.param


@pytest.fixture
def types_factory():
    """Return a new types factory."""
    return TypesFactory()


@pytest.fixture
def component_factory():
    """Return a new types factory."""
    return ComponentFactory()


@pytest.fixture
def x_sometime(types_factory):
    """Map x_sometime to time"""
    types_factory.types_map["X-SOMETIME"] = "time"
    yield
    types_factory.types_map.pop("X-SOMETIME")


@pytest.fixture
def factory():
    """Return a new component factory."""
    return ComponentFactory()


@pytest.fixture
def vUTCOffset_ignore_exceptions():
    vUTCOffset.ignore_exceptions = True
    yield
    vUTCOffset.ignore_exceptions = False


@pytest.fixture
def event_component(tzp):
    """Return an event component."""
    c = Component()
    c.name = "VEVENT"
    return c


@pytest.fixture
def c(tzp):
    """Return an empty component."""
    return Component()


comp = c


@pytest.fixture
def calendar_component(tzp):
    """Return an empty component."""
    c = Component()
    c.name = "VCALENDAR"
    return c


@pytest.fixture
def dont_validate_new():
    """Remove validation for new() of components."""
    value = Component._validate_new
    Component._validate_new = False
    yield
    Component._validate_new = value


@pytest.fixture
def filled_event_component(c, calendar_component):
    """Return an event with some values and add it to calendar_component."""
    e = Component(summary="A brief history of time")
    e.name = "VEVENT"
    e.add("dtend", "20000102T000000", encode=0)
    e.add("dtstart", "20000101T000000", encode=0)
    calendar_component.add_component(e)
    return e


@pytest.fixture
def calendar_with_resources(tzp):
    c = Calendar()
    c["resources"] = 'Chair, Table, "Room: 42"'
    return c


@pytest.fixture(scope="module")
def tzp(tzp_name) -> Generator[TZP, None, None]:
    """The timezone provider."""
    _tzp.use(tzp_name)
    yield _tzp
    _tzp.use_default()


@pytest.fixture(params=PYTZ_TZP + ["zoneinfo"])
def other_tzp(request, tzp):
    """This is annother timezone provider.

    The purpose here is to cross test: pytz <-> zoneinfo.
    tzp as parameter makes sure we test the cross product.
    """
    return TZP(request.param)


@pytest.fixture
def pytz_only(tzp, tzp_name) -> str:
    """Skip tests that are not running under pytz."""
    assert tzp.uses_pytz()
    return tzp_name


@pytest.fixture
def zoneinfo_only(tzp, request, tzp_name) -> str:
    """Skip tests that are not running under zoneinfo."""
    assert tzp.uses_zoneinfo()
    return tzp_name


@pytest.fixture
def no_pytz(tzp_name) -> str:
    """Do not run tests with pytz."""
    assert tzp_name != "pytz"
    return tzp_name


@pytest.fixture
def no_zoneinfo(tzp_name) -> str:
    """Do not run tests with zoneinfo."""
    assert tzp_name != "zoneinfo"
    return tzp_name


def pytest_generate_tests(metafunc):
    """Parametrize without skipping:

    tzp_name will be parametrized according to the use of
    - pytz_only
    - zoneinfo_only
    - no_pytz
    - no_zoneinfo

    See https://docs.pytest.org/en/6.2.x/example/parametrize.html#deferring-the-setup-of-parametrized-resources
    """
    if "tzp_name" in metafunc.fixturenames:
        tzp_names = PYTZ_TZP + ["zoneinfo"]
        if "zoneinfo_only" in metafunc.fixturenames:
            tzp_names = ["zoneinfo"]
        if "pytz_only" in metafunc.fixturenames:
            tzp_names = PYTZ_TZP
        assert not (
            "zoneinfo_only" in metafunc.fixturenames
            and "pytz_only" in metafunc.fixturenames
        ), "Use pytz_only or zoneinfo_only but not both!"
        for name in ["pytz", "zoneinfo"]:
            if f"no_{name}" in metafunc.fixturenames and name in tzp_names:
                tzp_names.remove(name)
        metafunc.parametrize("tzp_name", tzp_names, scope="module")


class DoctestZoneInfo(ZoneInfo):
    """Constent ZoneInfo representation for tests."""

    def __repr__(self):
        return f"ZoneInfo(key={self.key!r})"


def doctest_print(*args):
    """doctest print"""
    args = [arg.decode("UTF-8") if isinstance(arg, bytes) else arg for arg in args]
    print(*(str(arg).strip().replace("\r\n", "\n").replace("\r", "\n") for arg in args))


def doctest_import(name, *args, **kw):
    """Replace the import mechanism to skip the whole doctest if we import pytz."""
    if name == "pytz":
        return pytz
    return __import__(name, *args, **kw)


NOW = datetime(2025, 5, 17, 8, 6, 12)
NOW_UTC = NOW.replace(tzinfo=timezone.utc)
UID_DEFAULT = "d755cef5-2311-46ed-a0e1-6733c9e15c63"


@pytest.fixture
def test_uid() -> str:
    """The UID that tests always create."""
    return UID_DEFAULT


@pytest.fixture(autouse=True)
def fixed_env(monkeypatch):
    """Create a fixed test environment for the functions that are time and randomness dependent."""
    # uuid is fixed for all tests
    uid = uuid.UUID(UID_DEFAULT, version=4)
    monkeypatch.setattr(uuid, "uuid4", lambda: uid)
    # now is fixed
    monkeypatch.setattr(Component, "_utc_now", staticmethod(lambda: NOW_UTC))


@pytest.fixture
def env_for_doctest(monkeypatch):
    """Modify the environment to make doctests run."""
    monkeypatch.setitem(sys.modules, "zoneinfo", zoneinfo)
    monkeypatch.setattr(zoneinfo, "ZoneInfo", DoctestZoneInfo)
    from icalendar.timezone.zoneinfo import ZONEINFO

    monkeypatch.setattr(ZONEINFO, "utc", zoneinfo.ZoneInfo("UTC"))
    return {"print": doctest_print}


@pytest.fixture(params=timezone_ids.TZIDS)
def tzid(request: pytest.FixtureRequest) -> str:
    """Return a timezone id to be used with pytz or zoneinfo.

    This goes through all the different timezones possible.
    """
    return request.param


@pytest.fixture(params=PROPERTY_NAMES)
def v_prop_name(request):
    """Names of property types that occur as a property of a component."""
    return request.param


@pytest.fixture
def v_prop(v_prop_name):
    """Property types that occur as a property of a component."""
    return getattr(prop, v_prop_name)


@pytest.fixture
def v_prop_example(v_prop) -> prop.VPROPERTY:
    return v_prop.examples()[0]


@pytest.fixture
def mock():
    """A mock."""
    return Mock()

import itertools
import re
from datetime import datetime, timedelta

import pytest

import icalendar
from icalendar import prop
from icalendar.cal.calendar import Calendar
from icalendar.cal.component import Component
from icalendar.cal.event import Event
from icalendar.cal.journal import Journal
from icalendar.timezone import tzid_from_dt


def test_cal_Component(calendar_component):
    """A component is like a dictionary with extra methods and attributes."""
    assert calendar_component
    assert calendar_component.is_empty()


def test_nonempty_calendar_component(calendar_component):
    """Every key defines a property.A property can consist of either a
    single item. This can be set with a single value...
    """
    calendar_component["prodid"] = "-//max m//icalendar.mxm.dk/"
    assert not calendar_component.is_empty()
    assert calendar_component == Calendar({"PRODID": "-//max m//icalendar.mxm.dk/"})

    # or with a list
    calendar_component["ATTENDEE"] = ["Max M", "Rasmussen"]
    assert calendar_component == Calendar(
        {"ATTENDEE": ["Max M", "Rasmussen"], "PRODID": "-//max m//icalendar.mxm.dk/"}
    )


def test_add_multiple_values(event_component):
    """add multiple values to a property.

    If you use the add method you don't have to considder if a value is
    a list or not.
    """
    # add multiple values at once
    event_component.add("attendee", ["test@test.com", "test2@test.com"])

    # or add one per line
    event_component.add("attendee", "maxm@mxm.dk")
    event_component.add("attendee", "test@example.dk")

    # add again multiple values at once to very concatenaton of lists
    event_component.add("attendee", ["test3@test.com", "test4@test.com"])

    assert event_component == Event(
        {
            "ATTENDEE": [
                prop.vCalAddress("test@test.com"),
                prop.vCalAddress("test2@test.com"),
                prop.vCalAddress("maxm@mxm.dk"),
                prop.vCalAddress("test@example.dk"),
                prop.vCalAddress("test3@test.com"),
                prop.vCalAddress("test4@test.com"),
            ]
        }
    )


def test_get_content_directly(c):
    """You can get the values back directly ..."""
    c.add("prodid", "-//my product//")
    assert c["prodid"] == prop.vText("-//my product//")
    # ... or decoded to a python type
    assert c.decoded("prodid") == "-//my product//"


def test_get_default_value(c):
    """With default values for non existing properties"""
    assert c.decoded("version", "No Version") == "No Version"


def test_default_list_example(c):
    c.add("rdate", [datetime(2013, 3, 28), datetime(2013, 3, 27)])
    assert isinstance(c.decoded("rdate"), prop.vDDDLists)


def test_render_component(calendar_component):
    """The component can render itself in the RFC 5545 format."""
    calendar_component.add("attendee", "Max M")
    assert (
        calendar_component.to_ical()
        == b"BEGIN:VCALENDAR\r\nATTENDEE:Max M\r\nEND:VCALENDAR\r\n"
    )


def test_nested_component_event_ics(filled_event_component):
    """Check the ical string of the event component."""
    assert filled_event_component.to_ical() == (
        b"BEGIN:VEVENT\r\nDTEND:20000102T000000\r\n"
        b"DTSTART:20000101T000000\r\nSUMMARY:A brief history of time\r"
        b"\nEND:VEVENT\r\n"
    )


def test_nested_components(calendar_component, filled_event_component):
    """Components can be nested, so You can add a subcomponent. Eg a calendar
    holds events."""
    assert calendar_component.subcomponents == [
        Event(
            {
                "DTEND": "20000102T000000",
                "DTSTART": "20000101T000000",
                "SUMMARY": "A brief history of time",
            }
        )
    ]


def test_walk_filled_calendar_component(calendar_component, filled_event_component):
    """We can walk over nested componentes with the walk method."""
    assert [i.name for i in calendar_component.walk()] == ["VCALENDAR", "VEVENT"]


def test_filter_walk(calendar_component, filled_event_component):
    """We can also just walk over specific component types, by filtering
    them on their name."""
    assert [i.name for i in calendar_component.walk("VEVENT")] == ["VEVENT"]
    assert [i["dtstart"] for i in calendar_component.walk("VEVENT")] == [
        "20000101T000000"
    ]


def test_recursive_property_items(calendar_component, filled_event_component):
    """We can enumerate property items recursively with the property_items
    method."""
    calendar_component.add("attendee", "Max M")
    assert calendar_component.property_items() == [
        ("BEGIN", b"VCALENDAR"),
        ("ATTENDEE", prop.vCalAddress("Max M")),
        ("BEGIN", b"VEVENT"),
        ("DTEND", "20000102T000000"),
        ("DTSTART", "20000101T000000"),
        ("SUMMARY", "A brief history of time"),
        ("END", b"VEVENT"),
        ("END", b"VCALENDAR"),
    ]


def test_flat_property_items(calendar_component, filled_event_component):
    """We can also enumerate property items just under the component."""
    calendar_component.add("attendee", "Max M")
    assert calendar_component.property_items(recursive=False) == [
        ("BEGIN", b"VCALENDAR"),
        ("ATTENDEE", prop.vCalAddress("Max M")),
        ("END", b"VCALENDAR"),
    ]


def test_flat_property_items_2(filled_event_component):
    """Flat enumeration on the event."""
    assert filled_event_component.property_items(recursive=False) == [
        ("BEGIN", b"VEVENT"),
        ("DTEND", "20000102T000000"),
        ("DTSTART", "20000101T000000"),
        ("SUMMARY", "A brief history of time"),
        ("END", b"VEVENT"),
    ]


def test_indent():
    """Text fields which span multiple mulitple lines require proper indenting"""
    c = Calendar()
    c["description"] = "Paragraph one\n\nParagraph two"
    assert c.to_ical() == (
        b"BEGIN:VCALENDAR\r\nDESCRIPTION:Paragraph one\\n\\nParagraph two"
        b"\r\nEND:VCALENDAR\r\n"
    )


def test_INLINE_properties(calendar_with_resources):
    """INLINE properties have their values on one property line. Note the
    double quoting of the value with a colon in it.
    """
    assert calendar_with_resources == Calendar(
        {"RESOURCES": 'Chair, Table, "Room: 42"'}
    )
    assert calendar_with_resources.to_ical() == (
        b'BEGIN:VCALENDAR\r\nRESOURCES:Chair\\, Table\\, "Room: 42"\r\n'
        b"END:VCALENDAR\r\n"
    )


def test_get_inline(calendar_with_resources):
    """The inline values must be handled by the get_inline() and
    set_inline() methods.
    """
    assert calendar_with_resources.get_inline("resources", decode=0) == [
        "Chair",
        "Table",
        "Room: 42",
    ]


def test_get_inline_decoded(calendar_with_resources):
    """These can also be decoded"""
    assert calendar_with_resources.get_inline("resources", decode=1) == [
        b"Chair",
        b"Table",
        b"Room: 42",
    ]


def test_set_inline(calendar_with_resources):
    """You can set them directly ..."""
    calendar_with_resources.set_inline(
        "resources", ["A", "List", "of", "some, recources"], encode=1
    )
    assert calendar_with_resources["resources"] == 'A,List,of,"some, recources"'
    assert calendar_with_resources.get_inline("resources", decode=0) == [
        "A",
        "List",
        "of",
        "some, recources",
    ]


def test_inline_free_busy_inline(c):
    c["freebusy"] = (
        "19970308T160000Z/PT3H,19970308T200000Z/PT1H,19970308T230000Z/19970309T000000Z"
    )
    assert c.get_inline("freebusy", decode=0) == [
        "19970308T160000Z/PT3H",
        "19970308T200000Z/PT1H",
        "19970308T230000Z/19970309T000000Z",
    ]

    freebusy = c.get_inline("freebusy", decode=1)
    assert isinstance(freebusy[0][0], datetime)
    assert isinstance(freebusy[0][1], timedelta)


def test_cal_Component_add(comp, tzp):
    """Test the for timezone correctness: dtstart should preserve it's
    timezone, created, dtstamp and last-modified must be in UTC.
    """
    comp.add("dtstart", tzp.localize(datetime(2010, 10, 10, 10, 0, 0), "Europe/Vienna"))
    comp.add("created", datetime(2010, 10, 10, 12, 0, 0))
    comp.add("dtstamp", tzp.localize(datetime(2010, 10, 10, 14, 0, 0), "Europe/Vienna"))
    comp.add("last-modified", tzp.localize_utc(datetime(2010, 10, 10, 16, 0, 0)))

    lines = comp.to_ical().splitlines()
    assert b"DTSTART;TZID=Europe/Vienna:20101010T100000" in lines
    assert b"CREATED:20101010T120000Z" in lines
    assert b"DTSTAMP:20101010T120000Z" in lines
    assert b"LAST-MODIFIED:20101010T160000Z" in lines


def test_cal_Component_add_no_reencode(comp):
    """Already encoded values should not be re-encoded."""
    comp.add("ATTACH", "me")
    comp.add("ATTACH", "you", encode=False)
    binary = prop.vBinary("us")
    comp.add("ATTACH", binary)

    assert comp["ATTACH"] == ["me", "you", binary]


def test_cal_Component_add_property_parameter(comp):
    """Test the for timezone correctness: dtstart should preserve it's
    timezone, crated, dtstamp and last-modified must be in UTC.
    """
    comp.add("X-TEST-PROP", "tryout.", parameters={"prop1": "val1", "prop2": "val2"})
    lines = comp.to_ical().splitlines()
    assert b"X-TEST-PROP;PROP1=val1;PROP2=val2:tryout." in lines


comp_prop = pytest.mark.parametrize(
    ("component_name", "property_name"),
    [
        ("VEVENT", "DTSTART"),
        ("VEVENT", "DTEND"),
        ("VEVENT", "RECURRENCE-ID"),
        ("VTODO", "DUE"),
    ],
)


@comp_prop
def test_cal_Component_from_ical(component_name, property_name, tzp):
    """Check for proper handling of TZID parameter of datetime properties"""
    component_str = "BEGIN:" + component_name + "\n"
    component_str += property_name + ";TZID=America/Denver:"
    component_str += "20120404T073000\nEND:" + component_name
    component = Component.from_ical(component_str)
    assert tzid_from_dt(component[property_name].dt) == "America/Denver"


@comp_prop
def test_cal_Component_from_ical_2(component_name, property_name, tzp):
    """Check for proper handling of TZID parameter of datetime properties"""
    component_str = "BEGIN:" + component_name + "\n"
    component_str += property_name + ":"
    component_str += "20120404T073000\nEND:" + component_name
    component = Component.from_ical(component_str)
    assert component[property_name].dt.tzinfo is None


def test_cal_Component_to_ical_property_order():
    component_str = [
        b"BEGIN:VEVENT",
        b"DTSTART:19970714T170000Z",
        b"DTEND:19970715T035959Z",
        b"SUMMARY:Bastille Day Party",
        b"END:VEVENT",
    ]
    component = Component.from_ical(b"\r\n".join(component_str))

    sorted_str = component.to_ical().splitlines()
    assert sorted_str != component_str
    assert set(sorted_str) == set(component_str)

    preserved_str = component.to_ical(sorted=False).splitlines()
    assert preserved_str == component_str


def test_cal_Component_to_ical_parameter_order():
    component_str = [
        b"BEGIN:VEVENT",
        b"X-FOOBAR;C=one;A=two;B=three:helloworld.",
        b"END:VEVENT",
    ]
    component = Component.from_ical(b"\r\n".join(component_str))

    sorted_str = component.to_ical().splitlines()
    assert sorted_str[0] == component_str[0]
    assert sorted_str[1] == b"X-FOOBAR;A=two;B=three;C=one:helloworld."
    assert sorted_str[2] == component_str[2]

    preserved_str = component.to_ical(sorted=False).splitlines()
    assert preserved_str == component_str


@pytest.fixture
def repr_example(c):
    class ReprExample:
        component = c
        component["key1"] = "value1"
        calendar = Calendar()
        calendar["key1"] = "value1"
        event = Event()
        event["key1"] = "value1"
        nested = Component(key1="VALUE1")
        nested.add_component(component)
        nested.add_component(calendar)

    return ReprExample


def test_repr_component(repr_example):
    """Test correct class representation."""
    assert re.match(r"Component\({u?'KEY1': u?'value1'}\)", str(repr_example.component))


def test_repr_calendar(repr_example):
    assert re.match(r"VCALENDAR\({u?'KEY1': u?'value1'}\)", str(repr_example.calendar))


def test_repr_event(repr_example):
    assert re.match(r"VEVENT\({u?'KEY1': u?'value1'}\)", str(repr_example.event))


def test_nested_components_2(repr_example):
    """Representation of nested Components"""
    repr_example.calendar.add_component(repr_example.event)
    print(repr_example.nested)
    assert re.match(
        r"Component\({u?'KEY1': u?'VALUE1'}, "
        r"Component\({u?'KEY1': u?'value1'}\), "
        r"VCALENDAR\({u?'KEY1': u?'value1'}, "
        r"VEVENT\({u?'KEY1': u?'value1'}\)\)\)",
        str(repr_example.nested),
    )


def test_component_factory_VEVENT(factory):
    """Check the events in the component factory"""
    component = factory["VEVENT"]
    event = component(dtstart="19700101")
    assert event.to_ical() == b"BEGIN:VEVENT\r\nDTSTART:19700101\r\nEND:VEVENT\r\n"


def test_component_factory_VCALENDAR(factory):
    """Check the VCALENDAR in the factory."""
    assert factory.get("VCALENDAR") == icalendar.cal.Calendar


def test_minimal_calendar_component_with_one_event():
    """Setting up a minimal calendar component looks like this"""
    cal = Calendar()

    # Some properties are required to be compliant
    cal["prodid"] = "-//My calendar product//mxm.dk//"
    cal["version"] = "2.0"

    # We also need at least one subcomponent for a calendar to be compliant
    event = Event()
    event["summary"] = "Python meeting about calendaring"
    event["uid"] = "42"
    event.add("dtstart", datetime(2005, 4, 4, 8, 0, 0))
    cal.add_component(event)
    assert cal.subcomponents[0].to_ical() == (
        b"BEGIN:VEVENT\r\nSUMMARY:Python meeting about calendaring\r\n"
        b"DTSTART:20050404T080000\r\nUID:42\r\n"
        b"END:VEVENT\r\n"
    )


def test_calendar_journals_property(calendars):
    """Calendar.journals returns all VJOURNAL components."""
    journals = calendars.rfc_7986_image.journals
    assert len(journals) == 2
    assert all(isinstance(j, Journal) for j in journals)


def test_calendar_with_parsing_errors_includes_all_events(calendars):
    """Parsing a complete calendar from a string will silently ignore wrong
    events but adding the error information to the component's 'errors'
    attribute. The error in the following is the third EXDATE: it has an
    empty DATE.
    """
    event_descriptions = [
        e["DESCRIPTION"].to_ical() for e in calendars.parsing_error.walk("VEVENT")
    ]
    assert event_descriptions == [b"Perfectly OK event", b"Wrong event"]


def test_calendar_with_parsing_errors_has_an_error_in_one_event(calendars):
    """Parsing a complete calendar from a string will silently ignore wrong
    events but adding the error information to the component's 'errors'
    attribute. The error in the following is the third EXDATE: it has an
    empty DATE.
    """
    errors = [e.errors for e in calendars.parsing_error.walk("VEVENT")]
    assert errors == [[], [("EXDATE", "Expected datetime, date, or time. Got: ''")]]


def test_cal_strict_parsing(calendars):
    """If components are damaged, we raise an exception."""
    with pytest.raises(ValueError):
        calendars.parsing_error_in_UTC_offset


def test_cal_ignore_errors_parsing(calendars, vUTCOffset_ignore_exceptions):
    """If we diable the errors, we should be able to put the calendar back together."""
    assert (
        calendars.parsing_error_in_UTC_offset.to_ical()
        == calendars.parsing_error_in_UTC_offset.raw_ics
    )


@pytest.mark.parametrize(
    ("calendar", "other_calendar"),
    itertools.product(
        [
            "issue_156_RDATE_with_PERIOD_TZID_khal",
            "issue_156_RDATE_with_PERIOD_TZID_khal_2",
            "issue_178_custom_component_contains_other",
            "issue_178_custom_component_inside_other",
            "issue_526_calendar_with_events",
            "issue_526_calendar_with_different_events",
            "issue_526_calendar_with_event_subset",
        ],
        repeat=2,
    ),
)
def test_comparing_calendars(calendars, calendar, other_calendar, tzp):
    are_calendars_equal = calendars[calendar] == calendars[other_calendar]
    are_calendars_actually_equal = calendar == other_calendar
    assert are_calendars_equal == are_calendars_actually_equal


@pytest.mark.parametrize(
    ("calendar", "shuffeled_calendar"),
    [
        (
            "issue_526_calendar_with_events",
            "issue_526_calendar_with_shuffeled_events",
        ),
    ],
)
def test_calendars_with_same_subcomponents_in_different_order_are_equal(
    calendars, calendar, shuffeled_calendar
):
    assert (
        calendars[calendar].subcomponents != calendars[shuffeled_calendar].subcomponents
    )
    assert calendars[calendar] == calendars[shuffeled_calendar]

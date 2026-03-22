"""This tests the creation of new components.

To aid creating valid calendars with a few lines of code, the components
receive a new() classmethod.
This method MUST use property setters to set the properties defined in the keywords.

New keywords can be added over time.

See https://github.com/collective/icalendar/issues/843
"""

from __future__ import annotations

import itertools
import traceback
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import pytest

from icalendar import (
    Alarm,
    Availability,
    Available,
    Calendar,
    Component,
    Event,
    FreeBusy,
    Journal,
    Todo,
    vCalAddress,
)
from icalendar.enums import BUSYTYPE
from icalendar.prop import vText, vUid, vUri, vXmlReference

from .conftest import NOW_UTC, UID_DEFAULT

if TYPE_CHECKING:
    from collections.abc import Callable

UTC = timezone.utc

# Test parametrization

param_summary_components = pytest.mark.parametrize(
    "component", [Event, Todo, Alarm, Journal, Available, Availability]
)
param_description_components = pytest.mark.parametrize(
    "component", [Event, Todo, Alarm, Journal, Available, Availability]
)
COMPONENTS_DTSTAMP = {
    Component,
    Event,
    Journal,
    Todo,
    FreeBusy,
    Available,
    Availability,
}
COMPONENTS_DTSTAMP_AUTOMATIC = {Event, Journal, Todo, FreeBusy, Available, Availability}
COMPONENTS_UID_AUTOMATIC = {Event, Todo, Journal, Available, Availability, Calendar}
COMPONENTS_UID = {Event, Todo, Journal, Alarm, Calendar, Available, Availability}
COMPONENTS_SEQUENCE = {Event, Todo, Journal, Availability}
COMPONENTS_CATEGORIES = {Event, Journal, Todo, Calendar, Availability, Available}
COMPONENTS_ORGANIZER = {Availability, Event, FreeBusy, Journal, Todo}
COMPONENTS_LOCATION = {Availability, Available, Event, Todo}
COMPONENTS_URL = {Availability, Event, Todo, Journal, FreeBusy, Calendar}
COMPONENTS_BUSYTYPE = {Availability}
COMPONENTS_DESCRIPTION = {
    Event,
    Todo,
    Journal,
    Alarm,
    Available,
    Availability,
    Calendar,
}
COMPONENTS_SUMMARY = {Event, Todo, Journal, Alarm, Available, Availability}
COMPONENTS_COMMENT = {
    Event,
    Todo,
    Journal,
    FreeBusy,
    Available,
    Availability,
}  # Standard and Daylight
COMPONENTS_PRIORITY = {Event, Todo, Availability}
COMPONENTS_CONTACT = {Event, Todo, Journal, FreeBusy, Available, Availability}
COMPONENTS_START_END = {Event, Todo, FreeBusy, Available, Availability}
COMPONENTS_STATUS = {Event, Todo, Journal}
COMPONENTS_ATTENDEES = {Event, Todo, Journal, Alarm}
# RFC 9253 properties are defines on ALL
# So, if you add new components, do not forget to add them here.
COMPONENTS_LINKS = COMPONENTS_RELATED_TO = COMPONENTS_CONCEPTS = COMPONENTS_REFID = {
    Alarm,
    Availability,
    Available,
    Calendar,
    Event,
    FreeBusy,
    Journal,
    Todo,
}


@param_summary_components
def test_summary_default(component):
    """Test the summary property default."""
    c = component()
    assert c.summary is None


@param_description_components
def test_description_default(component):
    """Test the summary property default."""
    c = component()
    assert c.description is None


@param_summary_components
def test_summary_delete(component):
    """Test the summary property default."""
    c = component()
    c.summary = "alksdj"
    del c.summary
    assert c.summary is None
    del c.summary
    assert c.summary is None


@param_description_components
def test_description_delete(component):
    """Test the summary property default."""
    c = component()
    c.description = "alksdj"
    del c.description
    assert c.description is None
    del c.description
    assert c.description is None


param_summary = pytest.mark.parametrize(
    "summary", ["akshdkjahskjdhas", "This is a more\ncomplex summary.", None]
)
param_description = pytest.mark.parametrize(
    "description", ["akshdkjahskjdhas", "This is a more\ncomplex summary.", None]
)


def assert_summary_equals(component: Component, summary: str | None):
    """Check this is the summary."""
    assert_property_equals(component, "summary", summary)


def assert_description_equals(component: Component, summary: str | None):
    """Check this is the summary."""
    assert_property_equals(component, "description", summary)


def assert_property_equals(component: Component, name: str, text: str | None):
    """Check the property."""
    assert getattr(component, name.lower()) == text
    if text is None:
        assert name.upper() not in component
    else:
        assert component[name.upper()] == text


@param_summary_components
@param_summary
def test_set_summary(component, summary):
    """Test the summary property default."""
    c = component()
    c.summary = summary
    assert_summary_equals(c, summary)


@param_summary_components
@param_summary
def test_new_with_summary(component, summary, dont_validate_new):
    """Test the summary property default."""
    assert_summary_equals(component.new(summary=summary), summary)


@param_description_components
@param_description
def test_set_description(component, description):
    """Test the description property default."""
    c = component()
    c.description = description
    assert_description_equals(c, description)


@param_description_components
@param_description
def test_new_with_description(component, description, dont_validate_new):
    """Test the description property default."""
    assert_description_equals(component.new(description=description), description)


def new_journal_description(description) -> Journal:
    """use new()"""
    return Journal.new(description=description)


def set_journal_description(description) -> Journal:
    """Set the description"""
    journal = Journal()
    journal.descriptions = description
    return journal


@pytest.mark.parametrize(
    ("description", "expected_description"),
    [
        (None, []),
        ([], []),
        ("one description", ["one description"]),
        (("desc12", "desc23"), ["desc12", "desc23"]),
    ],
)
@pytest.mark.parametrize(
    "get_journal", [new_journal_description, set_journal_description]
)
def test_journal_description_is_a_list(
    get_journal: Callable[..., Journal], description, expected_description
):
    """A jounal entry can have several descriptions."""
    journal = get_journal(description)
    assert journal.descriptions == expected_description
    if not description:
        assert "DESCRIPTION" not in journal
    else:
        assert "DESCRIPTION" in journal


def test_multiple_descriptions_are_concatenated():
    """For compatibility we also provide the description method that concatenates descriptions."""
    journal = Journal.new(description=("one description", "two descriptions"))
    assert journal.description == "one description\r\n\r\ntwo descriptions"


def component_setter(
    component_class: type[Component], property_name: str, value: Any
) -> Component:
    """We set the value of the component's attribute."""
    component = component_class()
    try:
        setattr(component, property_name, value)
    except TypeError:
        # we show the exception in case the test fails for easier debug
        traceback.print_exc()
        pytest.skip("Cannot set value")
    return component


def component_with_new(
    component_class: type[Component], property_name: str, value: Any
) -> Component:
    """Use new() to create the component."""
    kw = {property_name.lower(): value}
    return component_class.new(**kw)


def assert_component_attribute_has_value(
    component: Component, property_name: str, expected_value: Any, message
):
    """Make  sure that a component's attribute has a value."""
    actual_value = getattr(component, property_name)
    assert actual_value == expected_value, (
        f"The attribute {property_name} of {component} "
        f"should be {expected_value!r} but got {actual_value!r}.\n{message}"
    )


automatic_time_test_cases = list(
    itertools.chain.from_iterable(
        [
            (
                COMPONENTS_DTSTAMP.copy(),
                property_name,
                key,
                date(2023, 10, 21),
                datetime(2023, 10, 21, tzinfo=timezone.utc),
                True,
                f"{key} becomes a UTC value 1",
            ),
            (
                COMPONENTS_DTSTAMP.copy(),
                property_name,
                key,
                datetime(2023, 10, 22),
                datetime(2023, 10, 22, tzinfo=timezone.utc),
                True,
                f"{key} becomes a UTC value 2",
            ),
            (
                COMPONENTS_DTSTAMP.copy(),
                property_name,
                key,
                datetime(2023, 10, 23, 12, 30, tzinfo=timezone.utc),
                datetime(2023, 10, 23, 12, 30, tzinfo=ZoneInfo("UTC")),
                True,
                f"{key} becomes a UTC value 3",
            ),
            (
                COMPONENTS_DTSTAMP.copy(),
                property_name,
                key,
                datetime(2023, 10, 24, 21, 0, 1, tzinfo=timezone(timedelta(hours=1))),
                datetime(2023, 10, 24, 20, 0, 1, tzinfo=ZoneInfo("UTC")),
                True,
                f"{key} becomes a UTC value 4",
            ),
            (
                COMPONENTS_DTSTAMP_AUTOMATIC.copy(),
                property_name,
                key,
                None,
                NOW_UTC,
                key == "DTSTAMP",
                f"we use the current time to create a datetime for {key}",
            ),
            (
                COMPONENTS_DTSTAMP - COMPONENTS_DTSTAMP_AUTOMATIC,
                property_name,
                key,
                None,
                None,
                False,
                f"{key} is not automatically set",
            ),
        ]
        for property_name, key in (
            ("stamp", "DTSTAMP"),
            ("created", "CREATED"),
            ("last_modified", "LAST-MODIFIED"),
        )
    )
)
for (
    component_classes,
    property_name,
    _key,
    _value,
    _expected_value,
    _expected,
    _message,
) in automatic_time_test_cases:
    if property_name != "stamp" and FreeBusy in component_classes:
        # FreeBusy only has stamp.
        component_classes.remove(FreeBusy)


attendee1 = vCalAddress("mailto:attendee1@example.com")
attendee2 = vCalAddress("mailto:attendee2@test.test")


new_test_cases = [
    (
        COMPONENTS_UID,
        "uid",
        "uid",
        "test UID",
        "test UID",
        True,
        "Set the UID property",
    ),
    (
        COMPONENTS_UID_AUTOMATIC,
        "uid",
        "uid",
        None,
        UID_DEFAULT,
        True,
        "Set the UID property by default for these components",
    ),
    (
        COMPONENTS_UID - COMPONENTS_UID_AUTOMATIC,
        "uid",
        "uid",
        None,
        "",
        False,
        "UID is not automatically set",
    ),
    (
        {Event, Todo, Journal, Availability, Available, FreeBusy},
        "start",
        "dtstart",
        datetime(2023, 10, 24, 21, 0, 1, tzinfo=ZoneInfo("Europe/Berlin")),
        datetime(2023, 10, 24, 21, 0, 1, tzinfo=ZoneInfo("Europe/Berlin")),
        True,
        "set the start",
    ),
    (
        {Event, Available, FreeBusy},
        "end",
        "dtend",
        datetime(2023, 10, 24, 22, 0, 1, tzinfo=ZoneInfo("Europe/Berlin")),
        datetime(2023, 10, 24, 22, 0, 1, tzinfo=ZoneInfo("Europe/Berlin")),
        True,
        "set the end",
    ),
    (
        {Todo},
        "end",
        "due",
        datetime(2023, 10, 24, 22, 0, 1, tzinfo=ZoneInfo("Europe/Berlin")),
        datetime(2023, 10, 24, 22, 0, 1, tzinfo=ZoneInfo("Europe/Berlin")),
        True,
        "set the end",
    ),
    (
        {Event, Todo, Journal, Available},
        "RECURRENCE_ID",
        "RECURRENCE-ID",
        datetime(2025, 4, 28, 16, 5, tzinfo=ZoneInfo("UTC")),
        datetime(2025, 4, 28, 16, 5, tzinfo=ZoneInfo("UTC")),
        True,
        "set the recurrence_id",
    ),
    (
        {Event, Todo, Journal, Available},
        "RECURRENCE_ID",
        "RECURRENCE-ID",
        None,
        None,
        False,
        "no recurrence_id by default",
    ),
    (
        {Todo, Event, Calendar, Journal},
        "color",
        "color",
        "red",
        "red",
        True,
        "set the color",
    ),
    (
        COMPONENTS_SEQUENCE,
        "sequence",
        "SEQUENCE",
        1,
        1,
        True,
        "set the sequence",
    ),
    (
        COMPONENTS_SEQUENCE,
        "sequence",
        "SEQUENCE",
        None,
        0,
        False,
        "get the default the sequence",
    ),
    (
        COMPONENTS_CATEGORIES,
        "categories",
        "CATEGORIES",
        ["cat1", "cat2"],
        ["cat1", "cat2"],
        True,
        "set the categories",
    ),
    (
        COMPONENTS_CATEGORIES,
        "categories",
        "CATEGORIES",
        (),
        [],
        False,
        "categories are absent",
    ),
    (
        COMPONENTS_ORGANIZER,
        "organizer",
        "ORGANIZER",
        "mailto:bernard@example.com",
        "mailto:bernard@example.com",
        True,
        "set the organizer",
    ),
    (
        COMPONENTS_ORGANIZER,
        "organizer",
        "ORGANIZER",
        None,
        None,
        False,
        "no organizer by default",
    ),
    (
        COMPONENTS_LOCATION,
        "location",
        "LOCATION",
        "Berlin",
        "Berlin",
        True,
        "set the location",
    ),
    (
        COMPONENTS_LOCATION,
        "location",
        "LOCATION",
        None,
        None,
        False,
        "no location by default",
    ),
    (
        COMPONENTS_URL,
        "url",
        "URL",
        "https://icalendar.readthedocs.io/",
        "https://icalendar.readthedocs.io/",
        True,
        "set the url",
    ),
    (
        COMPONENTS_URL,
        "url",
        "URL",
        None,
        "",
        False,
        "no url by default",
    ),
    (
        COMPONENTS_BUSYTYPE,
        "busy_type",
        "BUSYTYPE",
        BUSYTYPE.BUSY,
        BUSYTYPE.BUSY,
        True,
        "set the url",
    ),
    (
        COMPONENTS_BUSYTYPE,
        "busy_type",
        "BUSYTYPE",
        None,
        BUSYTYPE.BUSY_UNAVAILABLE,
        False,
        "default busy type",
    ),
    (
        COMPONENTS_DESCRIPTION,
        "description",
        "DESCRIPTION",
        "This describes the component a bit more in detail.",
        "This describes the component a bit more in detail.",
        True,
        "set the description",
    ),
    (
        COMPONENTS_DESCRIPTION,
        "description",
        "DESCRIPTION",
        None,
        None,
        False,
        "no description by default",
    ),
    (
        COMPONENTS_SUMMARY,
        "summary",
        "SUMMARY",
        "component summary",
        "component summary",
        True,
        "set the summary",
    ),
    (
        COMPONENTS_SUMMARY,
        "summary",
        "SUMMARY",
        None,
        None,
        False,
        "no summary by default",
    ),
    (
        COMPONENTS_PRIORITY,
        "priority",
        "PRIORITY",
        8,
        8,
        True,
        "priority is set",
    ),
    (
        COMPONENTS_PRIORITY,
        "priority",
        "PRIORITY",
        None,
        0,
        False,
        "no priority by default",
    ),
    (
        COMPONENTS_COMMENT,
        "comments",
        "COMMENT",
        None,
        [],
        False,
        "no comments",
    ),
    (
        COMPONENTS_COMMENT,
        "comments",
        "COMMENT",
        "This is a comment",
        ["This is a comment"],
        True,
        "one comment is set",
    ),
    (
        COMPONENTS_COMMENT,
        "comments",
        "COMMENT",
        ["one", "two", "three"],
        ["one", "two", "three"],
        True,
        "several comments",
    ),
    (
        COMPONENTS_CONTACT,
        "contacts",
        "CONTACT",
        None,
        [],
        False,
        "no contacts",
    ),
    (
        COMPONENTS_CONTACT,
        "contacts",
        "CONTACT",
        "This is a comment",
        ["This is a comment"],
        True,
        "one contact is set",
    ),
    (
        COMPONENTS_CONTACT,
        "contacts",
        "CONTACT",
        ["one", "two", "three"],
        ["one", "two", "three"],
        True,
        "several contacts",
    ),
    (
        {Event},
        "transparency",
        "TRANSP",
        "TRANSPARENT",
        "TRANSPARENT",
        True,
        "value set to TRANSPARENT",
    ),
    (
        {Event},
        "transparency",
        "TRANSP",
        "OPAQUE",
        "OPAQUE",
        True,
        "value set to OPAQUE",
    ),
    (
        {Event},
        "transparency",
        "TRANSP",
        None,
        "OPAQUE",
        False,
        "value is not set, defaults to OPAQUE",
    ),
    (
        COMPONENTS_STATUS,
        "status",
        "STATUS",
        "CANCELLED",
        "CANCELLED",
        True,
        "value set to CANCELLED",
    ),
    (
        COMPONENTS_STATUS,
        "status",
        "STATUS",
        "NEEDS-ACTION",
        "NEEDS-ACTION",
        True,
        "value set to NEEDS-ACTION",
    ),
    (
        COMPONENTS_STATUS,
        "status",
        "STATUS",
        None,
        "",
        False,
        "value is not set",
    ),
    (
        COMPONENTS_STATUS,
        "status",
        "STATUS",
        "",
        "",
        False,
        "value is not set",
    ),
    (
        COMPONENTS_ATTENDEES,
        "attendees",
        "ATTENDEE",
        [],
        [],
        True,
        "value is not set",
    ),
    (
        COMPONENTS_ATTENDEES,
        "attendees",
        "ATTENDEE",
        None,
        [],
        False,
        "value is empty",
    ),
    (
        COMPONENTS_ATTENDEES,
        "attendees",
        "ATTENDEE",
        [attendee1],
        [attendee1],
        True,
        "one attendee",
    ),
    (
        COMPONENTS_ATTENDEES,
        "attendees",
        "ATTENDEE",
        attendee2,
        [attendee2],
        True,
        "one attendee",
    ),
    (
        COMPONENTS_ATTENDEES,
        "attendees",
        "ATTENDEE",
        [attendee1, attendee2],
        [attendee1, attendee2],
        True,
        "two attendees",
    ),
]

rfc_7986_test_cases = [
    (
        {Calendar},
        "last_modified",
        "LAST-MODIFIED",
        datetime(2011, 10, 5, 13, 32, 25),
        datetime(2011, 10, 5, 13, 32, 25, tzinfo=UTC),
        True,
        "value set to 2011-10-05T13:32:25 UTC",
    ),
    (
        {Calendar},
        "last_modified",
        "LAST-MODIFIED",
        None,
        None,
        False,
        "value is not set",
    ),
    (
        {Calendar},
        "source",
        "SOURCE",
        "https://github.com/collective/icalendar",
        "https://github.com/collective/icalendar",
        True,
        "setting a string",
    ),
    (
        {Calendar},
        "refresh_interval",
        "REFRESH-INTERVAL",
        timedelta(hours=1),
        timedelta(hours=1),
        True,
        "setting a timedelta",
    ),
    (
        {Calendar},
        "refresh_interval",
        "REFRESH-INTERVAL",
        None,
        None,
        False,
        "setting nothing",
    ),
]


rfc_9253_link_values = [
    vUri("https://123"),
    vUid("123-123-123"),
    vXmlReference("http://example.com"),
]

rfc_9253_related_to_values = [
    vUri("https://123"),
    vUid("123-123-123"),
    vText("nananana", params={"RELTYPE": "SIBLING"}),
]
rfc_9253_test_cases = [
    (
        COMPONENTS_LINKS,
        "links",
        "LINK",
        None,
        [],
        False,
        "setting nothing",
    ),
    (
        COMPONENTS_LINKS,
        "links",
        "LINK",
        [],
        [],
        False,
        "setting nothing",
    ),
    (
        COMPONENTS_LINKS,
        "links",
        "LINK",
        ["https://123"],
        [vUri("https://123")],
        True,
        "set one value",
    ),
    (
        COMPONENTS_LINKS,
        "links",
        "LINK",
        rfc_9253_link_values,
        rfc_9253_link_values,
        True,
        "set several values",
    ),
    (
        COMPONENTS_RELATED_TO,
        "related_to",
        "RELATED-TO",
        None,
        [],
        False,
        "setting nothing",
    ),
    (
        COMPONENTS_RELATED_TO,
        "related_to",
        "RELATED-TO",
        [],
        [],
        False,
        "setting nothing",
    ),
    (
        COMPONENTS_RELATED_TO,
        "related_to",
        "RELATED-TO",
        ["https://123"],
        [vText("https://123")],
        True,
        "set one value",
    ),
    (
        COMPONENTS_RELATED_TO,
        "related_to",
        "RELATED-TO",
        rfc_9253_related_to_values,
        rfc_9253_related_to_values,
        True,
        "set several values",
    ),
    (
        COMPONENTS_CONCEPTS,
        "concepts",
        "CONCEPT",
        None,
        [],
        False,
        "setting nothing",
    ),
    (
        COMPONENTS_CONCEPTS,
        "concepts",
        "CONCEPT",
        [],
        [],
        False,
        "setting nothing",
    ),
    (
        COMPONENTS_CONCEPTS,
        "concepts",
        "CONCEPT",
        ["https://123", vUri("https://asd")],
        [vUri("https://123"), vUri("https://asd")],
        True,
        "set two values",
    ),
    (
        COMPONENTS_REFID,
        "refids",
        "REFID",
        None,
        [],
        False,
        "setting nothing",
    ),
    (
        COMPONENTS_REFID,
        "refids",
        "REFID",
        [],
        [],
        False,
        "setting nothing",
    ),
    (
        COMPONENTS_REFID,
        "refids",
        "REFID",
        "itinerary-2014-11-17",
        ["itinerary-2014-11-17"],
        True,
        "set a value",
    ),
    (
        COMPONENTS_REFID,
        "refids",
        "REFID",
        ["itinerary-2014-11-17", "itinerary-2014-11-17-2"],
        ["itinerary-2014-11-17", "itinerary-2014-11-17-2"],
        True,
        "set two values",
    ),
]


@pytest.mark.parametrize(
    (
        "component_classes",
        "property_name",
        "key",
        "initial_value",
        "expected_value",
        "key_present",
        "message",
    ),
    automatic_time_test_cases
    + new_test_cases
    + rfc_7986_test_cases
    + rfc_9253_test_cases,
)
@pytest.mark.parametrize(
    "create_component_with_property", [component_setter, component_with_new]
)
def test_properties_and_new(
    create_component_with_property,
    component_classes,
    property_name,
    initial_value,
    expected_value,
    key_present,
    key,
    message,
    dont_validate_new,
):
    """We set and get the dtstamp."""
    for component_class in component_classes:
        print(
            "processing:",
            component_class.name,
            "->",
            property_name,
            "=",
            initial_value,
            ":",
            message,
        )
        component = create_component_with_property(
            component_class, property_name, initial_value
        )
        if (
            create_component_with_property is component_with_new
            or initial_value is not None
        ):
            assert (key in component) == key_present, message
            # the setter does not create default values
            # so we only check it if present
            assert_component_attribute_has_value(
                component, property_name, expected_value, message
            )


@pytest.mark.parametrize("component_class", COMPONENTS_START_END)
def test_end_must_be_after_start(tzp, component_class):
    """The end must be after the start."""
    with pytest.raises(ValueError) as e:
        component_class.new(
            start=tzp.localize_utc(datetime(2011, 10, 5, 13, 32, 25)),
            end=tzp.localize_utc(datetime(2011, 10, 5, 12, 32, 25)),
        )
    assert "end must be after start" in str(e.value)


@pytest.mark.parametrize("component_class", COMPONENTS_START_END)
def test_start_and_end_can_be_the_same(tzp, component_class):
    """The end must be after the start."""
    start = tzp.localize_utc(datetime(2011, 10, 5, 13, 32, 25))
    c = component_class.new(start=start, end=start)
    assert c.start == start
    assert c.end == start
    assert c.duration == timedelta(0)


def test_journal_start():
    """Journal does not have an end."""
    j = Journal.new(start=datetime(2011, 10, 5, 13, 32, 25))
    assert j.start == datetime(2011, 10, 5, 13, 32, 25)


def test_modify_attendees():
    """We modify the list and see of that works."""
    attendees = [attendee1]
    j = Journal.new(attendees=attendees)
    j.attendees.append(attendee2)
    assert j.attendees == [attendee1, attendee2]
    ics = j.to_ical().decode()
    assert str(attendee1) in ics
    assert str(attendee2) in ics


def test_modify_default_attendees():
    """Empty attendees need to be modifiable."""
    todo = Todo.new()
    todo.attendees.append(attendee1)
    assert todo.attendees == [attendee1]
    ics = todo.to_ical().decode()
    assert str(attendee1) in ics


def test_empty_attendees_to_ical():
    """We should be able to have no attendees set."""
    e = Event.new()
    e.attendees = []
    assert "ATTENDEE" not in e.to_ical().decode()


def test_modify_empty_attendees_1():
    """Empty value set and modified."""
    e = Event()
    attendees = []
    e.attendees = attendees
    e.attendees.append(attendee1)
    assert e.attendees == [attendee1] == attendees


def test_modify_empty_attendees_2():
    """Empty value set and modified."""
    e = Event()
    attendees = []
    e.attendees = attendees
    attendees.append(attendee1)
    assert e.attendees == [attendee1] == attendees

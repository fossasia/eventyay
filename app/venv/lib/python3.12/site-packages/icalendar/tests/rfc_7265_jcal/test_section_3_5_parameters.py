"""
Property parameters are represented as a JSON object where each key-
value pair represents the iCalendar parameter name and its value.
The name of the parameter MUST be in lowercase; the original case of
the parameter value MUST be preserved.
"""

from typing import TYPE_CHECKING

import pytest

from icalendar import PARTSTAT, ROLE, VPROPERTY, Event, vCalAddress
from icalendar.parser import Parameters

if TYPE_CHECKING:
    from icalendar.cal.calendar import Calendar


def test_vCalAddressExample():
    """Test the example from vCalAddress."""
    addr = vCalAddress.new(
        "jsmith@example.org",
        partstat=PARTSTAT.ACCEPTED,
        rsvp=True,
        role=ROLE.REQ_PARTICIPANT,
    )
    event = Event()
    event.attendees = [addr]
    event.summary = "Meeting"
    jcal = event.to_jcal()
    assert jcal == [
        "vevent",
        [
            [
                "attendee",
                {"partstat": "ACCEPTED", "rsvp": "TRUE", "role": "REQ-PARTICIPANT"},
                "cal-address",
                "mailto:jsmith@example.org",
            ],
            ["summary", {}, "text", "Meeting"],
        ],
        [],
    ]


def test_parameter_conversion_is_handed_over_to_parameter(v_prop: VPROPERTY, mock):
    """The parameters are part of the jCal conversion."""
    example = v_prop.examples()[0]
    assert isinstance(example.params, Parameters)
    example.params = mock
    return_value = example.params.to_jcal.return_value
    jcal = example.to_jcal("X-NAME")
    mock.to_jcal.assert_called_once()
    assert len(jcal) >= 4
    assert jcal[1] == return_value
    assert jcal[0] == "X-NAME"


def test_all_default_values_are_lowercase(v_prop_example):
    """All the default values should be lowercase.

    :rfc:`7265`:
        If the property has no "VALUE" parameter but has a default value
        type, the default value type is used.
    """
    jcal = v_prop_example.to_jcal("X-NAME")
    ical_type: str = jcal[2]
    assert ical_type.islower()


def test_all_set_values_are_preserved(v_prop_example):
    """Check the set value type.

    :rfc:`5545`:
        All names of [...] property parameter values are case-insensitive.

    :rfc:`7265`:
        If the property has a "VALUE" parameter, that parameter's value
        is used as the value type.

    We can convert them to lowercase but it is not stated explicitely.
    """
    v_prop_example.VALUE = "X-OTHER-VALUE"
    jcal = v_prop_example.to_jcal("X-NAME")
    ical_type: str = jcal[2]
    assert ical_type == "x-other-value"


def test_unknown_value(calendars):
    """Test unknown value.

    :rfc:`7265`:
        If the property has no "VALUE" parameter and has no default value
        type, "unknown" is used.

    """
    calendar: Calendar = calendars.x_location
    jcal = calendar.to_jcal()
    props = jcal[1]
    checked = 0
    for prop in props:
        print(prop)
        if prop[0].startswith("x-"):
            assert prop[2] == "unknown"
            checked += 1
    assert checked >= 3, "We checked at least some properties."


@pytest.mark.parametrize(
    ("event_index", "parameter_index", "expected_value"),
    [
        (
            0,
            0,
            [
                "attendee",
                {
                    "delegated-to": [
                        "mailto:jdoe@example.com",
                        "mailto:jqpublic@example.com",
                    ]
                },
                "cal-address",
                "mailto:jsmith@example.com",
            ],
        ),
        (
            0,
            1,
            [
                "attendee",
                {
                    "delegated-from": [
                        "mailto:jsmith@example.com",
                        "mailto:jdoe@example.com",
                    ]
                },
                "cal-address",
                "mailto:jdoe@example.com",
            ],
        ),
        (
            0,
            2,
            [
                "attendee",
                {
                    "member": [
                        "mailto:projectA@example.com",
                        "mailto:projectB@example.com",
                    ]
                },
                "cal-address",
                "mailto:janedoe@example.com",
            ],
        ),
        (
            1,
            0,
            [
                "attendee",
                {"delegated-to": "mailto:jdoe@example.com"},
                "cal-address",
                "mailto:jsmith@example.com",
            ],
        ),
        (
            1,
            1,
            [
                "attendee",
                {"delegated-from": "mailto:jsmith@example.com"},
                "cal-address",
                "mailto:jdoe@example.com",
            ],
        ),
        (
            1,
            2,
            [
                "attendee",
                {"member": "mailto:projectA@example.com"},
                "cal-address",
                "mailto:janedoe@example.com",
            ],
        ),
    ],
)
def test_parameters_with_values_as_list(
    calendars, event_index, parameter_index, expected_value
):
    """Check the conversion of list value parameters.

    In [RFC5545], some parameters allow using a COMMA-separated list of
    values.  To ease processing in jCal, the value of such parameters
    MUST be represented in an array containing the separated values.
    """
    calendar: Calendar = calendars.rfc_7256_multi_value_parameters
    event = calendar.events[event_index]
    parameter = event.to_jcal()[1][parameter_index]
    assert parameter == expected_value

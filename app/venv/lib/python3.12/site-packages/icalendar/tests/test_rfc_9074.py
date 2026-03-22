"""Test the VALARM compatibility of RFC 9074.

See https://www.rfc-editor.org/rfc/rfc9074.html
and also https://github.com/collective/icalendar/issues/657
"""

import pytest

from icalendar.prop import vDDDTypes, vText


@pytest.mark.parametrize(
    ("prop", "cls", "file", "alarm_index"),
    [
        ("UID", vText, "rfc_9074_example_1", 0),
        ("RELATED-TO", vText, "rfc_9074_example_2", 1),
        ("ACKNOWLEDGED", vDDDTypes, "rfc_9074_example_3", 0),
        ("PROXIMITY", vText, "rfc_9074_example_proximity", 0),
    ],
)
def test_calendar_types(events, prop, cls, file, alarm_index):
    """Check the types of the properties."""
    event = events[file]
    alarm = event.subcomponents[alarm_index]
    value = alarm[prop]
    assert isinstance(value, cls)


def test_snooze(events):
    """Check values of the alarms."""
    alarm_1 = events.rfc_9074_example_3.subcomponents[0]
    assert alarm_1["ACKNOWLEDGED"].dt == vDDDTypes.from_ical("20210302T152024Z")
    alarm_2 = events.rfc_9074_example_3.subcomponents[1]
    assert alarm_2["RELATED-TO"] == "8297C37D-BA2D-4476-91AE-C1EAA364F8E1"
    assert alarm_2["RELATED-TO"].params["RELTYPE"] == "SNOOZE"


def test_proximity(events):
    """Check the proximity values."""
    alarm = events.rfc_9074_example_proximity.subcomponents[0]
    assert alarm["PROXIMITY"] == "DEPART"
    assert len(alarm.subcomponents) == 1
    location = alarm.subcomponents[0]
    assert location["UID"] == "123456-abcdef-98765432"

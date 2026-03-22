"""We would like to be able to get the right timezone names.

See https://github.com/collective/icalendar/issues/336

It appears that the timezone Brazil/DeNoronha is actually America/Noronha.
"""

from datetime import datetime

from dateutil import tz

from icalendar.cal.event import Event
from icalendar.timezone import tzid_from_tzinfo

valid_names = ("America/Noronha", "Brazil/DeNoronha")


def test_timezone_name_directly():
    """Try to get the name directly."""
    tzinfo = tz.gettz("Brazil/DeNoronha")
    assert tzid_from_tzinfo(tzinfo) in valid_names


def test_in_event():
    """The example has an event in it and we want to have the id in it."""
    event = Event()
    event.start = datetime(2025, 5, 13, 14, 23, tzinfo=tz.gettz("Brazil/DeNoronha"))
    ics = event.to_ical().decode()
    print(ics)
    assert any(name in ics for name in valid_names)

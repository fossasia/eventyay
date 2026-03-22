"""We want to add rrule as a string for convenience.

See https://github.com/collective/icalendar/issues/301
"""

from icalendar.cal.event import Event


def test_rrule_add_example():
    event = Event()
    event.add("RRULE", "FREQ=DAILY;INTERVAL=2")
    assert "FREQ=DAILY;INTERVAL=2" in event.to_ical().decode("utf-8")
    assert event.rrules[0]["freq"] == ["DAILY"]
    assert event.rrules[0]["interval"] == [2]

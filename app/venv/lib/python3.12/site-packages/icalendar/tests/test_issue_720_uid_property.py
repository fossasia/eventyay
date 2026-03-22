"""This tests the UID property.

See https://github.com/collective/icalendar/issues/740
"""

from icalendar.cal.alarm import Alarm


def test_alarm_uses_x_property_too():
    alarm = Alarm()
    alarm["X-ALARMUID"] = "1234"
    assert alarm.uid == "1234"

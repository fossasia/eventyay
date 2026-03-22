"""This tests if the UID is set be default, closing issue 315.

See https://github.com/collective/icalendar/issues/315
"""

import pytest

from icalendar import Event, Journal, Todo


@pytest.mark.parametrize("cls", [Event, Journal, Todo])
def test_uid_is_included(cls):
    """Make sure we have a UID!"""
    component = cls.new()
    assert "uid" in component
    assert component.uid != ""
    assert "UID" in component.to_ical().decode()

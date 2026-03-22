"""This implemensts RFC 6868.

There are only some changes to parameters needed.
"""

import os
from typing import TYPE_CHECKING

import pytest

from icalendar.cal.calendar import Calendar
from icalendar.parser import dquote, rfc_6868_escape, rfc_6868_unescape

if TYPE_CHECKING:
    from icalendar import vCalAddress, vText


param_duplicate = pytest.mark.parametrize(
    "duplicate", [lambda x: x, lambda cal: Calendar.from_ical(cal.to_ical())]
)


@param_duplicate
def test_rfc_6868_example(calendars, duplicate):
    """Check the example from the RFC."""
    cal: Calendar = duplicate(calendars.rfc_6868)
    attendee: vCalAddress = cal.events[0]["attendee"]
    assert attendee.name == 'George Herman "Babe" Ruth'


@param_duplicate
def test_all_parameters(calendars, duplicate):
    """Check that all examples get decoded correctly."""
    cal: Calendar = duplicate(calendars.rfc_6868)
    param = cal["X-PARAM"].params["ALL"]
    assert param == '^"\n'


@param_duplicate
def test_unknown_character(calendars, duplicate):
    """if a ^ (U+005E) character is followed by any character other than
    the ones above, parsers MUST leave both the ^ and the following
    character in place"""
    cal: Calendar = duplicate(calendars.rfc_6868)
    param = cal["X-PARAM"].params["UNKNOWN"]
    assert param == "^a^ ^asd"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("^a", "^a"),
        ("^^", "^"),
        # ("^n", ),  # see other test
        ("^'", '"'),
        ("^^a^b", "^a^b"),
    ],
)
@pytest.mark.parametrize(
    "modify", [lambda x: x, lambda x: x * 10, lambda x: f"asd{x}aaA^AA"]
)
def test_unescape(text, expected, modify):
    """Check unescaping."""
    result = rfc_6868_unescape(modify(text))
    assert result == modify(expected)


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r", os.linesep])
def test_unescape_newline(newline, monkeypatch):
    """Unescape the newline."""
    monkeypatch.setattr(os, "linesep", newline)
    assert rfc_6868_unescape("^n") == newline


param_values = pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", ""),
        ("^", "^^"),
        ("^n", "^^n"),
        ("This text\n has\r several\r\n lines", "This text^n has^n several^n lines"),
        ('Call me "Harry".', "Call me ^'Harry^'."),
    ],
)


@param_values
def test_escape_rfc_6868(text, expected):
    """Check that we can escape the content with special characters."""
    escaped = rfc_6868_escape(text)
    assert escaped == expected, f"{escaped!r} == {expected!r}"
    assert rfc_6868_escape(rfc_6868_unescape(escaped)) == expected


@param_values
def test_escaping_parameters(text, expected):
    cal = Calendar()
    cal.add("X-Param", "asd")
    param: vText = cal["X-PARAM"]
    param.params["RFC6868"] = text
    ical = cal.to_ical().decode()
    print(ical)
    assert "X-PARAM;RFC6868=" + dquote(expected) in ical


def test_encode_example_again(calendars):
    """The example file should yield its content again."""
    cal: Calendar = calendars.rfc_6868
    again = Calendar.from_ical(cal.to_ical())
    assert cal == again
    assert cal.to_ical() == again.to_ical()

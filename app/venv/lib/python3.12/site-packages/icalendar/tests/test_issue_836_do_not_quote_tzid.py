"""Quoting the TZID parameter creates compatibility problems.

See https://github.com/collective/icalendar/issues/836

:rfc:`5545`:

.. code-block:: text

    param-value   = paramtext / quoted-string
    paramtext     = *SAFE-CHAR
    quoted-string = DQUOTE *QSAFE-CHAR DQUOTE
    SAFE-CHAR     = WSP / %x21 / %x23-2B / %x2D-39 / %x3C-7E
                   / NON-US-ASCII
     ; Any character except CONTROL, DQUOTE, ";", ":", ","
     NON-US-ASCII  = UTF8-2 / UTF8-3 / UTF8-4
     ; UTF8-2, UTF8-3, and UTF8-4 are defined in [RFC3629]

"""

from datetime import datetime, time

import pytest

from icalendar import Event, Parameters, vDatetime, vDDDTypes, vPeriod, vTime
from icalendar.prop import vDDDLists

# All the controls except HTAB
CONTROL = {i for i in range(256) if 0x00 <= i <= 0x08 or 0x0A <= i <= 0x1F or i == 0x7F}

# Any character except CONTROL, DQUOTE, ";", ":", ","
SAFE_CHAR = set(range(256)) - CONTROL - set(b'";:,')

param_tzid = pytest.mark.parametrize(
    "tzid",
    [
        "Europe/London",
        "Eastern Standard Time",
    ],
)


@param_tzid
@pytest.mark.parametrize(
    "vdt",
    [
        vDatetime(datetime(2024, 10, 11, 12, 0)),
        vTime(time(23, 59, 59)),
        vDDDTypes(datetime(2024, 10, 11, 12, 0)),
        vPeriod((datetime(2024, 10, 11, 12, 0), datetime(2024, 10, 11, 13, 0))),
        vDDDLists([datetime(2024, 10, 11, 12, 0)]),
    ],
)
def test_parameter_is_not_quoted_when_not_needed(tzid, vdt):
    """Check that serializing the value works without quoting."""
    e = Event()
    vdt.params["TZID"] = tzid
    e["DTSTART"] = vdt
    ics = e.to_ical().decode()
    print(ics)
    assert tzid in ics
    assert f'"{tzid}' not in ics
    assert f'{tzid}"' not in ics


@pytest.mark.parametrize("safe_char", list(map(chr, sorted(SAFE_CHAR))))
def test_safe_char_is_not_escaped(safe_char):
    """Check that paramerter serialization is without quotes for safe chars."""
    params = Parameters(tzid=safe_char)
    result = params.to_ical().decode()
    assert '"' not in result


def test_get_calendar_and_serialize_it_wihtout_quotes(calendars):
    """The example calendar should not contain the timezone with quotes."""
    ics = calendars.issue_836_do_not_quote_tzid.to_ical().decode()
    assert '"Eastern Standard' not in ics
    assert 'Standard Time"' not in ics
    assert "Eastern Standard Time" in ics

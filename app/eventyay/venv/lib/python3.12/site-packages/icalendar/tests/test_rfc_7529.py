"""This tests the compatibility with RFC 7529.

See
- https://github.com/collective/icalendar/issues/655
- https://www.rfc-editor.org/rfc/rfc7529.html
"""

import pytest

from icalendar.prop import vMonth, vRecur, vSkip


@pytest.mark.parametrize(
    ("uid", "scale"),
    [
        ("4.3.1", "CHINESE"),
        ("4.3.2", "ETHIOPIC"),
        ("4.3.3", "HEBREW"),
        ("4.3.4", "GREGORIAN"),
    ],
)
def test_rscale(calendars, uid, scale):
    """Check that the RSCALE is parsed correctly."""
    event = calendars.rfc_7529.walk(select=lambda c: c.get("UID") == uid)[0]
    print(event.errors)
    rrule = event["RRULE"]
    print(rrule)
    assert rrule["RSCALE"] == [scale]


@pytest.mark.parametrize(
    ("uid", "skip"),
    [
        ("4.3.2", None),
        ("4.3.3", ["FORWARD"]),
    ],
)
def test_rscale_with_skip(calendars, uid, skip):
    """Check that the RSCALE is parsed correctly."""
    event = calendars.rfc_7529.walk(select=lambda c: c.get("UID") == uid)[0]
    recur = event["RRULE"]
    assert recur.get("SKIP") == skip


def test_leap_month(calendars):
    """Check that we can parse the leap month."""
    event = calendars.rfc_7529.walk(select=lambda c: c.get("UID") == "4.3.3")[0]
    recur = event["RRULE"]
    assert recur["BYMONTH"][0].leap is True


@pytest.mark.parametrize(
    ("ty", "recur", "ics"),
    [
        (
            vRecur,
            vRecur(rscale="CHINESE", freq="YEARLY"),
            b"RSCALE=CHINESE;FREQ=YEARLY",
        ),
        (vRecur, vRecur(bymonth=vMonth(10)), b"BYMONTH=10"),
        (vRecur, vRecur(bymonth=vMonth("5L")), b"BYMONTH=5L"),
        (vMonth, vMonth(10), b"10"),
        (vMonth, vMonth("5L"), b"5L"),
        (vSkip, vSkip.OMIT, b"OMIT"),
        (vSkip, vSkip.BACKWARD, b"BACKWARD"),
        (vSkip, vSkip.FORWARD, b"FORWARD"),
        (vSkip, vSkip("OMIT"), b"OMIT"),
        (vSkip, vSkip("BACKWARD"), b"BACKWARD"),
        (vSkip, vSkip("FORWARD"), b"FORWARD"),
        (
            vRecur,
            vRecur(rscale="GREGORIAN", freq="YEARLY", skip="FORWARD"),
            b"RSCALE=GREGORIAN;FREQ=YEARLY;SKIP=FORWARD",
        ),
        (
            vRecur,
            vRecur(rscale="GREGORIAN", freq="YEARLY", skip=vSkip.FORWARD),
            b"RSCALE=GREGORIAN;FREQ=YEARLY;SKIP=FORWARD",
        ),
    ],
)
def test_conversion(ty, recur, ics):
    """Test string conversion."""
    assert recur.to_ical() == ics
    assert ty.from_ical(ics.decode()) == recur
    assert ty.from_ical(ics.decode()).to_ical() == ics

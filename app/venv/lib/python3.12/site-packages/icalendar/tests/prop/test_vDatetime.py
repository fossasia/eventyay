from datetime import datetime

import pytest

from icalendar.prop import vDatetime


def test_to_ical():
    assert vDatetime(datetime(2001, 1, 1, 12, 30, 0)).to_ical() == b"20010101T123000"


def test_from_ical():
    assert vDatetime.from_ical("20000101T120000") == datetime(2000, 1, 1, 12, 0)
    assert vDatetime.from_ical("20010101T000000") == datetime(2001, 1, 1, 0, 0)


def test_to_ical_utc(tzp):
    dutc = tzp.localize_utc(datetime(2001, 1, 1, 12, 30, 0))
    assert vDatetime(dutc).to_ical() == b"20010101T123000Z"


def test_to_ical_utc_1899(tzp):
    dutc = tzp.localize_utc(datetime(1899, 1, 1, 12, 30, 0))
    assert vDatetime(dutc).to_ical() == b"18990101T123000Z"


def test_bad_ical():
    with pytest.raises(ValueError):
        vDatetime.from_ical("20010101T000000A")


def test_roundtrip():
    utc = vDatetime.from_ical("20010101T000000Z")
    assert vDatetime(utc).to_ical() == b"20010101T000000Z"


def test_transition(tzp):
    # 1 minute before transition to DST
    dat = vDatetime.from_ical("20120311T015959", "America/Denver")
    assert dat.strftime("%Y%m%d%H%M%S %z") == "20120311015959 -0700"

    # After transition to DST
    dat = vDatetime.from_ical("20120311T030000", "America/Denver")
    assert dat.strftime("%Y%m%d%H%M%S %z") == "20120311030000 -0600"

    dat = vDatetime.from_ical("20101010T000000", "Europe/Vienna")
    assert vDatetime(dat).to_ical() == b"20101010T000000"

"""Test the property parameters.

See https://github.com/collective/icalendar/issues/798
"""

from datetime import datetime

import pytest

from icalendar import (
    CUTYPE,
    FBTYPE,
    PARTSTAT,
    RANGE,
    RELTYPE,
    vCalAddress,
    vDatetime,
    vPeriod,
    vText,
)
from icalendar.parser import Parameters
from icalendar.timezone.tzp import TZP


class Prop:
    params: Parameters

    def __init__(self, **parameters):
        """Create a new property."""
        self.params = Parameters(parameters)

    def to_ical(self) -> str:
        """Parameters to bytes to string."""
        return self.params.to_ical().decode("utf-8")

    from icalendar.param import (
        ALTREP,
        CN,
        CUTYPE,
        DELEGATED_FROM,
        DELEGATED_TO,
        RELTYPE,
    )


@pytest.fixture
def p():
    """Empty test property."""
    return Prop()


def test_set_altrep(p):
    p.ALTREP = "http://example.com"
    assert p.params == {"ALTREP": "http://example.com"}
    assert p.ALTREP == "http://example.com"


def test_altrep_must_be_quoted():
    """altrepparam = "ALTREP" "=" DQUOTE uri DQUOTE"""
    assert Prop(ALTREP="1234aA").to_ical() == 'ALTREP="1234aA"'


def test_del_altrep(p):
    """Del when empty"""
    del p.ALTREP
    assert p.params == {}
    assert p.ALTREP is None


def test_del_altrep_full(p):
    """Del when empty"""
    p.ALTREP = "http://example.com"
    del p.ALTREP
    assert p.params == {}
    assert p.ALTREP is None


def test_get_cutype(p):
    """The default is individual."""
    assert p.CUTYPE == "INDIVIDUAL"


def test_set_lowercase():
    p = Prop(CUTYPE="individual")
    assert p.CUTYPE == "INDIVIDUAL"
    p.CUTYPE = "unknown"
    assert p.CUTYPE == CUTYPE.UNKNOWN


def test_set_delegation_to_string(p):
    p.DELEGATED_FROM = "mailto:foo"
    assert p.DELEGATED_FROM == ("mailto:foo",)


def test_set_delegation_to_tuple(p):
    p.DELEGATED_TO = ("mailto:foo", "mailto:bar")
    assert p.DELEGATED_TO == ("mailto:foo", "mailto:bar")


def test_delete_delegation_to(p):
    p.DELEGATED_TO = ("mailto:foo", "mailto:bar")
    del p.DELEGATED_TO
    assert p.DELEGATED_TO == ()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ((), ""),
        (("mailto:foo",), 'DELEGATED-TO="mailto:foo"'),
        (("mailto:foo", "mailto:bar"), 'DELEGATED-TO="mailto:foo","mailto:bar"'),
        (('mailto:"asd"',), "DELEGATED-TO=\"mailto:^'asd^'\""),
    ],
)
def test_serialize_delegation_to(p, value, expected):
    p.DELEGATED_TO = value
    assert p.to_ical() == expected


@pytest.mark.parametrize(
    ("index", "expected"),
    [
        (0, FBTYPE.BUSY_UNAVAILABLE),
        (1, FBTYPE.BUSY),
        (2, FBTYPE.FREE),
    ],
)
def test_get_fbtype(calendars, index, expected):
    fb = calendars.issue_798_freebusy.freebusy[index]
    p: vPeriod = fb["FREEBUSY"]
    if isinstance(p, list):
        p = p[0]
    assert expected == p.FBTYPE


@pytest.fixture
def addr():
    return vCalAddress("mailto:foo")


def test_partstat_get(addr: vCalAddress):
    """test the default partstat"""
    assert addr.PARTSTAT == "NEEDS-ACTION"


def test_set_the_partstat(addr: vCalAddress):
    addr.PARTSTAT = PARTSTAT.ACCEPTED
    assert addr.PARTSTAT == "ACCEPTED"


def test_this_and_future():
    assert vDatetime(datetime(2019, 12, 10)).RANGE is None


def test_this_and_future_set():
    d = vDatetime(datetime(2019, 12, 10))
    d.RANGE = RANGE.THISANDFUTURE
    assert d.params["RANGE"] == "THISANDFUTURE"


def test_rsvp_default(addr):
    assert not addr.RSVP


@pytest.mark.parametrize("rsvp", [True, False])
def test_set_rsvp(addr: vCalAddress, rsvp):
    addr.RSVP = rsvp
    assert rsvp == addr.RSVP
    assert addr.params["RSVP"] == ("TRUE" if rsvp else "FALSE")


def test_sent_by(addr: vCalAddress):
    assert addr.SENT_BY is None


def test_set_sent_by(addr: vCalAddress):
    addr.SENT_BY = "mailto:asd"
    assert addr.SENT_BY == "mailto:asd"
    assert addr.params["SENT-BY"] == "mailto:asd"
    assert addr.params.to_ical() == b'SENT-BY="mailto:asd"'


@pytest.mark.parametrize("tzid", [None, "Europe/Berlin"])
def test_tzid(tzid, tzp: TZP):
    """Check that the TZID parameter is determined by the datetime value."""
    dt = vDatetime(tzp.localize(datetime(2019, 12, 10), tzid))
    assert dt.TZID == tzid


@pytest.mark.parametrize(
    ("index", "reltype"),
    [
        (0, RELTYPE.PARENT),
        (1, RELTYPE.SIBLING),
    ],
)
def test_reltype_example(calendars, index, reltype):
    """The reltype parameter in the examples."""
    event = calendars.issue_798_related_to.events[index]
    print(event.to_ical().decode())
    r: vText = event["RELATED-TO"]
    print(r)
    print(r.params)
    assert reltype == r.RELTYPE


def test_set_reltype(p):
    p.RELTYPE = RELTYPE.CHILD
    assert p.RELTYPE == RELTYPE.CHILD
    assert p.params["RELTYPE"] == "CHILD"

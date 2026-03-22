"""Tests for vCard properties within Component parsing."""

from __future__ import annotations

from icalendar import Component
from icalendar.prop import vAdr, vN, vOrg


class TestComponentIntegration:
    """Test vCard properties work within Component parsing."""

    def test_adr_in_component(self):
        """ADR property works in a Component."""
        comp = Component()
        comp.add("ADR", ("", "", "123 Main St", "City", "State", "12345", "USA"))
        ical = comp.to_ical()
        assert b"ADR:;;123 Main St;City;State;12345;USA" in ical

    def test_n_in_component(self):
        """N property works in a Component."""
        comp = Component()
        comp.add("N", ("Doe", "John", "M.", "Dr.", "Jr."))
        ical = comp.to_ical()
        assert b"N:Doe;John;M.;Dr.;Jr." in ical

    def test_org_in_component(self):
        """ORG property works in a Component."""
        comp = Component()
        comp.add("ORG", ("ABC Inc.", "Marketing"))
        ical = comp.to_ical()
        assert b"ORG:ABC Inc.;Marketing" in ical

    def test_vcard_in_vcalendar(self):
        """vCard properties can appear in VCALENDAR (non-standard but possible)."""
        ical_data = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
ADR:;;123 Main St;Springfield;IL;62701;USA
END:VCALENDAR
"""
        cal = Component.from_ical(ical_data)
        assert "ADR" in cal
        adr_value = cal["ADR"]
        # Should be parsed as vAdr
        assert isinstance(adr_value, vAdr)
        assert adr_value.fields.street == "123 Main St"

    def test_parse_n_from_component(self):
        """N property is parsed correctly from component."""
        ical_data = b"""BEGIN:VCARD
VERSION:4.0
N:Doe;John;M.;Dr.;Jr.
END:VCARD
"""
        comp = Component.from_ical(ical_data)
        assert "N" in comp
        n_value = comp["N"]
        assert isinstance(n_value, vN)
        assert n_value.fields.family == "Doe"
        assert n_value.fields.given == "John"

    def test_parse_org_from_component(self):
        """ORG property is parsed correctly from component."""
        ical_data = b"""BEGIN:VCARD
VERSION:4.0
ORG:ABC Inc.;Marketing;Sales
END:VCARD
"""
        comp = Component.from_ical(ical_data)
        assert "ORG" in comp
        org_value = comp["ORG"]
        assert isinstance(org_value, vOrg)
        assert org_value.name == "ABC Inc."
        assert org_value.units == ("Marketing", "Sales")

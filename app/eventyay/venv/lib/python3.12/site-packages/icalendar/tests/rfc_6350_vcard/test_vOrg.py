"""Tests for vCard ORG (Organization) property per RFC 6350."""

from __future__ import annotations

import pytest

from icalendar.prop import vOrg


class TestVOrgCreation:
    """Test vOrg creation and field access."""

    def test_org_creation_with_tuple(self):
        """Create ORG from tuple of fields."""
        org = vOrg(("ABC Inc.", "Marketing", "Sales"))
        assert org.fields == ("ABC Inc.", "Marketing", "Sales")

    def test_org_creation_with_list(self):
        """Create ORG from list of fields."""
        org = vOrg(["ABC Inc.", "Marketing"])
        assert org.fields == ("ABC Inc.", "Marketing")

    def test_org_creation_with_string(self):
        """Create ORG from vCard format string."""
        org = vOrg("ABC Inc.;Marketing;Sales")
        assert org.fields == ("ABC Inc.", "Marketing", "Sales")

    def test_org_requires_at_least_one_field(self):
        """ORG must have at least 1 field (organization name)."""
        with pytest.raises(ValueError, match="at least 1 field"):
            vOrg(())

    def test_org_variable_length(self):
        """ORG supports variable number of organizational units."""
        # Just organization name
        org1 = vOrg(("ABC Inc.",))
        assert len(org1.fields) == 1

        # Organization with 1 unit
        org2 = vOrg(("ABC Inc.", "Marketing"))
        assert len(org2.fields) == 2

        # Organization with many units
        org3 = vOrg(("ABC Inc.", "North America", "USA", "California", "Marketing"))
        assert len(org3.fields) == 5


class TestVOrgNameAndUnits:
    """Test vOrg name and units properties."""

    def test_name_property(self):
        """name property returns the organization name (first field)."""
        org = vOrg(("ABC Inc.", "Marketing", "Sales"))
        assert org.name == "ABC Inc."

    def test_name_property_single_field(self):
        """name property works with single field."""
        org = vOrg(("ABC Inc.",))
        assert org.name == "ABC Inc."

    def test_units_property(self):
        """units property returns organizational units (remaining fields)."""
        org = vOrg(("ABC Inc.", "Marketing", "Sales"))
        assert org.units == ("Marketing", "Sales")

    def test_units_property_single_field(self):
        """units property returns empty tuple when only name is present."""
        org = vOrg(("ABC Inc.",))
        assert org.units == ()

    def test_units_property_many_units(self):
        """units property returns all organizational units."""
        org = vOrg(("ABC Inc.", "North America", "USA", "California", "Marketing"))
        assert org.units == ("North America", "USA", "California", "Marketing")


class TestVOrgSerialization:
    """Test vOrg to_ical and from_ical."""

    def test_org_to_ical(self):
        """ORG to_ical generates semicolon-separated format."""
        org = vOrg(("ABC Inc.", "Marketing", "Sales"))
        result = org.to_ical()
        assert result == b"ABC Inc.;Marketing;Sales"

    def test_org_from_ical(self):
        """Parse ORG from vCard format."""
        result = vOrg.from_ical("ABC Inc.;Marketing;Sales")
        assert result == ("ABC Inc.", "Marketing", "Sales")

    def test_org_round_trip(self):
        """ORG survives round-trip through to_ical and from_ical."""
        original = ("ABC Inc.", "North American Division", "Marketing")
        org = vOrg(original)
        ical = org.to_ical()
        parsed = vOrg.from_ical(ical)
        assert parsed == original


class TestVOrgEscaping:
    """Test vOrg escaping behavior."""

    def test_org_semicolons_not_escaped_as_separators(self):
        """Semicolons in ORG are field separators, not escaped."""
        org = vOrg(("ABC Inc.", "Marketing", "Sales"))
        ical = org.to_ical()
        assert b"\\;" not in ical
        assert ical.count(b";") == 2  # 2 semicolons for 3 fields

    def test_org_commas_in_name_escaped(self):
        """Commas within ORG fields ARE escaped per RFC 6350."""
        org = vOrg(("ABC, Inc.", "Marketing"))
        ical = org.to_ical()
        assert b"\\," in ical
        # Round-trip preserves commas
        parsed = vOrg.from_ical(ical)
        assert parsed[0] == "ABC, Inc."


class TestVOrgIcalValue:
    """Test vOrg ical_value property."""

    def test_ical_value_returns_fields(self):
        """ical_value property returns the fields tuple."""
        org = vOrg(("ABC Inc.", "Marketing", "Sales"))
        assert org.ical_value == org.fields
        assert org.ical_value == ("ABC Inc.", "Marketing", "Sales")

"""Tests for vCard ADR (Address) property per RFC 6350."""

from __future__ import annotations

import pytest

from icalendar.prop import AdrFields, vAdr


class TestVAdrCreation:
    """Test vAdr creation and field access."""

    def test_adr_creation_with_tuple(self):
        """Create ADR from tuple of 7 fields."""
        adr = vAdr(("", "", "123 Main St", "Springfield", "IL", "62701", "USA"))
        assert adr.fields == AdrFields(
            po_box="",
            extended="",
            street="123 Main St",
            locality="Springfield",
            region="IL",
            postal_code="62701",
            country="USA",
        )

    def test_adr_creation_with_list(self):
        """Create ADR from list of 7 fields."""
        adr = vAdr(["", "", "123 Main St", "Springfield", "IL", "62701", "USA"])
        assert adr.fields.street == "123 Main St"

    def test_adr_creation_with_string(self):
        """Create ADR from vCard format string."""
        adr = vAdr(";;123 Main St;Springfield;IL;62701;USA")
        assert adr.fields.street == "123 Main St"
        assert adr.fields.locality == "Springfield"

    def test_adr_creation_with_adrfields(self):
        """Create ADR from AdrFields named tuple."""
        fields = AdrFields("", "", "123 Main St", "Springfield", "IL", "62701", "USA")
        adr = vAdr(fields)
        assert adr.fields is fields

    def test_adr_requires_7_fields(self):
        """ADR must have exactly 7 fields."""
        with pytest.raises(ValueError, match="exactly 7 fields"):
            vAdr(("too", "few"))

    def test_adr_named_field_access(self):
        """Access ADR fields by name."""
        adr = vAdr(
            ("PO Box 1", "Suite 200", "123 Main St", "City", "State", "12345", "USA")
        )
        assert adr.fields.po_box == "PO Box 1"
        assert adr.fields.extended == "Suite 200"
        assert adr.fields.street == "123 Main St"
        assert adr.fields.locality == "City"
        assert adr.fields.region == "State"
        assert adr.fields.postal_code == "12345"
        assert adr.fields.country == "USA"


class TestVAdrSerialization:
    """Test vAdr to_ical and from_ical."""

    def test_adr_to_ical(self):
        """ADR to_ical generates semicolon-separated format."""
        adr = vAdr(("", "", "123 Main St", "Springfield", "IL", "62701", "USA"))
        result = adr.to_ical()
        assert result == b";;123 Main St;Springfield;IL;62701;USA"

    def test_adr_from_ical(self):
        """Parse ADR from vCard format."""
        result = vAdr.from_ical(";;123 Main St;Springfield;IL;62701;USA")
        assert isinstance(result, AdrFields)
        assert result == AdrFields(
            "", "", "123 Main St", "Springfield", "IL", "62701", "USA"
        )

    def test_adr_round_trip(self):
        """ADR survives round-trip through to_ical and from_ical."""
        original = AdrFields("", "", "123 Main St", "Springfield", "IL", "62701", "USA")
        adr = vAdr(original)
        ical = adr.to_ical()
        parsed = vAdr.from_ical(ical)
        assert parsed == original


class TestVAdrEscaping:
    """Test vAdr escaping behavior."""

    def test_adr_semicolons_not_escaped_as_separators(self):
        """Semicolons in ADR are field separators, not escaped."""
        adr = vAdr(
            ("PO Box 1", "Suite 200", "123 Main St", "City", "State", "12345", "USA")
        )
        ical = adr.to_ical()
        # Semicolons between fields should NOT be escaped
        assert b"\\;" not in ical  # No escaped semicolons
        assert ical.count(b";") == 6  # 6 semicolons for 7 fields

    def test_adr_commas_in_field_are_escaped(self):
        """Commas within ADR fields ARE escaped."""
        adr = vAdr(("", "", "123 Main St, Apt 4", "Springfield", "IL", "62701", "USA"))
        ical = adr.to_ical()
        assert b"\\," in ical

    def test_adr_semicolons_in_field_are_escaped(self):
        """Semicolons within ADR field values ARE escaped."""
        adr = vAdr(("", "", "123 Main St; Apt 4", "Springfield", "IL", "62701", "USA"))
        ical = adr.to_ical()
        assert b"\\;" in ical
        # 6 separators + 1 escaped within field = 7 total semicolons
        assert ical.count(b";") == 7

        # Round-trip preserves the semicolon in the field value
        parsed = vAdr.from_ical(ical)
        assert parsed.street == "123 Main St; Apt 4"

    def test_adr_empty_fields_preserved(self):
        """Empty fields are preserved in ADR."""
        adr = vAdr(("", "", "123 Main St", "City", "", "12345", "USA"))
        ical = adr.to_ical()
        parsed = vAdr.from_ical(ical)
        assert parsed.po_box == ""
        assert parsed.extended == ""
        assert parsed.region == ""


class TestVAdrIcalValue:
    """Test vAdr ical_value property."""

    def test_ical_value_returns_fields(self):
        """ical_value property returns the AdrFields."""
        adr = vAdr(("", "", "123 Main St", "Springfield", "IL", "62701", "USA"))
        assert adr.ical_value == adr.fields
        assert isinstance(adr.ical_value, AdrFields)


class TestVAdrIssue137:
    """Test the exact example from Issue #137."""

    def test_issue_137_example(self):
        """Parse and round-trip the ADR example from Issue #137."""
        adr_value = ";2822 Email HQ;Suite 2821;RFCVille;PA;1521$;USA"
        parsed = vAdr.from_ical(adr_value)

        assert len(parsed) == 7
        assert parsed.po_box == ""
        assert parsed.extended == "2822 Email HQ"
        assert parsed.street == "Suite 2821"
        assert parsed.locality == "RFCVille"
        assert parsed.region == "PA"
        assert parsed.postal_code == "1521$"
        assert parsed.country == "USA"

        # Round-trip should preserve structure
        adr = vAdr(parsed)
        regenerated = adr.to_ical().decode("utf-8")
        assert regenerated == adr_value

"""Tests for vCard N (Name) property per RFC 6350."""

from __future__ import annotations

import pytest

from icalendar.prop import vN
from icalendar.prop.n import NFields


class TestVNCreation:
    """Test vN creation and field access."""

    def test_n_creation_with_tuple(self):
        """Create N from tuple of 5 fields."""
        n = vN(("Doe", "John", "M.", "Dr.", "Jr."))
        assert n.fields == NFields(
            family="Doe",
            given="John",
            additional="M.",
            prefix="Dr.",
            suffix="Jr.",
        )

    def test_n_creation_with_list(self):
        """Create N from list of 5 fields."""
        n = vN(["Doe", "John", "M.", "Dr.", "Jr."])
        assert n.fields.family == "Doe"

    def test_n_creation_with_string(self):
        """Create N from vCard format string."""
        n = vN("Doe;John;M.;Dr.;Jr.")
        assert n.fields.family == "Doe"
        assert n.fields.given == "John"

    def test_n_creation_with_nfields(self):
        """Create N from NFields named tuple."""
        fields = NFields("Doe", "John", "M.", "Dr.", "Jr.")
        n = vN(fields)
        assert n.fields is fields

    def test_n_requires_5_fields(self):
        """N must have exactly 5 fields."""
        with pytest.raises(ValueError, match="exactly 5 fields"):
            vN(("too", "few"))

    def test_n_named_field_access(self):
        """Access N fields by name."""
        n = vN(("Doe", "John", "Michael", "Dr.", "Jr."))
        assert n.fields.family == "Doe"
        assert n.fields.given == "John"
        assert n.fields.additional == "Michael"
        assert n.fields.prefix == "Dr."
        assert n.fields.suffix == "Jr."


class TestVNSerialization:
    """Test vN to_ical and from_ical."""

    def test_n_to_ical(self):
        """N to_ical generates semicolon-separated format."""
        n = vN(("Doe", "John", "M.", "Dr.", "Jr."))
        result = n.to_ical()
        assert result == b"Doe;John;M.;Dr.;Jr."

    def test_n_from_ical(self):
        """Parse N from vCard format."""
        result = vN.from_ical("Doe;John;M.;Dr.;Jr.")
        assert isinstance(result, NFields)
        assert result == NFields("Doe", "John", "M.", "Dr.", "Jr.")

    def test_n_round_trip(self):
        """N survives round-trip through to_ical and from_ical."""
        original = NFields("Doe", "John", "Michael", "Dr.", "Jr.")
        n = vN(original)
        ical = n.to_ical()
        parsed = vN.from_ical(ical)
        assert parsed == original


class TestVNEscaping:
    """Test vN escaping behavior."""

    def test_n_semicolons_not_escaped_as_separators(self):
        """Semicolons in N are field separators, not escaped."""
        n = vN(("Doe", "John", "M.", "Dr.", "Jr."))
        ical = n.to_ical()
        assert b"\\;" not in ical
        assert ical.count(b";") == 4  # 4 semicolons for 5 fields

    def test_n_empty_fields_preserved(self):
        """Empty fields are preserved in N."""
        n = vN(("Doe", "John", "", "", ""))
        ical = n.to_ical()
        parsed = vN.from_ical(ical)
        assert parsed.additional == ""
        assert parsed.prefix == ""
        assert parsed.suffix == ""

    def test_n_commas_in_suffix_escaped(self):
        """Commas within N fields ARE escaped per RFC 6350."""
        n = vN(("Doe", "John", "M.", "Dr.", "Jr.,M.D.,A.C.P."))
        ical = n.to_ical()
        assert b"\\," in ical
        # Round-trip preserves commas
        parsed = vN.from_ical(ical)
        assert parsed.suffix == "Jr.,M.D.,A.C.P."


class TestVNIcalValue:
    """Test vN ical_value property."""

    def test_ical_value_returns_fields(self):
        """ical_value property returns the NFields."""
        n = vN(("Doe", "John", "M.", "Dr.", "Jr."))
        assert n.ical_value == n.fields
        assert isinstance(n.ical_value, NFields)

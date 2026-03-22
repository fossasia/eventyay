"""Tests for issue #870: Add new() method to vCalAddress class."""

from datetime import datetime

import pytest

from icalendar import Event
from icalendar.prop import vCalAddress


class TestVCalAddressNew:
    """Test the vCalAddress.new() method functionality."""

    def test_new_with_email_only(self):
        """Test creating vCalAddress with email only."""
        addr = vCalAddress.new("test@test.com")

        assert str(addr) == "mailto:test@test.com"
        assert len(addr.params) == 0

    def test_new_with_mailto_prefix(self):
        """Test that existing mailto: prefix is preserved."""
        addr = vCalAddress.new("mailto:test@test.com")

        assert str(addr) == "mailto:test@test.com"

    def test_new_with_case_insensitive_mailto(self):
        """Test case-insensitive mailto: handling."""
        test_cases = [
            "MAILTO:test@test.com",
            "Mailto:test@test.com",
            "MailTo:test@test.com",
            "mAiLtO:test@test.com",
        ]

        for email in test_cases:
            addr = vCalAddress.new(email)
            assert str(addr) == email  # Preserve original case

    def test_new_with_cn_parameter(self):
        """Test creating vCalAddress with CN parameter."""
        addr = vCalAddress.new("test@test.com", cn="Test User")

        assert str(addr) == "mailto:test@test.com"
        assert addr.params["CN"] == "Test User"

    @pytest.mark.parametrize(
        ("argument", "value", "parameter", "expected_value"),
        [
            ("cutype", "INDIVIDUAL", "CUTYPE", "INDIVIDUAL"),
            ("cutype", "GROUP", "CUTYPE", "GROUP"),
            ("cutype", "RESOURCE", "CUTYPE", "RESOURCE"),
            ("cutype", "ROOM", "CUTYPE", "ROOM"),
            ("role", "REQ-PARTICIPANT", "ROLE", "REQ-PARTICIPANT"),
            ("role", "OPT-PARTICIPANT", "ROLE", "OPT-PARTICIPANT"),
            ("role", "NON-PARTICIPANT", "ROLE", "NON-PARTICIPANT"),
            ("role", "CHAIR", "ROLE", "CHAIR"),
            ("partstat", "NEEDS-ACTION", "PARTSTAT", "NEEDS-ACTION"),
            ("partstat", "ACCEPTED", "PARTSTAT", "ACCEPTED"),
            ("partstat", "DECLINED", "PARTSTAT", "DECLINED"),
            ("partstat", "TENTATIVE", "PARTSTAT", "TENTATIVE"),
            ("partstat", "DELEGATED", "PARTSTAT", "DELEGATED"),
            ("language", "en-US", "LANGUAGE", "en-US"),
            ("language", "de-DE", "LANGUAGE", "de-DE"),
            ("directory", "ldap://example.com", "DIR", "ldap://example.com"),
        ],
    )
    def test_new_with_string_parameters(
        self, argument, value, parameter, expected_value
    ):
        """Test vCalAddress.new() with various string parameters."""
        kwargs = {argument: value}
        addr = vCalAddress.new("test@test.com", **kwargs)

        assert str(addr) == "mailto:test@test.com"
        assert addr.params[parameter] == expected_value

    @pytest.mark.parametrize(
        ("rsvp_value", "expected_param"),
        [
            (True, "TRUE"),
            (False, "FALSE"),
        ],
    )
    def test_new_with_rsvp_parameter(self, rsvp_value, expected_param):
        """Test vCalAddress.new() with RSVP parameter."""
        addr = vCalAddress.new("test@test.com", rsvp=rsvp_value)

        assert str(addr) == "mailto:test@test.com"
        assert addr.params["RSVP"] == expected_param

    @pytest.mark.parametrize(
        ("delegate_param", "delegate_value", "expected_param", "expected_value"),
        [
            (
                "delegated_from",
                "sender@test.com",
                "DELEGATED-FROM",
                "mailto:sender@test.com",
            ),
            (
                "delegated_from",
                "mailto:sender@test.com",
                "DELEGATED-FROM",
                "mailto:sender@test.com",
            ),
            (
                "delegated_to",
                "delegate@test.com",
                "DELEGATED-TO",
                "mailto:delegate@test.com",
            ),
            (
                "delegated_to",
                "MAILTO:delegate@test.com",
                "DELEGATED-TO",
                "MAILTO:delegate@test.com",
            ),
            ("sent_by", "secretary@test.com", "SENT-BY", "mailto:secretary@test.com"),
            (
                "sent_by",
                "mailto:secretary@test.com",
                "SENT-BY",
                "mailto:secretary@test.com",
            ),
        ],
    )
    def test_new_with_email_parameters(
        self, delegate_param, delegate_value, expected_param, expected_value
    ):
        """Test vCalAddress.new() with email delegation parameters."""
        kwargs = {delegate_param: delegate_value}
        addr = vCalAddress.new("test@test.com", **kwargs)

        assert str(addr) == "mailto:test@test.com"
        assert addr.params[expected_param] == expected_value

    def test_new_with_all_parameters(self):
        """Test creating vCalAddress with all parameters."""
        addr = vCalAddress.new(
            "test@test.com",
            cn="Test User",
            cutype="INDIVIDUAL",
            delegated_from="sender@test.com",
            delegated_to="delegate@test.com",
            directory="ldap://example.com",
            language="en-US",
            partstat="ACCEPTED",
            role="REQ-PARTICIPANT",
            rsvp=True,
            sent_by="secretary@test.com",
        )

        assert str(addr) == "mailto:test@test.com"
        assert addr.params["CN"] == "Test User"
        assert addr.params["CUTYPE"] == "INDIVIDUAL"
        assert addr.params["DELEGATED-FROM"] == "mailto:sender@test.com"
        assert addr.params["DELEGATED-TO"] == "mailto:delegate@test.com"
        assert addr.params["DIR"] == "ldap://example.com"
        assert addr.params["LANGUAGE"] == "en-US"
        assert addr.params["PARTSTAT"] == "ACCEPTED"
        assert addr.params["ROLE"] == "REQ-PARTICIPANT"
        assert addr.params["RSVP"] == "TRUE"
        assert addr.params["SENT-BY"] == "mailto:secretary@test.com"

    def test_new_with_none_parameters_ignored(self):
        """Test that None parameters are ignored."""
        addr = vCalAddress.new(
            "test@test.com",
            cn=None,
            role=None,
            rsvp=None,
        )

        assert str(addr) == "mailto:test@test.com"
        assert "CN" not in addr.params
        assert "ROLE" not in addr.params
        assert "RSVP" not in addr.params

    def test_new_integration_with_event(self):
        """Test that vCalAddress.new() works with Event attendees."""
        addr = vCalAddress.new("test@test.com", cn="Test User", rsvp=True)
        event = Event.new(attendees=[addr])

        assert event.attendees == [addr]
        attendee = event.attendees[0]
        assert str(attendee) == "mailto:test@test.com"
        assert attendee.params["CN"] == "Test User"
        assert attendee.params["RSVP"] == "TRUE"


class TestVCalAddressNewErrorCases:
    """Test error cases for vCalAddress.new() method."""

    def test_new_requires_email(self):
        """Test that email parameter is required."""
        with pytest.raises(TypeError):
            vCalAddress.new()  # Missing required email argument

    def test_new_email_must_be_string(self):
        """Test that email must be a string."""
        with pytest.raises(TypeError, match="Email must be a string, not int"):
            vCalAddress.new(123)

        with pytest.raises(TypeError, match="Email must be a string, not list"):
            vCalAddress.new(["test@test.com"])


class TestVCalAddressNewExamples:
    """Test examples that demonstrate vCalAddress.new() usage."""

    def test_basic_usage_example(self):
        """Test basic usage example from docstring."""
        addr = vCalAddress.new("test@test.com")
        assert str(addr) == "mailto:test@test.com"

    def test_with_parameters_example(self):
        """Test example with parameters from docstring."""
        addr = vCalAddress.new("test@test.com", cn="Test User", role="CHAIR")
        assert addr.params["CN"] == "Test User"
        assert addr.params["ROLE"] == "CHAIR"

    def test_consistent_with_event_new(self):
        """Test that vCalAddress.new() integrates well with Event.new()."""
        # Both should create objects with .new() class method
        event = Event.new(summary="Test", start=datetime(2026, 1, 1, 12, 0))
        addr = vCalAddress.new("test@test.com", cn="Test User")

        # Should be able to add the address to event attendees
        event.attendees = [addr]
        assert len(event.attendees) == 1
        assert event.attendees[0].params["CN"] == "Test User"

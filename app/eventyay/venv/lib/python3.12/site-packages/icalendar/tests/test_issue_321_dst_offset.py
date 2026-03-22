"""Test for Issue #321 - AssertionError with VTIMEZONE containing only DAYLIGHT.

When a VTIMEZONE component contains only a DAYLIGHT subcomponent (no STANDARD),
converting it to a pytz timezone with lookup_tzid=False would fail with an
AssertionError.

The issue occurs because the code assumes it can find a non-DST (STANDARD)
transition to calculate the dst_offset, but when only DAYLIGHT exists, this
assumption fails.

Original issue: https://github.com/collective/icalendar/issues/321
Original PR with test case: https://github.com/collective/icalendar/pull/379
Test case by: @niccokunzmann
Fix by: @SashankBhamidi
"""

import pytest


class TestIssue321DstOffset:
    """Test VTIMEZONE conversion with only DAYLIGHT component."""

    @pytest.fixture
    def calendar_with_only_daylight(self, calendars):
        """Load calendar with VTIMEZONE containing only DAYLIGHT."""
        return calendars.issue_321_assert_dst_offset_is_not_false

    def test_vtimezone_with_only_daylight_does_not_raise_assertion(
        self, calendar_with_only_daylight
    ):
        """Test that VTIMEZONE with only DAYLIGHT can be converted to timezone.

        This tests the specific case from issue #321 where a calendar generated
        by khal had a VTIMEZONE with only DAYLIGHT, causing an AssertionError
        when calling to_tz().
        """
        timezone = list(calendar_with_only_daylight.walk())[1]
        assert timezone.name == "VTIMEZONE"
        assert timezone["TZID"] == "Europe/Berlin"

        # This should not raise AssertionError
        # With lookup_tzid=True (default), it finds Europe/Berlin in the system
        tz = timezone.to_tz()
        assert tz is not None

    def test_vtimezone_with_only_daylight_forced_creation(
        self, calendar_with_only_daylight
    ):
        """Test forced timezone creation with lookup_tzid=False.

        This is a more stringent test that forces timezone creation from the
        VTIMEZONE definition rather than looking up an existing timezone.
        This was the specific case that triggered the AssertionError.
        """
        pytest.importorskip("pytz", reason="This test requires pytz")
        from icalendar.timezone.pytz import PYTZ

        pytz_provider = PYTZ()

        timezone = list(calendar_with_only_daylight.walk())[1]

        # Force creation from VTIMEZONE definition
        # This used to fail with AssertionError
        tz = timezone.to_tz(tzp=pytz_provider, lookup_tzid=False)
        assert tz is not None
        assert tz.zone == "Europe/Berlin"

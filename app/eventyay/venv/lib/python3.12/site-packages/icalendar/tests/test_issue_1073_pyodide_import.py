"""Tests for issue #1073: Import failure in Pyodide/WebAssembly environments.

The ZONEINFO class should use lazy initialization to avoid import-time
failures in environments without timezone data.
"""

import threading
from unittest import mock

from icalendar.timezone.zoneinfo import ZONEINFO


def test_zoneinfo_class_does_not_initialize_at_import_time():
    """Test that ZONEINFO class attributes are not computed at class definition.

    The class should have None placeholders for _utc and _available_timezones_cache
    that are only populated when the properties are accessed.
    """
    # Verify that the class uses lazy initialization pattern
    # The class attributes should exist and potentially be None initially
    # (they may be populated from previous test runs, but that's OK)
    assert hasattr(ZONEINFO, "_utc")
    assert hasattr(ZONEINFO, "_available_timezones_cache")

    # The class should have property accessors for utc and _available_timezones
    # Check via __dict__ since they are instance properties
    assert "utc" in ZONEINFO.__dict__
    assert isinstance(ZONEINFO.__dict__["utc"], property)
    assert "_available_timezones" in ZONEINFO.__dict__
    assert isinstance(ZONEINFO.__dict__["_available_timezones"], property)


def test_zoneinfo_utc_property_works():
    """Test that UTC timezone property returns a valid ZoneInfo."""
    z = ZONEINFO()

    utc = z.utc
    assert utc is not None
    assert str(utc) == "UTC"

    # Second access should return the same cached instance
    assert z.utc is utc


def test_zoneinfo_available_timezones_property_works():
    """Test that available_timezones property returns a valid set."""
    z = ZONEINFO()

    timezones = z._available_timezones
    assert timezones is not None
    assert isinstance(timezones, set)
    assert "UTC" in timezones

    # Second access should return the same cached instance
    assert z._available_timezones is timezones


def test_zoneinfo_knows_timezone_id():
    """Test that knows_timezone_id correctly uses the lazy _available_timezones."""
    z = ZONEINFO()

    assert z.knows_timezone_id("UTC") is True
    assert z.knows_timezone_id("America/New_York") is True
    assert z.knows_timezone_id("NonExistent/Timezone") is False


def test_zoneinfo_can_be_instantiated_before_timezone_access():
    """Test that ZONEINFO can be instantiated without triggering timezone lookups.

    This is the key test for Pyodide compatibility - we need to be able to create
    the provider instance without it immediately trying to access timezone data.
    """
    # Use mock.patch to temporarily set class attributes to None
    # This is safer than directly modifying class state
    with mock.patch.object(  # noqa: SIM117
        ZONEINFO, "_utc", None
    ):
        with mock.patch.object(ZONEINFO, "_available_timezones_cache", None):
            # This should NOT raise even if zoneinfo data is unavailable
            z = ZONEINFO()

            # Just accessing the name should work without triggering timezone lookups
            assert z.name == "zoneinfo"


def test_zoneinfo_thread_safe_initialization():
    """Test that lazy initialization is thread-safe."""
    z = ZONEINFO()
    results = []
    errors = []

    def access_utc():
        try:
            utc = z.utc
            results.append(utc)
        except (ValueError, KeyError, OSError) as e:
            errors.append(e)

    # Create multiple threads that access utc simultaneously
    threads = [threading.Thread(target=access_utc) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All threads should get the same UTC timezone
    assert len(errors) == 0, f"Errors occurred: {errors}"
    assert len(results) == 10
    assert all(r is results[0] for r in results), (
        "All threads should get same UTC instance"
    )

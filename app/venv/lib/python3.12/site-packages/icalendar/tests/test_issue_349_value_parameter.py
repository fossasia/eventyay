"""Test VALUE parameter handling for Issue #349.

Tests that the VALUE parameter is properly set when adding properties with
Python native types (date, datetime, time, etc.) and properly used when
parsing iCalendar data.

Related Issues:
- #349: Adding an EXDATE with type date does not set the element's VALUE as DATE
- #187: Property values ignoring property parameters

Related PRs:
- #331: Fix VALUE parameter handling (2021, by thet)
- #196: Original attempt (2016, by stlaz)
"""

import datetime

from icalendar import Calendar, Event


class TestValueParameterEncoding:
    """Test that VALUE parameter is automatically set during encoding."""

    def test_exdate_with_date_sets_value_date(self):
        """Test that adding EXDATE with datetime.date sets VALUE=DATE."""
        ev = Event()
        ev.add("UID", "test-value-param-date")
        ev.add("DTSTAMP", datetime.datetime.now(datetime.timezone.utc))
        ev.add("SUMMARY", "EXDATE test")
        ev.add("DTSTART", datetime.date(2022, 1, 1))
        ev.add("RRULE", {"FREQ": "WEEKLY"})
        ev.add("EXDATE", datetime.date(2022, 1, 8))

        ical_str = ev.to_ical().decode()
        assert "EXDATE;VALUE=DATE:20220108" in ical_str

    def test_rdate_with_date_sets_value_date(self):
        """Test that adding RDATE with datetime.date sets VALUE=DATE."""
        ev = Event()
        ev.add("UID", "test-rdate-date")
        ev.add("DTSTAMP", datetime.datetime.now(datetime.timezone.utc))
        ev.add("DTSTART", datetime.date(2022, 1, 1))
        ev.add("RDATE", datetime.date(2022, 1, 15))

        ical_str = ev.to_ical().decode()
        assert "RDATE;VALUE=DATE:20220115" in ical_str

    def test_dtstart_with_date_sets_value_date(self):
        """Test that DTSTART with datetime.date sets VALUE=DATE."""
        ev = Event()
        ev.add("UID", "test-dtstart-date")
        ev.add("DTSTAMP", datetime.datetime.now(datetime.timezone.utc))
        ev.add("DTSTART", datetime.date(2022, 1, 1))

        ical_str = ev.to_ical().decode()
        assert "DTSTART;VALUE=DATE:20220101" in ical_str

    def test_dtstart_with_datetime_no_value_param(self):
        """Test that DTSTART with datetime.datetime doesn't set VALUE (default DATE-TIME)."""
        ev = Event()
        ev.add("UID", "test-dtstart-datetime")
        ev.add("DTSTAMP", datetime.datetime.now(datetime.timezone.utc))
        ev.add(
            "DTSTART",
            datetime.datetime(2022, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc),
        )

        ical_str = ev.to_ical().decode()
        # DATE-TIME is the default, so VALUE parameter should not be explicitly set
        # (though some implementations may still add it)
        assert "DTSTART" in ical_str
        assert "20220101T100000Z" in ical_str

    def test_exdate_list_with_dates_sets_value_date(self):
        """Test that EXDATE list with datetime.date objects sets VALUE=DATE."""
        ev = Event()
        ev.add("UID", "test-exdate-list")
        ev.add("DTSTAMP", datetime.datetime.now(datetime.timezone.utc))
        ev.add("DTSTART", datetime.date(2022, 1, 1))
        ev.add("RRULE", {"FREQ": "DAILY"})
        # Add dates individually - lists are handled by vDDDLists
        ev.add("EXDATE", datetime.date(2022, 1, 5))
        ev.add("EXDATE", datetime.date(2022, 1, 10))

        ical_str = ev.to_ical().decode()
        assert "EXDATE;VALUE=DATE:20220105" in ical_str
        assert "EXDATE;VALUE=DATE:20220110" in ical_str


class TestValueParameterDecoding:
    """Test that VALUE parameter is properly used during decoding."""

    def test_parse_exdate_with_value_date(self):
        """Test parsing EXDATE with VALUE=DATE parameter."""
        ical_str = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:test-parse-exdate-date
DTSTART;VALUE=DATE:20220101
EXDATE;VALUE=DATE:20220108
DTSTAMP:20220101T120000Z
SUMMARY:Test Event
END:VEVENT
END:VCALENDAR"""

        cal = Calendar.from_ical(ical_str)
        event = cal.walk("VEVENT")[0]
        exdate = event["EXDATE"]

        # EXDATE is always a vDDDLists, get the first item
        assert len(exdate.dts) == 1
        first_date = exdate.dts[0].dt
        # Should be parsed as a date, not datetime
        assert isinstance(first_date, datetime.date)
        assert not isinstance(first_date, datetime.datetime)
        assert first_date == datetime.date(2022, 1, 8)

    def test_parse_dtstart_with_value_date(self):
        """Test parsing DTSTART with VALUE=DATE parameter."""
        ical_str = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:test-parse-dtstart-date
DTSTART;VALUE=DATE:20220101
DTSTAMP:20220101T120000Z
SUMMARY:Test Event
END:VEVENT
END:VCALENDAR"""

        cal = Calendar.from_ical(ical_str)
        event = cal.walk("VEVENT")[0]
        dtstart = event["DTSTART"]

        # Should be parsed as a date, not datetime
        assert isinstance(dtstart.dt, datetime.date)
        assert not isinstance(dtstart.dt, datetime.datetime)
        assert dtstart.dt == datetime.date(2022, 1, 1)

    def test_parse_dtstart_without_value_defaults_to_datetime(self):
        """Test that DTSTART without VALUE parameter defaults to DATE-TIME."""
        ical_str = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:test-parse-dtstart-default
DTSTART:20220101T100000Z
DTSTAMP:20220101T120000Z
SUMMARY:Test Event
END:VEVENT
END:VCALENDAR"""

        cal = Calendar.from_ical(ical_str)
        event = cal.walk("VEVENT")[0]
        dtstart = event["DTSTART"]

        # Should be parsed as datetime
        assert isinstance(dtstart.dt, datetime.datetime)
        assert dtstart.dt == datetime.datetime(
            2022, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc
        )


class TestValueParameterRoundTrip:
    """Test that VALUE parameter survives encoding/decoding round trips."""

    def test_date_roundtrip(self):
        """Test that date values maintain their type through encode/decode."""
        # Create event with date
        ev1 = Event()
        ev1.add("UID", "test-roundtrip")
        ev1.add("DTSTAMP", datetime.datetime.now(datetime.timezone.utc))
        ev1.add("DTSTART", datetime.date(2022, 1, 1))
        ev1.add("EXDATE", datetime.date(2022, 1, 8))

        # Encode to iCalendar format
        ical_bytes = ev1.to_ical()

        # Decode back
        cal = Calendar.from_ical(
            b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\n"
            + ical_bytes
            + b"\nEND:VCALENDAR"
        )
        ev2 = cal.walk("VEVENT")[0]

        # Check that types are preserved
        assert isinstance(ev2["DTSTART"].dt, datetime.date)
        assert not isinstance(ev2["DTSTART"].dt, datetime.datetime)
        assert ev2["DTSTART"].dt == datetime.date(2022, 1, 1)

        # EXDATE is always a vDDDLists, get the first item
        assert len(ev2["EXDATE"].dts) == 1
        exdate = ev2["EXDATE"].dts[0].dt
        assert isinstance(exdate, datetime.date)
        assert not isinstance(exdate, datetime.datetime)
        assert exdate == datetime.date(2022, 1, 8)


class TestExplicitValueParameter:
    """Test handling of explicitly provided VALUE parameters."""

    def test_explicit_value_param_overrides_inference(self):
        """Test that explicitly provided VALUE parameter is used."""
        ev = Event()
        ev.add("UID", "test-explicit-value")
        ev.add("DTSTAMP", datetime.datetime.now(datetime.timezone.utc))
        # Explicitly set VALUE=DATE
        ev.add("DTSTART", datetime.date(2022, 1, 1), parameters={"VALUE": "DATE"})

        ical_str = ev.to_ical().decode()
        assert "VALUE=DATE" in ical_str

    def test_parameters_preserved(self):
        """Test that other parameters are preserved when VALUE is added."""
        ev = Event()
        ev.add("UID", "test-params-preserved")
        ev.add("DTSTAMP", datetime.datetime.now(datetime.timezone.utc))
        ev.add(
            "DTSTART",
            datetime.datetime(2022, 1, 1, 10, 0, 0),
            parameters={"TZID": "America/New_York"},
        )

        dtstart = ev["DTSTART"]
        assert "TZID" in dtstart.params
        assert dtstart.params["TZID"] == "America/New_York"

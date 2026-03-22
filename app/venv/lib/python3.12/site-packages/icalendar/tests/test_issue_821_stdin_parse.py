# tests/test_cli_stdin_argparse.py
import contextlib
import io
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from icalendar import Calendar, cli

INPUT = """
BEGIN:VCALENDAR
VERSION:2.0
CALSCALE:GREGORIAN
BEGIN:VEVENT
SUMMARY:Test Summary
ORGANIZER:organizer@test.test
ATTENDEE:attendee1@example.com
ATTENDEE:attendee2@test.test
COMMENT:Comment
DTSTART;TZID=Europe/Warsaw:20220820T103400
DTEND;TZID=Europe/Warsaw:20220820T113400
LOCATION:New Amsterdam, 1000 Sunrise Test Street
DESCRIPTION: Test Description
END:VEVENT
BEGIN:VEVENT
ORGANIZER:organizer@test.test
ATTENDEE:attendee1@example.com
SUMMARY:Test summary
DTSTART;TZID=Europe/Warsaw:20220820T200000
DTEND;TZID=Europe/Warsaw:20220820T203000
LOCATION:New Amsterdam, 1010 Test Street
DESCRIPTION:Test Description\\nThis one is multiline
END:VEVENT
BEGIN:VEVENT
UID:1
SUMMARY:TEST
DTSTART:20220511
DURATION:P5D
END:VEVENT
END:VCALENDAR
""".lstrip()


def _local_datetime(dt: str) -> str:
    """
    Match the CLI's behavior: display datetimes in the *local* timezone.
    The source times are Europe/Warsaw; convert to local tz for comparison.
    """
    return (
        datetime.strptime(dt, "%Y%m%dT%H%M%S")
        .replace(tzinfo=ZoneInfo("Europe/Warsaw"))
        .astimezone()
        .strftime("%c")
    )


# datetimes are displayed in the local timezone, so build expected strings at runtime
_firststart = _local_datetime("20220820T103400")
_firstend = _local_datetime("20220820T113400")
_secondstart = _local_datetime("20220820T200000")
_secondend = _local_datetime("20220820T203000")

PROPER_OUTPUT = f"""    Organizer: organizer <organizer@test.test>
    Attendees:
     attendee1 <attendee1@example.com>
     attendee2 <attendee2@test.test>
    Summary    : Test Summary
    Starts     : {_firststart}
    End        : {_firstend}
    Duration   : 1:00:00
    Location   : New Amsterdam, 1000 Sunrise Test Street
    Comment    : Comment
    Description:
      Test Description

    Organizer: organizer <organizer@test.test>
    Attendees:
     attendee1 <attendee1@example.com>
    Summary    : Test summary
    Starts     : {_secondstart}
    End        : {_secondend}
    Duration   : 0:30:00
    Location   : New Amsterdam, 1010 Test Street
    Comment    :{" "}
    Description:
     Test Description
     This one is multiline

    Organizer:{" "}
    Attendees:

    Summary    : TEST
    Starts     : Wed May 11 00:00:00 2022
    End        : Mon May 16 00:00:00 2022
    Duration   : 5 days, 0:00:00
    Location   :{" "}
    Comment    :{" "}
    Description:
    {" "}

""".replace("\r\n", "\n")  # normalize newlines just in case


class TestIcalendarCLIArgparseStdin(unittest.TestCase):
    def test_cli_with_stdin_dash(self):
        """
        Validate that `type=argparse.FileType("r", ...)` maps '-' to sys.stdin
        and the CLI prints the expected, fully formatted output.
        """
        # Provide INPUT via stdin
        fake_stdin = io.StringIO(INPUT)
        captured = io.StringIO()

        with (
            mock.patch.object(sys, "stdin", fake_stdin),
            mock.patch.object(sys, "argv", ["icalendar", "-"]),
            contextlib.redirect_stdout(captured),
        ):
            cli.main()

        assert captured.getvalue() == PROPER_OUTPUT

    def test_cli_with_file_path(self):
        """
        Validate that passing a real file path also yields the same output.
        """
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tf:
            tf.write(INPUT)
            tmpname = tf.name

        try:
            captured = io.StringIO()
            with (
                mock.patch.object(sys, "argv", ["icalendar", tmpname]),
                contextlib.redirect_stdout(captured),
            ):
                cli.main()
            assert captured.getvalue() == PROPER_OUTPUT
        finally:
            Path(tmpname).unlink()

    def test_view_direct_matches_cli(self):
        """
        Optional: sanity check that the lower-level view(event) path
        still matches what the CLI emits, to guard against formatting drift.
        """
        cal = Calendar.from_ical(INPUT)
        manual = []
        for evt in cal.walk("vevent"):
            manual.append(cli.view(evt))
            manual.append("")  # the CLI prints a blank line after each event
        manual_output = "\n".join(manual) + "\n"  # trailing newline

        assert manual_output == PROPER_OUTPUT


if __name__ == "__main__":
    unittest.main()

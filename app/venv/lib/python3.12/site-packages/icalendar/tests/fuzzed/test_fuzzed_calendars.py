"""This test tests all fuzzed calendars.

To add a new calendar test, echo the base64 calendar string into a file.

- The file is in src/icalendar/tests/calendars
- The file name contains "fuzz_testcase" and ends with ".ics"

Templace code to create a new test case:

.. code-block:: console

    echo "" | base64 -d > src/icalendar/tests/calendars/fuzz_testcase_.ics

"""

import icalendar.cal.calendar
from icalendar.tests.fuzzed import fuzz_v1_calendar


def test_fuzz_v1(fuzz_v1_calendar_path):
    """Test a calendar."""
    calendar = fuzz_v1_calendar_path.read_bytes()
    print(repr(calendar))
    fuzz_v1_calendar(
        icalendar.cal.calendar.Calendar.from_ical,
        calendar,
        multiple=True,
        should_walk=True,
    )

"""We can get time information that is actually of the WRONG value.

We can still parse it and correct the value parameter.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from icalendar import Event


@pytest.mark.parametrize(
    ("string", "expected_params", "expected_property_value"),
    [
        (":20150217", {}, date(2015, 2, 17)),
        (";VALUE=DATETIME:20150217", {"VALUE": "DATETIME"}, date(2015, 2, 17)),
        (
            ";VALUE=DATE:20150217T095800",
            {"VALUE": "DATE"},
            datetime(2015, 2, 17, 9, 58, 0),
        ),
        (
            ";VALUE=DATE:20150217T095800Z",
            {"VALUE": "DATE"},
            datetime(2015, 2, 17, 9, 58, 0, tzinfo=ZoneInfo("UTC")),
        ),
        (
            ";TZID=Europe/Berlin:20150217",
            {"TZID": "Europe/Berlin"},
            datetime(2015, 2, 17, tzinfo=ZoneInfo("Europe/Berlin")),
        ),
        (
            ";TZID=Europe/Berlin:20150217T095800Z",
            {"TZID": "Europe/Berlin"},
            datetime(2015, 2, 17, 9, 58, 0, tzinfo=ZoneInfo("Europe/Berlin")),
        ),
    ],
)
def test_wrong_dates_are_converted(string, expected_params, expected_property_value):
    """We convert these dates to the correct value if they turn up.

    We want to make sure that these are working, have values and do not throw exceptions.
    Information should not get lost except if it is contradictory.
    So, the tests can be changed if a different resolution is needed.

    The problem: The VALUE parameter might not correspond to the actual value.
    However, we correctly parse the value and do not lose information.
    """
    event = Event.from_ical(f"""
BEGIN:VEVENT
DTSTART{string}
END:VEVENT
""")
    dt = event.get("dtstart")
    test = f"{dt} should be {expected_property_value} with {expected_params}"
    assert dt.params == expected_params, test
    assert dt.dt == expected_property_value, test

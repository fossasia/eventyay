"""This is a collection of test files that are generated from the fuzzer.

The fuzzer finds the cases in which the icalendar module breaks.
These test cases reproduce the failure.
Some more tests can be added to make sure that the behavior works properly.
"""

_value_error_matches = [
    "component",
    "parse",
    "Expected",
    "Wrong date format",
    "END encountered",
    "vDDD",
    "recurrence",
    "Offset must",
    "Invalid iCalendar",
    "alue MUST",
    "Key name",
    "Invalid content line",
    "Content line could not be parsed",
    "does not exist",
    "base 64",
    "must use datetime",
    "Unknown date type",
    "Wrong",
    "Start time",
    "iCalendar",
    "recurrence",
    "float, float",
    "utc offset",
    "parent",
    "MUST be a datetime",
    "Invalid month:",
    "must have exactly",  # vCard field count validation (ADR, N)
    "must have at least",  # vCard ORG minimum field validation
]


def fuzz_v1_calendar(
    from_ical, calendar_string: str, multiple: bool, should_walk: bool
):
    """Take a from_ical function and reproduce the error.

    The calendar_string is a fuzzed input.
    """
    try:
        cal = from_ical(calendar_string, multiple=multiple)

        if not multiple:
            cal = [cal]
        for c in cal:
            if should_walk:
                for event in c.walk("VEVENT"):
                    event.to_ical()
            else:
                c.to_ical()
    except (ValueError, TypeError) as e:
        if any(m in str(e) for m in _value_error_matches):
            return -1
        raise

"""Tests for Issue 355.

see https://github.com/collective/icalendar/issues/355
"""

import pytest

from icalendar.parser import unescape_backslash


def test_facebook_link_is_correctly_parsed(events):
    """The facebook link must not be damaged.

    see https://github.com/collective/icalendar/pull/356#issuecomment-1222626128
    """
    assert (
        events.issue_355_url_escaping["DESCRIPTION"]
        == "https://www.facebook.com/events/756119502186737/?acontext=%7B%22source%22%3A5%2C%22action_history%22%3A[%7B%22surface%22%3A%22page%22%2C%22mechanism%22%3A%22main_list%22%2C%22extra_data%22%3A%22%5C%22[]%5C%22%22%7D]%2C%22has_source%22%3Atrue%7D"
    )


def test_other_facebook_link_is_correctly_parsed(events):
    """The facebook link must not be damaged.

    see https://github.com/collective/icalendar/pull/356#issuecomment-1265872696
    """
    expected_result = "https://www.facebook.com/events/756119502186737/?acontext=%7B%22source%22%3A5%2C%22action_history%22%3A[%7B%22surface%22%3A%22page%22%2C%22mechanism%22%3A%22main_list%22%2C%22extra_data%22%3A%22%5C%22[]%5C%22%22%7D]%2C%22has_source%22%3Atrue%7D"
    assert events.issue_355_url_escaping_2["DESCRIPTION"] == expected_result


def test_empty_quotes(events):
    """Make sure that empty quoted parameter values are supported."""
    assert events.issue_355_url_escaping_empty_param["ORGANIZER"].params["CN"] == ""


@pytest.mark.parametrize(
    ("input_string", "expected_result", "message"),
    [
        ("test 123", "test 123", "No escapes, should remain unchanged."),
        (r"\\n", "\\n", "No escape after escaped backslash."),
        (r"\\,", "\\,", "No escape after escaped backslash."),
        (r"\\;", "\\;", "No escape after escaped backslash."),
        (r"\\:", "\\:", "No escape after escaped backslash."),
        (r"\\N", "\\N", "No escape after escaped backslash."),
        ("-\\n-", "-\n-", "Newline escape."),
        ("-\\,", "-,", "Comma escape."),
        ("-\\;", "-;", "Semicolon escape."),
        ("-\\:", "-:", "Colon escape."),
        ("-\\N-", "-\n-", "Newline escape."),
    ],
)
def test_unescape_backslash(input_string, expected_result, message):
    """Test unescape_backslash function with various inputs."""
    assert unescape_backslash(input_string) == expected_result, (
        f"{message}: {input_string} -> {expected_result}"
    )

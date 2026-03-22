"""Tests for split_on_unescaped_semicolon function."""

from __future__ import annotations

import pytest

from icalendar.parser import split_on_unescaped_semicolon


@pytest.mark.parametrize(
    ("input_str", "expected"),
    [
        # Simple cases
        ("a;b;c", ["a", "b", "c"]),
        ("single", ["single"]),
        # Escaped semicolons are not split points
        (r"a\;b\;c", ["a;b;c"]),
        # Mixed escaped and unescaped
        (r"field1\;with;field2", ["field1;with", "field2"]),
        # vCard ADR example
        (r"PO Box 123\;Suite 200;City", ["PO Box 123;Suite 200", "City"]),
        # Empty string returns single empty field
        ("", [""]),
        # Empty fields are preserved
        (";;a;b;;c;", ["", "", "a", "b", "", "c", ""]),
        # Escaped backslash before semicolon (the backslash is escaped, not the semicolon)
        (r"field1\\;field2", ["field1\\", "field2"]),
        # Escaped backslash followed by escaped semicolon
        (r"field1\\\;still field1;field2", ["field1\\;still field1", "field2"]),
        # Multiple escaped backslashes
        (r"a\\\\;b", ["a\\\\", "b"]),
        # Escaped comma (should not affect semicolon splitting)
        (r"a\,b;c\,d", ["a,b", "c,d"]),
    ],
    ids=[
        "simple_split",
        "no_semicolons",
        "escaped_semicolons_not_split",
        "mixed_escaped_and_unescaped",
        "vcard_adr_example",
        "empty_string",
        "empty_fields_preserved",
        "escaped_backslash_before_semicolon",
        "escaped_backslash_then_escaped_semicolon",
        "multiple_escaped_backslashes",
        "escaped_comma_no_effect",
    ],
)
def test_split_on_unescaped_semicolon(input_str: str, expected: list[str]) -> None:
    """Test splitting strings on unescaped semicolons."""
    result = split_on_unescaped_semicolon(input_str)
    assert result == expected

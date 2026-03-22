"""Tests for vCard structured properties per RFC 6350.

vCard structured properties (ADR, N, ORG) use semicolons as field separators.
These semicolons should NOT be escaped, unlike iCalendar TEXT values.
"""

"""Tests for eventyay.api.utils.get_protocol.

Covers:
- Normal https / http URLs
- Schemeless URLs (//host/path)     → should fall back to 'https'
- None input                        → should fall back to 'https'
- Empty / whitespace-only strings   → should fall back to 'https'
- Bare hostname (no scheme or //)   → should fall back to 'https'
- Relative paths                    → should fall back to 'https'
- Mixed-case scheme                 → always returned in lower-case
"""

import pytest

from eventyay.api.utils import get_protocol


@pytest.mark.parametrize(
    "url, expected",
    [
        # Normal cases
        ("https://example.com", "https"),
        ("http://example.com/path", "http"),
        ("https://example.com:8080/api/v1/", "https"),
        # Edge cases – schemeless URLs with authority
        ("//example.com/path", "https"),
        # Edge cases – bare hostname (no scheme, no //)
        ("example.com", "https"),
        ("example.com/some/path", "https"),
        # Edge cases – relative paths (no scheme, no host)
        ("/relative/path", "https"),
        # Edge cases – no URL at all
        (None, "https"),
        ("", "https"),
        # Edge cases – whitespace-only strings
        ("   ", "https"),
        # Mixed-case scheme must be normalised to lower-case
        ("HTTPS://example.com", "https"),
        ("HTTP://example.com", "http"),
        # Unusual but valid schemes
        ("ftp://files.example.com", "ftp"),
    ],
)
def test_get_protocol(url, expected):
    assert get_protocol(url) == expected

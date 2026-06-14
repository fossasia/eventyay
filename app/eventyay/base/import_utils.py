"""Shared CSV header-matching utilities used by all import forms."""
from collections.abc import Iterable


def normalize_header_value(value: str | None) -> str:
    """Normalise a CSV header or suggestion string for fuzzy matching.

    Lowercases, collapses whitespace, strips trailing punctuation, and
    normalises common Unicode quote characters so that headers such as
    ``"Given name"`` and ``given_name`` compare as equal.
    """
    if not value:
        return ''
    value = value.lower().replace('-', ' ').replace('_', ' ')
    value = value.replace('\u2019', "'").replace('\u2018', "'").replace('\u201c', '"').replace('\u201d', '"')
    return ''.join(value.split()).rstrip('.')


def build_header_map(headers: Iterable[str]) -> dict[str, str]:
    """Return a ``{normalised_key: original_header}`` mapping.

    Pre-building this map once and reusing it with :func:`match_header` avoids
    re-normalising the full header list for every column during import-form
    construction.
    """
    return {normalize_header_value(h): h for h in headers}


def match_header(
    headers_or_map: Iterable[str] | dict[str, str],
    candidates: Iterable[str],
) -> str | None:
    """Return the first header that matches any of the *candidates*.

    *headers_or_map* may be either a raw iterable of header strings (a map is
    built on the fly) or a pre-built dict returned by :func:`build_header_map`
    (preferred when calling in a tight loop to avoid repeated normalisation).

    Returns ``None`` when no candidate matches any header.
    """
    header_map: dict[str, str] = (
        headers_or_map if isinstance(headers_or_map, dict) else build_header_map(headers_or_map)
    )
    for candidate in candidates:
        normalized = normalize_header_value(candidate)
        if normalized in header_map:
            return header_map[normalized]
    return None


def setting_is_truthy(value) -> bool:
    if value is True:
        return True
    if value in (False, None, '', 0):
        return False
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'on', 'yes')
    return bool(value)

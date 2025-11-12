"""Timezone conversion utilities for browser timezone support."""
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def get_browser_timezone(tz_string: Optional[str], fallback: str = 'UTC') -> ZoneInfo:
    """
    Resolve a :class:`zoneinfo.ZoneInfo` from user-provided input.

    Args:
        tz_string: Timezone identifier provided by the browser.
        fallback: Identifier to use when ``tz_string`` is empty or invalid (default: ``'UTC'``).

    Returns:
        :class:`zoneinfo.ZoneInfo` instance representing the resolved timezone.
    """
    candidates = [tz_string, fallback, 'UTC']

    for candidate in candidates:
        if not candidate:
            continue
        try:
            return ZoneInfo(candidate)
        except ZoneInfoNotFoundError:
            continue

    # ``UTC`` should always be available, but return it explicitly to satisfy type checkers.
    return ZoneInfo('UTC')


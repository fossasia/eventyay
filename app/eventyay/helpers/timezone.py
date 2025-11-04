"""
Timezone conversion utilities for browser timezone support
"""
import pytz


def get_browser_timezone(source, fallback='UTC'):
    """
    Resolve a pytz timezone from user-provided input.

    Args:
        source: Either a timezone string or a mapping with a ``browser_timezone`` key.
        fallback: Fallback timezone string if no usable timezone is provided (default: 'UTC').

    Returns:
        pytz timezone object.
    """
    if isinstance(source, str):
        browser_tz_str = source or fallback
    else:
        try:
            browser_tz_str = source.get('browser_timezone', fallback) or fallback
        except AttributeError:
            browser_tz_str = fallback

    try:
        return pytz.timezone(browser_tz_str)
    except pytz.UnknownTimeZoneError:
        return pytz.UTC


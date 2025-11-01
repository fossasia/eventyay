"""
Timezone conversion utilities for browser timezone support
"""
import pytz


def get_browser_timezone(form_data, fallback='UTC'):
    """
    Get browser timezone from form data
    
    Args:
        form_data: Dictionary containing cleaned form data
        fallback: Fallback timezone string if browser timezone not provided (default: 'UTC')
    
    Returns:
        pytz timezone object
    """
    browser_tz_str = form_data.get('browser_timezone') or fallback
    try:
        return pytz.timezone(browser_tz_str)
    except pytz.UnknownTimeZoneError:
        return pytz.UTC


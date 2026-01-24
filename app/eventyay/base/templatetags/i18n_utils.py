import json
from django import template
from i18nfield.strings import LazyI18nString

register = template.Library()

@register.filter
def localize_json(value):
    """
    Safely converts a value (LazyI18nString, dict, or JSON string) into a localized string.
    This is useful for settings fields that might be stored as JSON strings but need 
    to be displayed as localized text in templates.
    Only treats None and empty strings as empty; falsy non-text values (e.g. 0, False)
    are preserved and passed through to later handling.
    """
    if value is None or value == "":
        return ""

    # Try parsing as JSON if it's a string
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                value = LazyI18nString(parsed)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    # If it's a dict, convert to LazyI18nString
    if isinstance(value, dict):
        value = LazyI18nString(value)

    # Convert LazyI18nString (or any other object) to string to force localization
    return str(value)

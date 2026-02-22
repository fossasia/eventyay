from django import template
from i18nfield.strings import LazyI18nString

register = template.Library()


@register.filter(name='localize')
def localize(value):
    """
    Ensures that the value is localized.
    Handles dicts (JSON representation of I18nString) and LazyI18nString objects.
    """
    if isinstance(value, dict):
        return str(LazyI18nString(value))
    if isinstance(value, LazyI18nString):
        return str(value)
    return value


@register.filter(name='append_colon')
def append_colon(text):
    """
    Appends a colon to the text if it does not end with a punctuation mark.
    """
    text = str(text).strip()
    if not text:
        return ''
    return text if text[-1] in ['.', '!', '?', ':', ';'] else f'{text}:'

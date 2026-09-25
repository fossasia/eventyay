"""Template tags and filters for eventyay theme system."""

import re

from django import template
from django.utils.safestring import mark_safe


register = template.Library()

# Pattern to detect case-insensitive closing style tags, e.g. </style>, </style >, < / style >
_STYLE_CLOSE_RE = re.compile(r'<\s*/\s*style', re.IGNORECASE)


@register.filter(name='escape_style')
def escape_style(value: str) -> str:
    """
    Encode CSS for safe inclusion inside an HTML <style> block.

    Preserves valid CSS syntax (e.g. selectors with '>', quotes, ampersands)
    while neutralizing case-insensitive '</style' sequences by replacing them
    with CSS-escaped '\\3c /style' to prevent breaking out into HTML context.
    """
    if not value:
        return ''
    sanitized = _STYLE_CLOSE_RE.sub(r'\\3c /style', str(value))
    return mark_safe(sanitized)

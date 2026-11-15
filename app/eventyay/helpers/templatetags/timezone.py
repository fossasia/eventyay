from django import template

from eventyay.helpers.timezone import format_timezone_name


register = template.Library()


@register.filter
def timezone_display(value: str | None) -> str:
    """Format a timezone identifier for display without changing its value."""
    return format_timezone_name(value)

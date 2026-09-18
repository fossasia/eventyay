from django import template

register = template.Library()

@register.filter
def split(value, delimiter=','):
    """
    Usage: {{ value|split:"," }}
    """
    if not isinstance(value, str) or not value.strip():
        return []
    return [v.strip() for v in value.split(delimiter) if v.strip()]

from django import template

register = template.Library()


@register.filter(name='getitem')
def getitem(value, key):
    if value is None:
        return ''
    try:
        if hasattr(value, 'get'):
            return value.get(key, '')
        return value[key]
    except (KeyError, IndexError, TypeError):
        return ''


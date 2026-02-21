from django import template

register = template.Library()


@register.simple_tag
def get_menu_label(event, label_setting):
    """
    Get the custom menu label from event settings.
    
    Usage in templates:
        {% get_menu_label event 'menu_label_tickets' %}
    
    Returns the custom label if set, otherwise an empty string.
    The template should use this with a fallback to the default translated string.
    
    Args:
        event: Event object
        label_setting: Setting key (e.g., 'menu_label_tickets')
    
    Returns:
        Custom label if set (possibly empty string to trigger fallback), or None
    """
    if not event or not event.settings:
        return ''
    
    custom_label = getattr(event.settings, label_setting, '')
    return custom_label if custom_label else None

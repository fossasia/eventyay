from django import template

register = template.Library()


@register.simple_tag
def get_menu_label(event, label_setting):
    """
    Get the custom menu label from event settings.
    
    Returns the custom label if set in event.settings, otherwise returns an empty string.
    Templates should use the default filter to provide a fallback default label.
    
    Usage in templates:
        {% get_menu_label event 'menu_label_tickets' as label %}
        {{ label|default:_('Tickets') }}
    
    Args:
        event: Event object with settings attribute
        label_setting: Setting key (e.g., 'menu_label_tickets')
    
    Returns:
        Custom label if set in event.settings, otherwise an empty string.
    """
    if not event or not getattr(event, 'settings', None):
        return ''
    
    custom_label = getattr(event.settings, label_setting, '')
    return custom_label or ''

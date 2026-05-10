from django import template

register = template.Library()


@register.simple_tag
def get_menu_label(event, label_setting):
    """
    Return a custom menu label from event settings if configured.
    """
    if not event or not getattr(event, 'settings', None):
        return ''

    custom_label = getattr(event.settings, label_setting, '')
    return custom_label or ''

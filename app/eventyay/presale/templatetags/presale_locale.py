from django import template
from eventyay.common.utils.language import localize_event_text

register = template.Library()


@register.filter(name='event_localize')
def event_localize(value):
    """Render organizer-provided text in the selected event language.

    Uses request-scoped event language set by middleware; falls back to UI
    language and then to default language.
    """
    return localize_event_text(value)

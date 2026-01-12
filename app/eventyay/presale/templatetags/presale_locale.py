from django import template
from django.conf import settings
from django.utils import translation
from i18nfield.strings import LazyI18nString

from eventyay.common.utils.language import get_current_event_language

register = template.Library()


@register.filter(name='event_localize', is_safe=True)
def event_localize(value):
    """Render organizer-provided text in the selected event language.

    Uses thread-local event language set by middleware; falls back to UI language
    and then to default language.
    """
    event_lang = get_current_event_language()
    ui_lang = translation.get_language() or settings.LANGUAGE_CODE

    if isinstance(value, LazyI18nString):
        if event_lang:
            localized = value.localize(event_lang)
            if localized:
                return localized
        return value.localize(ui_lang)

    return value

from django import template
from django.conf import settings
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext_lazy as _
from i18nfield.strings import LazyI18nString

from eventyay.talk_rules.agenda import is_wip_agenda_url

register = template.Library()

MENU_LABEL_DEFAULTS = {
    'menu_label_tickets': _('Tickets'),
    'menu_label_join_video': _('Join online video'),
}


@register.simple_tag
def get_menu_label(event, label_setting):
    """
    Return a custom menu label from event settings if configured.
    """
    if not event or not getattr(event, 'settings', None):
        return ''

    custom_label = getattr(event.settings, label_setting, '')
    return custom_label or ''


def _localize_menu_label(value):
    if value is None:
        return ''
    if not isinstance(value, LazyI18nString):
        return value

    locale = translation.get_language() or settings.LANGUAGE_CODE
    return _localize_without_default_fallback(value, locale)


def _localize_without_default_fallback(value, locale):
    if value.data is None:
        return ''

    if not isinstance(value.data, dict):
        with translation.override(locale):
            return str(value.data)

    candidates = [locale]
    firstpart = locale.split('-')[0]
    if firstpart != locale:
        candidates.append(firstpart)
    candidates.extend(
        loc
        for loc in value.data
        if (loc.startswith(firstpart + '-') or firstpart == loc) and loc not in candidates
    )

    for candidate in candidates:
        localized = value.data.get(candidate)
        if localized:
            return localized
    return ''


@register.simple_tag
def get_localized_menu_label(event, label_setting):
    """
    Return a localized custom menu label, or the translated default label.

    Menu labels are UI text. If an organizer only customizes English, a
    different UI language should fall back to the translated default, not
    English.
    """
    custom_label = _localize_menu_label(get_menu_label(event, label_setting))
    if custom_label:
        return custom_label
    return MENU_LABEL_DEFAULTS.get(label_setting, '')


@register.simple_tag
def is_wip_agenda_preview(request):
    return is_wip_agenda_url(getattr(request, 'path_info', ''))


def _agenda_event_url_kwargs(event):
    return {'organizer': event.organizer.slug, 'event': event.slug}


@register.simple_tag
def agenda_schedule_nav_url(request, event):
    """Return the schedule tab URL, preserving WIP preview when applicable."""
    if is_wip_agenda_url(getattr(request, 'path_info', '')):
        return reverse(
            'agenda:versioned-schedule',
            kwargs={**_agenda_event_url_kwargs(event), 'version': 'wip'},
        )
    return event.talk_schedule_url


@register.simple_tag
def agenda_speakers_nav_url(request, event):
    """Return the speakers tab URL, preserving WIP preview when applicable."""
    if is_wip_agenda_url(getattr(request, 'path_info', '')):
        return reverse(
            'agenda:versioned-wip-speakers',
            kwargs=_agenda_event_url_kwargs(event),
        )
    return event.talk_speaker_url

from contextlib import suppress
from contextvars import ContextVar

from django.conf import settings
from django.utils import translation
from django.utils.text import slugify
from django.utils.translation.trans_real import get_supported_language_variant
from i18nfield.strings import LazyI18nString


def get_event_language_cookie_name(event_slug: str, organizer_slug: str | None = None) -> str:
    """Return a stable, per-event cookie name for content language selection."""
    safe_event = slugify(event_slug or '') or 'event'
    safe_organizer = slugify(organizer_slug or '') or 'organizer'
    return f"{settings.LANGUAGE_COOKIE_NAME}_event_{safe_organizer}_{safe_event}"


def validate_language(value, supported):
    """Validate and normalize a language code against a supported list."""
    with suppress(LookupError):
        normalized = get_supported_language_variant(value)
        if normalized in supported:
            return normalized
    return None


_event_language = ContextVar('event_language', default=None)


def set_current_event_language(lang: str | None):
    """Store event language for the current request context."""
    _event_language.set(lang)


def get_current_event_language() -> str | None:
    """Return event language stored for the current request context."""
    return _event_language.get()


def localize_event_text(value):
    if value is None:
        return value
    event_lang = get_current_event_language()
    ui_lang = translation.get_language() or settings.LANGUAGE_CODE
    default_lang = settings.LANGUAGE_CODE
    if isinstance(value, LazyI18nString):
        if event_lang:
            localized = value.localize(event_lang)
            if localized:
                return localized
        if ui_lang:
            localized = value.localize(ui_lang)
            if localized:
                return localized
        return value.localize(default_lang)
    return value

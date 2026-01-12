from contextlib import suppress
from threading import local

from django.conf import settings
from django.utils.text import slugify
from django.utils.translation.trans_real import get_supported_language_variant


def get_event_language_cookie_name(event_slug: str) -> str:
    """Return a stable, per-event cookie name for content language selection."""
    safe_slug = slugify(event_slug or '') or 'event'
    return f"{settings.LANGUAGE_COOKIE_NAME}_event_{safe_slug}"


def validate_language(value, supported):
    """Validate and normalize a language code against a supported list."""
    with suppress(LookupError):
        normalized = get_supported_language_variant(value)
        if normalized in supported:
            return normalized
    return None


_thread_state = local()


def set_current_event_language(lang: str | None):
    """Store event language for the current thread/request."""
    _thread_state.event_language = lang


def get_current_event_language() -> str | None:
    """Return event language stored for the current thread/request."""
    return getattr(_thread_state, 'event_language', None)

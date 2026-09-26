from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def ensure_secret_key_is_private():
    """
    Refuse to serve production traffic with a SECRET_KEY that is published in this repository.

    Called from the WSGI and ASGI entry points (the processes that verify tokens from requests)
    rather than from settings, so that build-time management commands (collectstatic,
    compilemessages) keep working without secrets.
    """
    if settings.IS_PRODUCTION and settings.SECRET_KEY in settings.PUBLIC_SECRET_KEYS:
        raise ImproperlyConfigured(
            'SECRET_KEY is set to a public placeholder value. '
            'Set EVY_SECRET_KEY in .env or provide .secrets/EVY_SECRET_KEY.'
        )

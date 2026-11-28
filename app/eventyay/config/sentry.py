import logging


SENTRY_DATA_COLLECTION = {
    'user_info': False,
    'cookies': {'mode': 'off'},
    'http_headers': {
        'request': {
            'mode': 'denylist',
            'terms': [
                'authorization',
                'cookie',
                'x-csrftoken',
                'x-forwarded-for',
                'x-real-ip',
                'forwarded',
            ],
        }
    },
    'http_bodies': [],
    'database_query_data': False,
    'queues': False,
    'stack_frame_variables': False,
}


def initialize_sentry(
    dsn: str,
    debug: bool,
    release: str | None,
    environment: str,
) -> None:
    """Initialize Sentry SDK 3.x with Eventyay's integrations and privacy defaults."""
    import sentry_sdk
    from django.core.exceptions import PermissionDenied
    from django.http import Http404
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            CeleryIntegration(),
            DjangoIntegration(),
            LoggingIntegration(level=None, event_level=logging.ERROR),
        ],
        data_collection=SENTRY_DATA_COLLECTION,
        debug=debug,
        release=release,
        environment=environment,
        ignore_errors=[Http404, PermissionDenied],
    )

from contextlib import suppress

from django.apps import AppConfig


class AgendaConfig(AppConfig):
    name = 'eventyay.agenda'

    def ready(self):
        from .phrases import AgendaPhrases  # noqa
        from . import permissions  # noqa


with suppress(ImportError):
    from eventyay import celery_app as celery  # noqa

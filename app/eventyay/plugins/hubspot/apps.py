from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from eventyay import __version__ as version


class HubSpotApp(AppConfig):
    name = 'eventyay.plugins.hubspot'
    verbose_name = _('HubSpot CRM')

    class EventyayPluginMeta:
        name = _('HubSpot CRM')
        category = 'FEATURE'
        featured = False
        version = version
        description = _(
            'Sync attendees to HubSpot when orders are paid. '
            'Uses static field mapping (email, first name, last name). '
            'Does not support configurable mappings or connection metadata.'
        )

    def ready(self):
        # Import signals module to register signal handlers.
        # Django apps use ready() for initialization work like signal registration.
        # This is done lazily to avoid circular import issues during startup.
        from . import signals  # NOQA

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
        description = _('Sync attendees to HubSpot when orders are paid.')

    def ready(self):
        from . import signals  # NOQA


default_app_config = 'eventyay.plugins.hubspot.HubSpotApp'

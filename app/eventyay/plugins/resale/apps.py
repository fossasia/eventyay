from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from eventyay import __version__ as version


class ResaleApp(AppConfig):
    name = 'eventyay.plugins.resale'
    verbose_name = _('Ticket resale marketplace')

    class EventyayPluginMeta:
        name = _('Ticket resale marketplace')
        version = version
        category = 'FEATURE'
        featured = True
        description = _(
            'Allow attendees to list purchased tickets for resale and let others buy them '
            'through a public marketplace on the event shop.'
        )

    def ready(self):
        from . import settings as _settings  # noqa: F401
        from . import signals  # noqa: F401


default_app_config = 'eventyay.plugins.resale.ResaleApp'

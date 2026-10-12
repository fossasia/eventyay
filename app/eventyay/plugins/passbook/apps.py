from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from eventyay import __version__ as version


class PassbookApp(AppConfig):
    name = 'eventyay.plugins.passbook'
    verbose_name = _('Passbook / Apple Wallet tickets')

    class EventyayPluginMeta:
        name = _('Apple Wallet / Passbook')
        author = 'Eventyay'
        version = version
        category = 'FEATURE'
        description = _('Output tickets as Passbook (.pkpass) files for Apple Wallet and compatible apps.')

    def ready(self):
        from . import signals  # noqa: F401


default_app_config = 'eventyay.plugins.passbook.PassbookApp'

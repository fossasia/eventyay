from importlib import import_module

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PassbookApp(AppConfig):
    name = 'eventyay.plugins.passbook'
    verbose_name = _('Apple Wallet ticket output')

    def ready(self):
        import_module('eventyay.plugins.passbook.signals')

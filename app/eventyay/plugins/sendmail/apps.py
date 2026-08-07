from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from eventyay import __version__ as version


class SendMailApp(AppConfig):
    name = 'eventyay.plugins.sendmail'
    verbose_name = _('Send out emails')



    def ready(self):
        from . import signals  # NOQA
        from . import tasks  # NOQA


default_app_config = 'eventyay.plugins.sendmail.SendMailApp'

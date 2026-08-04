from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class StatisticsApp(AppConfig):
    name = 'eventyay.plugins.statistics'
    verbose_name = _('Statistics')

    def ready(self):
        from . import signals  # NOQA


default_app_config = 'eventyay.plugins.statistics.StatisticsApp'

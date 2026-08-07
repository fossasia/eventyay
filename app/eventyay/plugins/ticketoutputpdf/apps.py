from django.apps import AppConfig
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from eventyay import __version__ as version


class TicketOutputPdfApp(AppConfig):
    name = 'eventyay.plugins.ticketoutputpdf'
    verbose_name = _('PDF ticket output')


    def ready(self):
        from . import signals  # NOQA

    @cached_property
    def compatibility_errors(self):
        errs = []
        try:
            import reportlab  # NOQA
        except ImportError:
            errs.append("Python package 'reportlab' is not installed.")
        return errs


default_app_config = 'eventyay.plugins.ticketoutputpdf.TicketOutputPdfApp'

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from . import __version__


class PaypalPluginApp(AppConfig):
    default = True
    name = "eventyay_paypal"
    verbose_name = _("PayPal")

    class EventyayPluginMeta:
        name = _("PayPal")
        author = "eventyay"
        version = __version__
        category = "PAYMENT"
        featured = True
        visible = True
        description = _("This plugin allows you to receive payments via PayPal.")

    def ready(self):
        from . import signals  # NOQA


default_app_config = "eventyay-paypal.apps.PaypalPluginApp"

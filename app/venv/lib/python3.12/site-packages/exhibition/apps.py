from django.utils.translation import gettext_lazy as _

from . import __version__

try:
    from eventyay.base.plugins import PluginConfig
except ImportError:
    raise RuntimeError("Please use a later version of eventyay-tickets")


class ExhibitionApp(PluginConfig):
    default = True
    name = "exhibition"
    verbose_name = _("Exhibition")

    class EventyayPluginMeta:
        name = _("Exhibition")
        author = "FOSSASIA"
        description = _("This plugin enables to add and control exhibitors in eventyay")
        visible = True
        featured = True
        version = __version__
        category = "FEATURE"

    def ready(self):
        from . import signals  # NOQA

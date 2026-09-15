import shutil

from django.apps import AppConfig
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from eventyay import __version__ as version


class PassbookApp(AppConfig):
    name = 'eventyay.plugins.passbook'
    verbose_name = _('Passbook Tickets')

    class EventyayPluginMeta:
        name = _('Passbook Tickets')
        author = 'Eventyay'
        version = version
        category = 'FORMAT'
        visible = True
        featured = True
        description = _('Provides passbook tickets for eventyay')

    def ready(self):
        from . import signals  # NOQA

    @cached_property
    def compatibility_errors(self):
        errs = []
        if not shutil.which('openssl'):
            errs.append(_('The OpenSSL binary is not installed or not in the PATH.'))
        return errs

    @cached_property
    def compatibility_warnings(self):
        errs = []
        try:
            from PIL import Image  # NOQA
        except ImportError:
            errs.append(
                _('Pillow is not installed on this system, which is required for converting and scaling images.')
            )
        return errs


default_app_config = 'eventyay.plugins.passbook.PassbookApp'

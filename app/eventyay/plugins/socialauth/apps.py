from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from eventyay import __version__ as version


class SocialAuthApp(AppConfig):
    name = 'eventyay.plugins.socialauth'
    verbose_name = _('SocialAuth')

    class EventyayPluginMeta:
        name = _('SocialAuth')
        author = _('the eventyay team')
        version = version
        featured = True
        description = _('This plugin allows you to login via social networks')
        visible = False

    def ready(self):
        super().ready()
        from .openid_connect import patch_openid_connect

        patch_openid_connect()


default_app_config = 'eventyay.plugins.socialauth.SocialAuthApp'

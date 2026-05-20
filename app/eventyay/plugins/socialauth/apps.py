from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from eventyay import __version__ as version


class SocialAuthApp(AppConfig):
    name = 'eventyay.plugins.socialauth'
    verbose_name = _('SocialAuth')

    def ready(self):
        from allauth.socialaccount.models import SocialApp

        # Must match _MIGRATION_SOCIALAPP_SECRET_MAX_LENGTH in migrations/0001_…secrets.py
        socialapp_secret_max_length = 512
        secret_field = SocialApp._meta.get_field('secret')
        if secret_field.max_length < socialapp_secret_max_length:
            secret_field.max_length = socialapp_secret_max_length

    class EventyayPluginMeta:
        name = _('SocialAuth')
        author = _('the eventyay team')
        version = version
        featured = True
        description = _('This plugin allows you to login via social networks')
        visible = False


default_app_config = 'eventyay.plugins.socialauth.SocialAuthApp'

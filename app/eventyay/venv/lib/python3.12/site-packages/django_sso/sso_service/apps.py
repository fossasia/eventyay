import importlib

from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from django.core.exceptions import ImproperlyConfigured
from .backend import EventAcceptor


class ServiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'django_sso.sso_service'

    def ready(self):
        if not hasattr(settings, 'SSO'):
            raise ImproperlyConfigured(f'Django SSO: Client side requires SSO variable in settings.py')

        if not hasattr(settings, 'SSO') or not isinstance(settings.SSO, dict):
            raise ImproperlyConfigured(
                f'Django SSO: In settings.py SSO variable must be dict. (Now are "{type(settings.SSO).__name__}")'
            )

        if not hasattr(settings, 'LOGIN_URL'):
            raise ImproperlyConfigured('Django SSO: Requires LOGIN_URL setting')

        for variable in ('TOKEN', 'ROOT'):
            if variable not in settings.SSO:
                raise ImproperlyConfigured(f"SSO[{variable}] {_('settings variable not set')}")

        settings.SSO['ROOT'] = settings.SSO['ROOT'].rstrip('/')

        sso_event_acceptor_class = settings.SSO.get('EVENT_ACCEPTOR_CLASS', '').strip()

        if sso_event_acceptor_class:
            if type(sso_event_acceptor_class) != str:
                raise ImproperlyConfigured(f"SSO[EVENT_ACCEPTOR_CLASS] {_('must be string')}")

            try:
                [module_name, class_name] = sso_event_acceptor_class.rsplit('.', 1)
                module = importlib.import_module(module_name)
                class_ref = getattr(module, class_name, None)

                if not class_ref:
                    raise ImproperlyConfigured(_(
                        f'In SSO[EVENT_ACCEPTOR_CLASS] declared module has no class named {class_name}'
                    ))

                if not issubclass(class_ref, EventAcceptor):
                    raise ImproperlyConfigured(
                        f'{settings.SSO["EVENT_ACCEPTOR_CLASS"]} {_("is not inherits")} '
                        f'django_sso.sso_service.backend.EventAcceptor'
                    )
            except ImproperlyConfigured as e:
                raise e
            except Exception as e:
                raise ImproperlyConfigured(_(
                    'Can\'t import SSO event acceptor class from SSO[EVENT_ACCEPTOR_CLASS] variable'
                ))

        from . import signals

from django.apps import AppConfig


class EventyayBaseConfig(AppConfig):
    name = 'eventyay.base'
    label = 'base'

    def ready(self):
        from .operational_logging import OUTCOME_SUCCESS, connect_operational_signals, log_event

        connect_operational_signals()
        from . import exporter  # NOQA
        from . import payment  # NOQA
        from . import exporters  # NOQA
        from . import invoice  # NOQA
        from . import notifications  # NOQA
        from . import email  # NOQA
        from . import anonymizer  # NOQA

        try:
            from eventyay.celery_app import app as celery_app  # NOQA
        except ImportError:
            pass

        log_event('core', 'config.loaded', OUTCOME_SUCCESS)


default_app_config = 'eventyay.base.EventyayBaseConfig'
try:
    import eventyay.celery_app as celery  # NOQA
except ImportError:
    pass

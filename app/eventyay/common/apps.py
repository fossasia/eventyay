from contextlib import suppress

from django.apps import AppConfig

from .gzip_static import install_static_gzip


class CommonConfig(AppConfig):
    name = 'eventyay.common'

    def ready(self):
        from . import checks  # noqa
        from . import log_display  # noqa
        from . import signals  # noqa
        from . import tasks  # noqa
        install_static_gzip()
        # from . import update_check  # noqa


with suppress(ImportError):
    from eventyay import celery_app as celery  # NOQA

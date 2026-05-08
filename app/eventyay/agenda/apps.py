import logging
from contextlib import suppress

from django.apps import AppConfig

LOGGER = logging.getLogger(__name__)


class AgendaConfig(AppConfig):
    name = 'eventyay.agenda'

    def ready(self):
        from .phrases import AgendaPhrases  # noqa
        from eventyay.schedule.signals import schedule_release

        def on_schedule_release(sender, schedule, **kwargs):
            from django.core.cache import cache

            prev_schedule = (
                sender.schedules.filter(version__isnull=False)
                .exclude(pk=schedule.pk)
                .order_by('-published')
                .values('version')
                .first()
            )
            keys_to_delete = [f'eagenda:meta:{sender.pk}:{schedule.version}']
            if prev_schedule:
                keys_to_delete.append(f'eagenda:meta:{sender.pk}:{prev_schedule["version"]}')
                keys_to_delete.append(f'eagenda:exporters:{sender.pk}:{prev_schedule["version"]}')
            cache.delete_many(keys_to_delete)

            try:
                from eventyay.agenda.tasks import warm_schedule_caches
                warm_schedule_caches.apply_async(kwargs={'schedule_pk': schedule.pk}, countdown=3)
            except Exception:
                LOGGER.exception('Failed to enqueue warm_schedule_caches for schedule pk=%s', schedule.pk)

        schedule_release.connect(on_schedule_release, dispatch_uid='agenda.on_schedule_release')


with suppress(ImportError):
    from eventyay import celery_app as celery  # noqa

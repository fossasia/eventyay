import logging
from contextlib import suppress

from django.apps import AppConfig
from django.conf import settings

LOGGER = logging.getLogger(__name__)


class AgendaConfig(AppConfig):
    name = 'eventyay.agenda'

    def ready(self):
        from .phrases import AgendaPhrases  # noqa
        from . import etherpad  # noqa
        from eventyay.schedule.signals import schedule_release

        def on_schedule_release(sender, schedule, **kwargs):
            from django.core.cache import cache

            all_versions = list(
                sender.schedules.filter(version__isnull=False)
                .values_list('version', flat=True)
            )
            language_codes = [code for code, _name in settings.LANGUAGES]
            keys_to_delete = []
            for version in all_versions:
                keys_to_delete.extend(f'eagenda:meta:{sender.pk}:{version}:{code}' for code in language_codes)
                keys_to_delete.append(f'eagenda:meta:{sender.pk}:{version}')
            keys_to_delete.extend(f'eagenda:exporters:{sender.pk}:{schedule.version}:{code}' for code in language_codes)
            keys_to_delete.append(f'eagenda:exporters:{sender.pk}:{schedule.version}')
            cache.delete_many(keys_to_delete)

            try:
                from eventyay.agenda.tasks import warm_schedule_caches
                warm_schedule_caches.apply_async(kwargs={'schedule_pk': schedule.pk}, countdown=3)
            except Exception:
                LOGGER.exception('Failed to enqueue warm_schedule_caches for schedule pk=%s', schedule.pk)

        schedule_release.connect(on_schedule_release, dispatch_uid='agenda.on_schedule_release', weak=False)

        from eventyay.base.models import SubmissionStates
        from eventyay.submission.signals import submission_state_change

        def on_submission_state_change(sender, submission, **kwargs):
            if submission.state not in SubmissionStates.terminal_states:
                return
            from eventyay.agenda.views.utils import (
                clear_featured_speakers_without_active_submissions,
                clear_schedule_caches,
            )

            clear_featured_speakers_without_active_submissions(sender, submission.speakers.all())
            clear_schedule_caches(sender, submission=submission)

        submission_state_change.connect(
            on_submission_state_change,
            dispatch_uid='agenda.on_submission_state_change',
            weak=False,
        )


with suppress(ImportError):
    from eventyay import celery_app as celery  # noqa

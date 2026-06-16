import logging

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import activate
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Event
from eventyay.celery import app

LOGGER = logging.getLogger(__name__)


@app.task(name='pretalx.agenda.export_schedule_html')
def export_schedule_html(*, event_id: int, make_zip=True):
    from django.core.management import call_command

    with scopes_disabled():
        event = Event.objects.prefetch_related('submissions').filter(pk=event_id).first()
    if not event:
        LOGGER.error('Could not find Event ID %s for export.', event_id)
        return

    with scope(event=event):
        if not event.current_schedule:
            LOGGER.error('Event %s could not be exported: it has no schedule.', event.slug)
            return

    cmd = ['export_schedule_html', event.slug]
    if make_zip:
        cmd.append('--zip')
    call_command(*cmd)


@app.task(name='eventyay.agenda.warm_schedule_caches')
def warm_schedule_caches(*, schedule_pk: int):
    """Pre-build and cache schedule JSON payloads for the newly released schedule.

    Warms non-enriched, enriched, meta, exporters, and per-talk/speaker inline
    caches so the first real user request after a schedule publish hits warm data.

    Note: Schedule and agenda.views.utils are imported locally to break the
    circular import chain: base.models.schedule → agenda.tasks → base.models.
    """
    # Local imports required to break circular dependency:
    # base.models.schedule imports export_schedule_html from this module,
    # so module-level imports of Schedule or agenda.views.utils create a cycle.
    from eventyay.agenda.views.utils import (
        CACHE_TTL,
        _serialize_schedule_build_data,
        build_public_schedule_exporters,
        build_schedule_meta_json,
        warm_scoped_schedule_caches,
    )
    from eventyay.base.models import Schedule

    with scopes_disabled():
        schedule = (
            Schedule.objects.select_related('event', 'event__organizer')
            .filter(pk=schedule_pk, version__isnull=False)
            .first()
        )
    if not schedule:
        return

    with scope(event=schedule.event):
        for featured in (True, False):
            try:
                cache.set(
                    f'eagenda:schedule:{schedule.pk}:{int(featured)}',
                    _serialize_schedule_build_data(
                        schedule,
                        all_talks=False,
                        enrich=False,
                        include_featured_speaker_metadata=featured,
                    ),
                    CACHE_TTL,
                )
            except Exception:
                LOGGER.exception('Failed to warm non-enriched cache for schedule %s (featured=%s)', schedule.pk, featured)

            try:
                cache.set(
                    f'eagenda:enriched:{schedule.pk}:{int(featured)}',
                    _serialize_schedule_build_data(
                        schedule,
                        enrich=True,
                        include_featured_speaker_metadata=featured,
                    ),
                    CACHE_TTL,
                )
            except Exception:
                LOGGER.exception('Failed to warm enriched cache for schedule %s (featured=%s)', schedule.pk, featured)

            try:
                warm_scoped_schedule_caches(schedule, featured=featured)
            except Exception:
                LOGGER.exception('Failed to warm scoped caches for schedule %s (featured=%s)', schedule.pk, featured)

        for lang_code, _name in settings.LANGUAGES:
            try:
                activate(lang_code)
                cache.set(
                    f'eagenda:meta:{schedule.event.pk}:{schedule.version}:{lang_code}',
                    build_schedule_meta_json(schedule.event, schedule),
                    CACHE_TTL,
                )
            except Exception:
                LOGGER.exception(
                    'Failed to warm meta cache for schedule %s (language=%s)',
                    schedule.pk,
                    lang_code,
                )

        try:
            for lang_code, _name in settings.LANGUAGES:
                activate(lang_code)
                build_public_schedule_exporters(schedule.event, version=schedule.version)
        except Exception:
            LOGGER.exception('Failed to warm exporters cache for schedule %s', schedule.pk)

    LOGGER.info('Pre-warmed schedule caches for schedule pk=%s version=%s', schedule.pk, schedule.version)

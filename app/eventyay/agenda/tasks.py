import json
import logging

from django.core.cache import cache
from django_scopes import scope, scopes_disabled
from i18nfield.utils import I18nJSONEncoder

from eventyay.base.models import Event
from eventyay.celery_app import app

LOGGER = logging.getLogger(__name__)

_CACHE_TTL = 600


@app.task(name='pretalx.agenda.export_schedule_html')
def export_schedule_html(*, event_id: int, make_zip=True):
    from django.core.management import call_command

    with scopes_disabled():
        event = Event.objects.prefetch_related('submissions').filter(pk=event_id).first()
    if not event:
        LOGGER.error(f'Could not find Event ID {event_id} for export.')
        return

    with scope(event=event):
        if not event.current_schedule:
            LOGGER.error(f'Event {event.slug} could not be exported: it has no schedule.')
            return

    cmd = ['export_schedule_html', event.slug]
    if make_zip:
        cmd.append('--zip')
    call_command(*cmd)


@app.task(name='eventyay.agenda.warm_schedule_caches')
def warm_schedule_caches(*, schedule_pk: int):
    """Pre-build and cache schedule JSON payloads for the newly released schedule.

    Warms non-enriched, enriched, and exporters caches so the first real user
    request after a schedule publish hits a warm cache instead of paying the
    full build_data cost.

    Note: Schedule and agenda.views.utils are imported locally to break the
    circular import chain: base.models.schedule → agenda.tasks → base.models.
    """
    # Local imports required to break circular dependency:
    # base.models.schedule imports export_schedule_html from this module,
    # so module-level imports of Schedule or agenda.views.utils create a cycle.
    from eventyay.agenda.views.utils import build_public_schedule_exporters, escape_json_for_script
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
                non_enriched = escape_json_for_script(json.dumps(
                    schedule.build_data(all_talks=False, enrich=False, include_featured_speaker_metadata=featured),
                    cls=I18nJSONEncoder,
                ))
                cache.set(f'eagenda:schedule:{schedule.pk}:{int(featured)}', non_enriched, _CACHE_TTL)
            except Exception:
                LOGGER.exception('Failed to warm non-enriched cache for schedule %s (featured=%s)', schedule.pk, featured)

            try:
                enriched = escape_json_for_script(json.dumps(
                    schedule.build_data(all_talks=False, enrich=True, include_featured_speaker_metadata=featured),
                    cls=I18nJSONEncoder,
                ))
                cache.set(f'eagenda:enriched:{schedule.pk}:{int(featured)}', enriched, _CACHE_TTL)
            except Exception:
                LOGGER.exception('Failed to warm enriched cache for schedule %s (featured=%s)', schedule.pk, featured)

        try:
            build_public_schedule_exporters(schedule.event, version=schedule.version)
        except Exception:
            LOGGER.exception('Failed to warm exporters cache for schedule %s', schedule.pk)

    LOGGER.info('Pre-warmed schedule caches for schedule pk=%s version=%s', schedule.pk, schedule.version)

from __future__ import annotations

import logging
import random
import time
from functools import partial
from typing import TYPE_CHECKING, Iterable
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.test import RequestFactory
from django.utils import translation
from django_scopes import scope, scopes_disabled

from eventyay.base.cache_keys import star_flush_delay_seconds, video_html_stamp_key
from eventyay.base.models import Event
from eventyay.base.models.cfp import CfP
from eventyay.base.models.profile import SpeakerProfile
from eventyay.base.models.question import Answer, AnswerOption, TalkQuestion
from eventyay.base.models.resource import Resource
from eventyay.base.models.room import Room
from eventyay.base.models.slot import TalkSlot
from eventyay.base.models.stream_schedule import StreamSchedule
from eventyay.base.models.submission import Submission, SubmissionFavourite, SpeakerRole
from eventyay.base.models.track import Track
from eventyay.base.signals import periodic_task
from eventyay.base.services.tasks import TransactionAwareTask
from eventyay.celery_app import app
from eventyay.helpers.periodic import SKIPPED
from eventyay.talk_rules.submission import are_featured_submissions_visible

if TYPE_CHECKING:
    from eventyay.base.models.schedule import Schedule

logger = logging.getLogger(__name__)


def refresh_video_html_cache_stamp(event_id: int, schedule_version: str) -> None:
    """Bump the stamp used in anonymous ``/video/`` HTML cache keys for this event/version."""
    cache.set(video_html_stamp_key(event_id, schedule_version), time.time(), timeout=None)


def released_schedules_for_event(event_id: int) -> list[Schedule]:
    """Return released (versioned) schedules for an event, without requiring an active django_scopes scope."""
    from eventyay.base.models.schedule import Schedule  # local import: circular dependency

    with scopes_disabled():
        return list(
            Schedule.objects.filter(event_id=event_id, version__isnull=False).select_related(
                'event', 'event__organizer'
            )
        )


@app.task(
    name='eventyay.base.rebuild_schedule_json_cache',
    ignore_result=True,
    base=TransactionAwareTask,
)
def rebuild_schedule_json_cache(
    schedule_pk: int,
    *,
    all_talks: bool = False,
    enrich: bool = True,
    include_featured_speaker_metadata: bool | None = None,
    language: str | None = None,
) -> None:
    """Recompute ``build_data`` for one released schedule and write fresh + backup cache entries.

    Keyword arguments must match the ``build_data`` variant that missed the cache
    (same stamp dimensions), otherwise the background job would not fill the key
    the next browser request expects.
    """
    from django.utils import translation

    from eventyay.base.models.schedule import Schedule  # local import: circular dependency

    with scopes_disabled():
        schedule = (
            Schedule.objects.filter(pk=schedule_pk, version__isnull=False)
            .select_related('event__organizer')
            .first()
        )
    if not schedule:
        return

    meta = include_featured_speaker_metadata
    if meta is None:
        meta = are_featured_submissions_visible(AnonymousUser(), schedule.event)
    lang = language or getattr(settings, 'LANGUAGE_CODE', 'en')

    with translation.override(lang):
        with scope(event=schedule.event):
            schedule.build_data(
                all_talks=all_talks,
                enrich=enrich,
                include_featured_speaker_metadata=meta,
                _force_recompute=True,
            )
    logger.info('Rebuilt schedule JSON cache for schedule %s (event %s)', schedule_pk, schedule.event_id)


def invalidate_released_schedule_caches(schedules: Iterable[Schedule]) -> None:
    """Invalidate ``build_data`` cache entries, refresh video HTML stamps, and enqueue background rebuilds."""
    schedules = list(schedules)
    if not schedules:
        return
    events_by_id = {
        e.pk: e
        for e in Event.objects.filter(pk__in={s.event_id for s in schedules}).select_related('organizer')
    }
    include_featured_by_event_id = {
        event_id: are_featured_submissions_visible(AnonymousUser(), event)
        for event_id, event in events_by_id.items()
    }
    language = getattr(settings, 'LANGUAGE_CODE', 'en')

    def enqueue_rebuild(schedule_pk: int, include_featured_speaker_metadata: bool) -> None:
        rebuild_schedule_json_cache.apply_async(
            kwargs={
                'schedule_pk': schedule_pk,
                'all_talks': False,
                'enrich': True,
                'include_featured_speaker_metadata': include_featured_speaker_metadata,
                'language': language,
            },
            countdown=1,
        )

    for schedule in schedules:
        schedule.invalidate_build_data_cache()
        refresh_video_html_cache_stamp(schedule.event_id, schedule.version)
        if getattr(settings, 'HAS_CELERY', False):
            event = events_by_id.get(schedule.event_id)
            if event is None:
                logger.warning(
                    'Skipping cache rebuild enqueue: event %s missing for schedule %s',
                    schedule.event_id,
                    schedule.pk,
                )
                continue
            include_featured_speaker_metadata = include_featured_by_event_id[schedule.event_id]
            transaction.on_commit(
                partial(enqueue_rebuild, schedule.pk, include_featured_speaker_metadata)
            )


@receiver(post_save, sender=TalkSlot, dispatch_uid='schedule_cache_talkslot_save')
@receiver(post_delete, sender=TalkSlot, dispatch_uid='schedule_cache_talkslot_delete')
def invalidate_on_talkslot_change(sender, instance, **kwargs):
    with scopes_disabled():
        schedule = instance.schedule
    if schedule.version:
        invalidate_released_schedule_caches([schedule])


@receiver(post_save, sender=Submission, dispatch_uid='schedule_cache_submission_save')
def invalidate_on_submission_change(sender, instance, **kwargs):
    from eventyay.base.models.schedule import Schedule  # local import: circular dependency

    with scopes_disabled():
        schedules = list(
            Schedule.objects.filter(talks__submission=instance, version__isnull=False)
            .distinct()
            .select_related('event', 'event__organizer')
        )
    invalidate_released_schedule_caches(schedules)


@receiver(post_save, sender=SpeakerRole, dispatch_uid='schedule_cache_speakerrole_save')
@receiver(post_delete, sender=SpeakerRole, dispatch_uid='schedule_cache_speakerrole_delete')
def invalidate_on_speakerrole_change(sender, instance, **kwargs):
    from eventyay.base.models.schedule import Schedule  # local import: circular dependency

    with scopes_disabled():
        schedules = list(
            Schedule.objects.filter(talks__submission=instance.submission, version__isnull=False)
            .distinct()
            .select_related('event', 'event__organizer')
        )
    invalidate_released_schedule_caches(schedules)


@receiver(post_save, sender=Resource, dispatch_uid='schedule_cache_resource_save')
@receiver(post_delete, sender=Resource, dispatch_uid='schedule_cache_resource_delete')
def invalidate_on_resource_change(sender, instance, **kwargs):
    from eventyay.base.models.schedule import Schedule  # local import: circular dependency

    with scopes_disabled():
        schedules = list(
            Schedule.objects.filter(talks__submission=instance.submission, version__isnull=False)
            .distinct()
            .select_related('event', 'event__organizer')
        )
    invalidate_released_schedule_caches(schedules)


@receiver(post_save, sender=Answer, dispatch_uid='schedule_cache_answer_save')
@receiver(post_delete, sender=Answer, dispatch_uid='schedule_cache_answer_delete')
def invalidate_on_answer_change(sender, instance, **kwargs):
    if not instance.submission_id:
        return
    from eventyay.base.models.schedule import Schedule  # local import: circular dependency

    with scopes_disabled():
        schedules = list(
            Schedule.objects.filter(talks__submission_id=instance.submission_id, version__isnull=False)
            .distinct()
            .select_related('event', 'event__organizer')
        )
    invalidate_released_schedule_caches(schedules)


@receiver(post_save, sender=AnswerOption, dispatch_uid='schedule_cache_answeroption_save')
@receiver(post_delete, sender=AnswerOption, dispatch_uid='schedule_cache_answeroption_delete')
def invalidate_on_answeroption_change(sender, instance, **kwargs):
    invalidate_released_schedule_caches(released_schedules_for_event(instance.question.event_id))


@receiver(post_save, sender=TalkQuestion, dispatch_uid='schedule_cache_talkquestion_save')
def invalidate_on_talkquestion_change(sender, instance, **kwargs):
    invalidate_released_schedule_caches(released_schedules_for_event(instance.event_id))


@receiver(post_save, sender=SpeakerProfile, dispatch_uid='schedule_cache_speakerprofile_save')
def invalidate_on_speakerprofile_change(sender, instance, **kwargs):
    invalidate_released_schedule_caches(released_schedules_for_event(instance.event_id))


@receiver(post_save, sender=Room, dispatch_uid='schedule_cache_room_save')
def invalidate_on_room_change(sender, instance, **kwargs):
    invalidate_released_schedule_caches(released_schedules_for_event(instance.event_id))


@receiver(post_save, sender=Track, dispatch_uid='schedule_cache_track_save')
def invalidate_on_track_change(sender, instance, **kwargs):
    invalidate_released_schedule_caches(released_schedules_for_event(instance.event_id))


@receiver(post_save, sender=StreamSchedule, dispatch_uid='schedule_cache_streamschedule_save')
@receiver(post_delete, sender=StreamSchedule, dispatch_uid='schedule_cache_streamschedule_delete')
def invalidate_on_streamschedule_change(sender, instance, **kwargs):
    invalidate_released_schedule_caches(released_schedules_for_event(instance.room.event_id))


@receiver(post_save, sender='base.Event', dispatch_uid='schedule_cache_event_save')
def invalidate_on_event_change(sender, instance, **kwargs):
    invalidate_released_schedule_caches(released_schedules_for_event(instance.pk))


@receiver(post_save, sender=CfP, dispatch_uid='schedule_cache_cfp_save')
def invalidate_on_cfp_change(sender, instance, **kwargs):
    invalidate_released_schedule_caches(released_schedules_for_event(instance.event_id))


@receiver(post_save, sender='base.User', dispatch_uid='schedule_cache_user_save')
def invalidate_on_user_change(sender, instance, **kwargs):
    with scopes_disabled():
        event_ids = list(
            SpeakerProfile.objects.filter(user=instance)
            .values_list('event_id', flat=True)
            .distinct()
        )
    for event_id in event_ids:
        invalidate_released_schedule_caches(released_schedules_for_event(event_id))


@receiver(post_save, sender=SubmissionFavourite, dispatch_uid='schedule_cache_submissionfavourite_save')
@receiver(post_delete, sender=SubmissionFavourite, dispatch_uid='schedule_cache_submissionfavourite_delete')
def invalidate_on_submissionfavourite_change(sender, instance, **kwargs):
    with scopes_disabled():
        event_id = instance.submission.event_id
    throttle_key = f'schedule_fav_flush_throttle_{event_id}'
    if not cache.add(throttle_key, 1, timeout=star_flush_delay_seconds()):
        return
    invalidate_released_schedule_caches(released_schedules_for_event(event_id))


def warm_event_build_data_caches(*, max_events: int = 10) -> int:
    """Populate ``Schedule.build_data`` cache for released current schedules."""
    n = 0
    for event in Event.objects.select_related('organizer').order_by('-id').iterator(chunk_size=100):
        with scope(event=event):
            schedule = event.current_schedule
            if not schedule or not schedule.version:
                continue
            schedule.build_data(
                all_talks=False,
                enrich=True,
                include_featured_speaker_metadata=are_featured_submissions_visible(
                    AnonymousUser(), event
                ),
                _force_recompute=True,
            )
        n += 1
        if n >= max_events:
            break
    logger.info('Warm build_data cache for %s events', n)
    return n


def warm_video_spa_pages(*, max_events: int = 10) -> int:
    """Populate anonymous video SPA HTML cache using the configured SITE_URL host.

    The cache key is host+scheme aware; warming uses settings.SITE_URL so the
    warmed entries are served to real browsers hitting the primary domain.
    """
    from eventyay.multidomain.views import VideoSPAView

    site_url = getattr(settings, 'SITE_URL', '')
    parsed = urlparse(site_url)
    site_scheme = parsed.scheme or 'http'
    site_hostname = parsed.hostname or 'localhost'
    site_port = str(parsed.port) if parsed.port else ('443' if site_scheme == 'https' else '80')
    rf = RequestFactory(SERVER_NAME=site_hostname, SERVER_PORT=site_port)
    view = VideoSPAView.as_view()
    language = getattr(settings, 'LANGUAGE_CODE', 'en')

    n = 0
    for event in Event.objects.select_related('organizer').order_by('-id').iterator(chunk_size=100):
        with scope(event=event):
            schedule = event.current_schedule
            if not schedule or not schedule.version:
                continue
            path = '/%s/%s/video/' % (event.organizer.slug, event.slug)
            request = rf.get(path, secure=(site_scheme == 'https'))
            request.user = AnonymousUser()
            with translation.override(language):
                view(request, organizer=event.organizer.slug, event=event.slug)
        n += 1
        if n >= max_events:
            break
    logger.info('Warm video SPA HTML cache for %s events', n)
    return n


periodic_warm_public_caches_next_run_key = 'eventyay.periodic_warm_public_caches_next_ts'


@receiver(signal=periodic_task)
def periodic_warm_public_caches(sender, **kwargs) -> object | None:
    """Warm caches at most once per random 24–48 h window (no edits required).

    ``runperiodic`` may fire often; this receiver skips until the previous run
    scheduled a next timestamp.  Edits still invalidate immediately via signals.
    """
    now = time.time()
    raw = cache.get(periodic_warm_public_caches_next_run_key)
    if raw is not None:
        try:
            if now < float(raw):
                return SKIPPED
        except (TypeError, ValueError):
            pass
    warm_event_build_data_caches(max_events=20)
    warm_video_spa_pages(max_events=15)
    delay = random.randint(24 * 3600, 48 * 3600)
    cache.set(periodic_warm_public_caches_next_run_key, now + delay, timeout=delay + 600)
    return None

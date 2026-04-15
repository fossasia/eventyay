import logging

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.dispatch import receiver
from django.test import RequestFactory
from django_scopes import scope

from eventyay.base.models import Event
from eventyay.base.signals import periodic_task
from eventyay.common.signals import minimum_interval
from eventyay.talk_rules.submission import are_featured_submissions_visible

logger = logging.getLogger(__name__)


def warm_event_build_data_caches(*, max_events=150):
    """Populate ``Schedule.build_data`` cache for released current schedules."""
    n = 0
    for event in Event.objects.select_related('organizer').order_by('-id').iterator(chunk_size=100):
        schedule = event.current_schedule
        if not schedule or not schedule.version:
            continue
        with scope(event=event):
            schedule.build_data(
                all_talks=False,
                enrich=True,
                include_featured_speaker_metadata=are_featured_submissions_visible(
                    AnonymousUser(), event
                ),
            )
        n += 1
        if n >= max_events:
            break
    logger.info('Warm build_data cache for %s events', n)
    return n


def warm_video_spa_pages(*, max_events=50):
    """Populate anonymous video SPA HTML cache (same path as browser /video/)."""
    from eventyay.multidomain.views import VideoSPAView

    n = 0
    for event in Event.objects.select_related('organizer').order_by('-id').iterator(chunk_size=100):
        schedule = event.current_schedule
        if not schedule or not schedule.version:
            continue
        path = '/%s/%s/video/' % (event.organizer.slug, event.slug)
        rf = RequestFactory()
        request = rf.get(path)
        request.user = AnonymousUser()
        request.LANGUAGE_CODE = getattr(settings, 'LANGUAGE_CODE', 'en')
        SessionMiddleware(lambda _req: None).process_request(request)
        request.session.save()
        view = VideoSPAView.as_view()
        view(request, organizer=event.organizer.slug, event=event.slug)
        n += 1
        if n >= max_events:
            break
    logger.info('Warm video SPA HTML cache for %s events', n)
    return n


@receiver(signal=periodic_task)
@minimum_interval(minutes_after_success=50, minutes_after_error=5)
def periodic_warm_public_caches(sender, **kwargs):
    warm_event_build_data_caches(max_events=150)
    warm_video_spa_pages(max_events=40)

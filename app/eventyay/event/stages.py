import copy
import datetime as dt

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ObjectDoesNotExist
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes import scope

from eventyay.common.text.phrases import phrases
from eventyay.base.models import SubmissionStates


def _is_talks_public(event):
    if not getattr(event, 'is_public', True):
        return False
    return bool(
        getattr(event, 'talks_published', False)
        or getattr(event, 'private_testmode_talks_enabled', False)
    )


def _get_tz(event):
    tz = getattr(event, 'timezone', None) or 'UTC'
    try:
        return ZoneInfo(tz) if isinstance(tz, str) else tz
    except (ZoneInfoNotFoundError, ValueError):
        return dt.timezone.utc


def _get_event_start(event):
    date_from = getattr(event, 'date_from', None)
    if date_from:
        if isinstance(date_from, dt.datetime):
            return date_from
        elif isinstance(date_from, dt.date):
            return dt.datetime.combine(date_from, dt.time(0, 0, 0), tzinfo=_get_tz(event))
    return now()


def _get_event_end(event):
    date_to = getattr(event, 'date_to', None)
    if date_to:
        if isinstance(date_to, dt.datetime):
            if date_to.time() == dt.time(0, 0):
                return date_to.replace(hour=23, minute=59, second=59, microsecond=999999)
            return date_to
        elif isinstance(date_to, dt.date):
            return dt.datetime.combine(date_to, dt.time(23, 59, 59, 999999), tzinfo=_get_tz(event))
    return _get_event_start(event)


def _is_in_preparation(event):
    return not _is_talks_public(event) and now() <= _get_event_end(event)


def _is_cfp_open(event):
    return (
        _is_talks_public(event)
        and hasattr(event, 'cfp')
        and event.cfp.is_open
        and now() <= _get_event_end(event)
    )


def _is_in_review(event):
    return (
        not _is_cfp_open(event)
        and not _is_in_preparation(event)
        and event.submissions.filter(state=SubmissionStates.SUBMITTED).exists()
        and now() <= _get_event_start(event)
    )


def _is_in_scheduling_stage(event):
    return (
        not _is_running(event)
        and not _is_in_wrapup(event)
        and not _is_in_review(event)
        and not _is_cfp_open(event)
        and not _is_in_preparation(event)
    )


def _is_running(event):
    return _get_event_start(event) <= now() <= _get_event_end(event)


def _is_in_wrapup(event):
    return _get_event_end(event) < now()



def _is_event_configured(event):
    return bool(
        getattr(event, 'location', None)
        or getattr(event, 'email', None)
        or getattr(event, 'header_image', None)
        or getattr(event, 'logo', None)
        or (hasattr(event, 'settings') and event.settings.get('event_logo_image'))
        or getattr(event, 'landing_page_text', None)
        or getattr(event, 'primary_color', None)
    )


def _is_cfp_configured(event):
    if not hasattr(event, 'cfp') or not event.cfp:
        return False
    return bool(
        getattr(event.cfp, 'headline', None)
        or getattr(event.cfp, 'text', None)
        or getattr(event.cfp, 'deadline', None)
    )


def _build_stage_check_cache(event):
    with scope(event=event):
        has_submissions = event.submissions.exists()
        cache = {
            'has_submissions': has_submissions,
            'has_accepted_or_rejected': False,
            'has_feedback': False,
            'has_recordings': False,
        }
        if has_submissions:
            cache['has_accepted_or_rejected'] = event.submissions.filter(
                state__in=[SubmissionStates.ACCEPTED, SubmissionStates.REJECTED]
            ).exists()
            cache['has_feedback'] = event.submissions.filter(feedback__isnull=False).exists()
            cache['has_recordings'] = (
                event.submissions.filter(answers__question__variant='video').exclude(answers__answer='').exists()
                or event.submissions.filter(resources__link__isnull=False).exists()
            )

        cache['has_speakers'] = event.speakers.exists()
        cache['has_reviewers'] = event.reviewers.exists()
        cache['has_reviews'] = event.reviews.exists()
        try:
            current_schedule = event.current_schedule
        except ObjectDoesNotExist:
            current_schedule = None
        wip_schedule = event.wip_schedule
        cache['has_schedule'] = current_schedule is not None
        cache['has_first_schedule'] = current_schedule is not None or bool(
            wip_schedule and wip_schedule.talks.filter(start__isnull=False).exists()
        )
        cache['has_sent_mails'] = event.queued_mails.filter(sent__isnull=False).exists()
        return cache


STAGES = {
    'PREPARATION': {
        'name': _('Preparation'),
        'method': _is_in_preparation,
        'icon': 'paper-plane',
        'links': [
            {
                'title': _('Configure the event'),
                'url': ['orga_urls', 'settings'],
                'check': _is_event_configured,
                'permission': 'can_change_settings',
            },
            {
                'title': _('Write a CfP'),
                'url': ['cfp', 'urls', 'edit_text'],
                'check': _is_cfp_configured,
                'permission': 'can_change_settings',
            },
        ],
    },
    'CFP_OPEN': {
        'name': _('CfP is open'),
        'method': _is_cfp_open,
        'icon': 'bullhorn',
        'links': [
            {
                'title': _('Monitor proposals'),
                'url': ['orga_urls', 'submissions'],
                'check_key': 'has_submissions',
                'permission': 'can_view_submission_stats',
            },
            {
                'title': _('Submit sessions for your speakers'),
                'url': ['orga_urls', 'new_submission'],
                'check_key': 'has_submissions',
                'permission': 'can_update_submission',
            },
            {
                'title': _('Add new speaker'),
                'url': ['orga_urls', 'new_speaker'],
                'check_key': 'has_speakers',
                'permission': 'can_list_speaker',
            },
            {
                'title': _('Invite reviewers'),
                'url': ['organizer', 'orga_urls', 'teams'],
                'check_key': 'has_reviewers',
                'permission': 'can_view_teams',
            },
        ],
    },
    'REVIEW': {
        'name': _('Review'),
        'method': _is_in_review,
        'icon': 'eye',
        'links': [
            {
                'title': _('Let reviewers do their work'),
                'url': ['orga_urls', 'reviews'],
                'check_key': 'has_reviews',
                'permission': 'can_review',
            },
            {
                'title': _('Accept or reject proposals'),
                'url': ['orga_urls', 'submissions'],
                'check_key': 'has_accepted_or_rejected',
                'permission': 'can_update_submission',
            },
            {
                'title': _('Build your first schedule'),
                'url': ['orga_urls', 'schedule'],
                'check_key': 'has_first_schedule',
                'permission': 'can_edit_schedule',
            },
        ],
    },
    'SCHEDULE': {
        'name': phrases.schedule.schedule if phrases.schedule else _('Schedule'),
        'method': _is_in_scheduling_stage,
        'icon': 'calendar-o',
        'links': [
            {
                'title': _('Release schedules as needed'),
                'url': ['orga_urls', 'schedule'],
                'check_key': 'has_schedule',
                'permission': 'can_edit_schedule',
            },
            {
                'title': _('Inform your speakers about the infrastructure'),
                'url': ['orga_urls', 'compose_mails_sessions'],
                'check_key': 'has_sent_mails',
                'permission': 'can_send_mail',
            },
        ],
    },
    'EVENT': {
        'name': _('Event'),
        'method': _is_running,
        'icon': 'play',
        'links': [
            {
                'title': _('Provide a point of contact for the speakers'),
                'url': ['orga_urls', 'settings'],
                'check': lambda event: bool(getattr(event, 'email', None)),
                'permission': 'can_change_settings',
            },
        ],
    },
    'WRAPUP': {
        'name': _('Wrapup'),
        'method': _is_in_wrapup,
        'icon': 'pause',
        'links': [
            {
                'title': _('Monitor incoming feedback'),
                'url': ['orga_urls', 'feedback'],
                'check_key': 'has_feedback',
                'permission': 'can_view_submission_stats',
            },
            {
                'title': _('Embed session recordings if available'),
                'url': ['orga_urls', 'submissions'],
                'check_key': 'has_recordings',
                'permission': 'can_update_submission',
            },
        ],
    },
}
STAGE_ORDER = ['PREPARATION', 'CFP_OPEN', 'REVIEW', 'SCHEDULE', 'EVENT', 'WRAPUP']


def in_stage(event, stage):
    return STAGES[stage]['method'](event)


def build_event_url(event, url):
    result = event
    for part in url:
        result = getattr(result, part)
    return result


def get_stages(event):
    inactive_state = 'done'
    stages = copy.deepcopy(STAGES)
    check_cache = None

    for stage in STAGES:
        is_stage_active = inactive_state == 'done' and in_stage(event, stage)
        if is_stage_active:
            inactive_state = 'todo'
        stages[stage]['phase'] = 'current' if is_stage_active else inactive_state
        for link in stages[stage].get('links', []):
            if 'check_key' in link:
                if check_cache is None:
                    check_cache = _build_stage_check_cache(event)
                link['is_configured'] = bool(check_cache.get(link['check_key'], False))
            elif 'check' in link:
                link['is_configured'] = bool(link['check'](event))
            else:
                link['is_configured'] = None
            if 'url' in link and link['url']:
                link['url'] = build_event_url(event, link['url'])
    return stages


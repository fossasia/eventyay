import copy

from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes import scope

from eventyay.base.models import SubmissionStates
from eventyay.common.text.phrases import phrases


def _is_in_preparation(event):
    """Keep non-public Talks in preparation until the event starts."""
    return not event.user_can_view_talks() and now() < event.date_from


def _is_cfp_open(event):
    """Show an open CfP only while public Talks accept proposals before the event."""
    return event.user_can_view_talks() and now() < event.date_from and event.cfp.is_open


def _is_in_review(event):
    """Review submitted proposals after preparation and the public CfP phase."""
    return (
        now() < event.date_from
        and not _is_in_preparation(event)
        and not _is_cfp_open(event)
        and event.submissions.filter(state=SubmissionStates.SUBMITTED).exists()
    )


def _is_in_scheduling_stage(event):
    """Schedule sessions once preparation, the CfP and proposal review are over."""
    return (
        now() < event.date_from
        and not _is_in_preparation(event)
        and not _is_cfp_open(event)
        and not _is_in_review(event)
    )


def _is_running(event):
    """Treat the start as inclusive and the end as the start of wrapup."""
    return event.date_from <= now() < event.date_to


def _is_in_wrapup(event):
    """Enter wrapup when the event has ended, regardless of its CfP deadline."""
    return event.date_to <= now()


STAGES = {
    'PREPARATION': {
        'name': _('Preparation'),
        'method': _is_in_preparation,
        'icon': 'paper-plane',
        'links': [
            {'title': _('Configure the event'), 'url': ['orga_urls', 'settings']},
            {'title': _('Gather your team'), 'url': ['organizer', 'orga_urls', 'base']},
            {'title': _('Write a CfP'), 'url': ['cfp', 'urls', 'edit_text']},
            {
                'title': _('Customize mail templates'),
                'url': ['orga_urls', 'mail_templates'],
            },
        ],
    },
    'CFP_OPEN': {
        'name': _('CfP'),
        'method': _is_cfp_open,
        'icon': 'bullhorn',
        'links': [
            {'title': _('Monitor proposals'), 'url': ['orga_urls', 'submissions']},
            {
                'title': _('Submit sessions for your speakers'),
                'url': ['orga_urls', 'new_submission'],
            },
            {'title': _('Invite reviewers'), 'url': ['organizer', 'orga_urls', 'base']},
        ],
    },
    'REVIEW': {
        'name': _('Review'),
        'method': _is_in_review,
        'icon': 'eye',
        'links': [
            {'title': _('Let reviewers do their work')},
            {
                'title': _('Accept or reject proposals'),
                'url': ['orga_urls', 'submissions'],
            },
            {'title': _('Build your first schedule'), 'url': ['orga_urls', 'schedule']},
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
            },
            {
                'title': _('Inform your speakers about the infrastructure'),
                'url': ['orga_urls', 'compose_mails_sessions'],
            },
        ],
    },
    'EVENT': {
        'name': _('Event'),
        'method': _is_running,
        'icon': 'play',
        'links': [
            {'title': _('Provide a point of contact for the speakers')},
            {'title': _('Enjoy the event!')},
        ],
    },
    'WRAPUP': {
        'name': _('Wrapup'),
        'method': _is_in_wrapup,
        'icon': 'pause',
        'links': [
            {'title': _('Monitor incoming feedback')},
            {'title': _('Embed session recordings if available')},
            {'title': _('Release next event date?')},
        ],
    },
}
STAGE_ORDER = ['PREPARATION', 'CFP_OPEN', 'REVIEW', 'SCHEDULE', 'EVENT', 'WRAPUP']


def in_stage(event, stage):
    """Evaluate a lifecycle phase within the event's data scope."""
    with scope(event=event):
        return STAGES[stage]['method'](event)


def build_event_url(event, url):
    """Resolve a phase action's attribute path against the event."""
    result = event
    for part in url:
        result = getattr(result, part)
    return result


def get_stages(event):
    """Mark the active lifecycle phase and the phases before and after it."""
    inactive_state = 'done'
    stages = copy.deepcopy(STAGES)

    for stage in STAGES:
        is_stage_active = inactive_state == 'done' and in_stage(event, stage)
        if is_stage_active:
            inactive_state = 'todo'
        stages[stage]['phase'] = 'current' if is_stage_active else inactive_state
        if stage == 'CFP_OPEN' and is_stage_active:
            stages[stage]['name'] = _('CfP is open')
        for link in stages[stage].get('links', []):
            if 'url' in link and link['url']:
                link['url'] = build_event_url(event, link['url'])
    return stages

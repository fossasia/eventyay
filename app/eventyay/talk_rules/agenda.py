import rules
from django.http import Http404

from .orga import can_view_speaker_names
from .person import is_reviewer
from .submission import (
    are_featured_submissions_visible,
    is_speaker,
    orga_can_change_submissions,
)


def is_submission_visible_via_featured(user, submission):
    return bool(submission and submission.is_featured and are_featured_submissions_visible(user, submission.event))


def is_submission_visible_via_schedule(user, submission):
    return bool(
        submission
        and is_agenda_visible(user, submission.event)
        and submission.slots.filter(schedule=submission.event.current_schedule, is_visible=True).exists()
    )


@rules.predicate
def can_view_wip_schedule(user, obj):
    """Organisers and reviewers with schedule access; never anonymous public visitors."""
    event = getattr(obj, 'event', None)
    if event is None and hasattr(obj, 'schedule'):
        event = obj.schedule.event
    if event is None and hasattr(obj, 'submission'):
        event = getattr(getattr(obj, 'submission', None), 'event', None)
    if not event or not user or user.is_anonymous:
        return False
    if orga_can_change_submissions(user, event):
        return True
    return bool(is_reviewer(user, event) and can_view_speaker_names(user, event))


WIP_AGENDA_URL_PATH = '/schedule/v/wip/'


def is_wip_agenda_url(path):
    return WIP_AGENDA_URL_PATH in (path or '')


def require_wip_schedule_access(request):
    if not can_view_wip_schedule(request.user, request.event):
        raise Http404()


def agenda_schedule_for_user(event, user, *, wip_preview=False):
    """Return the schedule backing an agenda page."""
    if wip_preview:
        return event.wip_schedule
    return event.current_schedule or event.wip_schedule


def filter_agenda_slots(qs, user, event, *, wip_preview=False):
    """Apply public ``is_visible`` filtering unless this is a WIP preview page."""
    if wip_preview:
        return qs
    return qs.filter(is_visible=True)


def wip_preview_build_data(user, event, schedule):
    """Whether ``build_data`` should bypass release visibility for this schedule."""
    return bool(schedule and not schedule.version and can_view_wip_schedule(user, event))


def can_access_schedule_widget(user, event):
    return user.has_perm('base.view_widget_schedule', event) or can_view_wip_schedule(user, event)


def agenda_speaker_talks(event, user, *, speaker=None, speaker_code=None, wip_preview=False):
    schedule = agenda_schedule_for_user(event, user, wip_preview=wip_preview)
    if not schedule:
        from eventyay.base.models import TalkSlot

        return TalkSlot.objects.none()
    qs = schedule.talks.all()
    if speaker is not None:
        qs = qs.filter(submission__speakers=speaker)
    elif speaker_code is not None:
        qs = qs.filter(submission__speakers__code=speaker_code)
    return filter_agenda_slots(qs, user, event, wip_preview=wip_preview)


@rules.predicate
def is_agenda_visible(user, event):
    event = event.event
    return bool(event and event.talks_published and event.get_feature_flag('show_schedule') and event.current_schedule)


can_view_schedule = is_agenda_visible | orga_can_change_submissions | (is_reviewer & can_view_speaker_names)


@rules.predicate
def is_agenda_submission_visible(user, submission):
    submission = getattr(submission, 'submission', submission)
    if not submission:
        return False
    return (
        is_submission_visible_via_schedule(user, submission)
        or is_submission_visible_via_featured(user, submission)
    )


@rules.predicate
def is_viewable_profile(user, profile):
    return is_speaker(profile.user, profile.event)


is_speaker_viewable = is_viewable_profile & can_view_schedule


@rules.predicate
def is_widget_always_visible(user, event):
    return event.get_feature_flag('show_widget_if_not_public')


is_widget_visible = is_agenda_visible | is_widget_always_visible


@rules.predicate
def event_uses_feedback(user, event):
    event = getattr(event, 'event', event)
    return event and event.get_feature_flag('use_feedback')

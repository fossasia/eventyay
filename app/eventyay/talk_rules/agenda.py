import rules
from django.http import Http404

from .orga import can_view_speaker_names
from .person import is_reviewer
from .submission import (
    are_featured_speakers_visible,
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
    return bool(
        event
        and event.talks_published
        and event.get_feature_flag('show_schedule')
        and event.current_schedule
        and not event.private_testmode_talks_enabled
    )


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


@rules.predicate
def is_pre_agenda_featured_public(user, event):
    """Featured speaker content is public before the full agenda is released."""
    event_obj = getattr(event, 'event', event)
    return bool(
        event_obj
        and are_featured_speakers_visible(user, event_obj)
        and not is_agenda_visible(user, event_obj)
    )


def speaker_has_released_schedule_slots(event, user):
    """True if the user has any talk slot on the published schedule."""
    schedule = getattr(event, 'current_schedule', None)
    if not schedule or not user:
        return False
    from django_scopes import scope

    from eventyay.base.models import TalkSlot

    with scope(event=event):
        return TalkSlot.objects.filter(
            schedule=schedule,
            submission__isnull=False,
            submission__speakers=user,
        ).exists()


@rules.predicate
def is_featured_speaker_profile(user, profile):
    if not profile or not profile.is_featured:
        return False
    event_obj = profile.event
    if not are_featured_speakers_visible(user, event_obj):
        return False
    # Speakers on the released schedule follow normal schedule visibility instead.
    if is_agenda_visible(user, event_obj) and speaker_has_released_schedule_slots(event_obj, profile.user):
        return False
    return True


@rules.predicate
def speaker_has_public_featured_submissions(user, profile):
    """Speaker profiles stay public before schedule release when they have featured talks."""
    if not profile or not profile.user_id:
        return False
    return bool(pending_public_submission_codes_for_speaker(profile.event, user, profile.user.code))


is_speaker_viewable = (
    (is_viewable_profile & can_view_schedule)
    | is_featured_speaker_profile
    | speaker_has_public_featured_submissions
)


@rules.predicate
def has_public_featured_speakers(user, event):
    event = getattr(event, 'event', event)
    if not event or not are_featured_speakers_visible(user, event):
        return False
    from eventyay.base.models import SpeakerProfile

    return SpeakerProfile.objects.filter(event=event, is_featured=True).exists()


def can_view_public_schedule_sessions(user, event, schedule=None):
    """Whether real schedule times may be shown on public featured/speaker pages."""
    event_obj = getattr(event, 'event', event)
    if schedule is None:
        schedule = getattr(event_obj, 'current_schedule', None) or getattr(event_obj, 'wip_schedule', None)
    if not schedule:
        return False
    return can_list_released_schedule_speakers(user, event_obj)


def can_list_released_schedule_speakers(user, event):
    """Whether the public speakers overview is available.

    Same gate for every visitor (including organisers): the schedule must be
    publicly released (``talks_published``, ``show_schedule``, a released version)
    and talk pages must not be limited to private test mode.
    """
    event_obj = getattr(event, 'event', event)
    if not event_obj or not event_obj.current_schedule:
        return False
    if not event_obj.get_feature_flag('show_schedule'):
        return False
    return is_agenda_visible(user, event_obj)


def _speaker_profile_by_code(event, speaker_code, *, select_related=()):
    from eventyay.base.models import SpeakerProfile

    queryset = SpeakerProfile.objects.filter(event=event, user__code__iexact=speaker_code)
    if select_related:
        queryset = queryset.select_related(*select_related)
    return queryset.first()


def public_speakers_list_available(user, event):
    """Whether the public speakers overview page and its nav links may be shown."""
    event_obj = getattr(event, 'event', event)
    if not can_list_released_schedule_speakers(user, event_obj):
        return False
    return event_obj.speakers.exists()


def agenda_speakers_page_reachable(user, event):
    """Whether the speakers list view may run and show schedule-style redirects."""
    event_obj = getattr(event, 'event', event)
    if not event_obj or not event_obj.get_feature_flag('show_schedule'):
        return False
    if can_list_released_schedule_speakers(user, event):
        return True
    if has_public_featured_speakers(user, event):
        return True
    if event_obj.current_schedule and event_obj.speakers.exists():
        return True
    return False


def should_hide_public_speaker_sessions(user, event, *, wip_preview=False):
    if wip_preview:
        return False
    return not is_agenda_visible(user, event)


def pending_public_submission_codes_for_speaker(event, user, speaker_code):
    """Submission codes that may appear as coming-soon for this speaker on public pages."""
    from django_scopes import scope

    from eventyay.base.models import SubmissionStates

    profile = _speaker_profile_by_code(event, speaker_code, select_related=('user', 'event'))
    if not profile:
        return set()

    featured_speaker = profile.is_featured and are_featured_speakers_visible(user, event)
    codes = set()
    with scope(event=event):
        submissions = (
            event.submissions.filter(speakers__code__iexact=speaker_code)
            .exclude(
                state__in=(
                    SubmissionStates.REJECTED,
                    SubmissionStates.CANCELED,
                    SubmissionStates.WITHDRAWN,
                    SubmissionStates.DELETED,
                )
            )
            .select_related('event')
        )
        for submission in submissions:
            if featured_speaker or is_submission_visible_via_featured(user, submission):
                codes.add(submission.code)
    return codes


def speaker_may_show_pending_sessions(user, event, speaker_code):
    profile = _speaker_profile_by_code(event, speaker_code)
    if not profile:
        return False
    if profile.is_featured and are_featured_speakers_visible(user, event):
        return True
    return bool(pending_public_submission_codes_for_speaker(event, user, speaker_code))


AGENDA_PAGES_WITHOUT_TALKS_PUBLISHED = frozenset(
    {
        'featured',
        'speakers',
        'speaker',
        'talk.detail',
        'widget.messages',
    }
)


def agenda_page_allowed_without_talks_published(url_name, user, event, *, url_kwargs=None):
    if url_name not in AGENDA_PAGES_WITHOUT_TALKS_PUBLISHED:
        return False
    if user is None:
        return False
    if url_name == 'speakers':
        return agenda_speakers_page_reachable(user, event)
    if url_name == 'talk.detail':
        slug = (url_kwargs or {}).get('slug')
        if not slug:
            return False
        submission = event.submissions.filter(code__iexact=slug).first()
        return is_submission_visible_via_featured(user, submission)
    if url_name in ('speaker', 'widget.messages'):
        if url_name == 'speaker':
            code = (url_kwargs or {}).get('code')
            if not code:
                return False
            profile = _speaker_profile_by_code(event, code)
            return bool(profile and is_speaker_viewable(user, profile))
        return (
            has_public_featured_speakers(user, event)
            or can_list_released_schedule_speakers(user, event)
        )
    return are_featured_submissions_visible(user, event)


@rules.predicate
def is_widget_always_visible(user, event):
    return event.get_feature_flag('show_widget_if_not_public')


is_widget_visible = is_agenda_visible | is_widget_always_visible


@rules.predicate
def event_uses_feedback(user, event):
    event = getattr(event, 'event', event)
    return event and event.get_feature_flag('use_feedback')

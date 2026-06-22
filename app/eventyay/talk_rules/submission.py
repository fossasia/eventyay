import rules
from django.db.models import Count, Exists, OuterRef, Q, Subquery

from .person import is_only_reviewer, is_reviewer


@rules.predicate
def reviewer_can_create_tags(user, obj):
    event = obj.event
    return bool(event.active_review_phase and event.active_review_phase.can_tag_submissions == 'create_tags')


@rules.predicate
def reviewer_can_change_submissions(user, obj):
    return bool(obj.event.active_review_phase and obj.event.active_review_phase.can_change_submission_state)


@rules.predicate
def reviewer_can_change_tags(user, obj):
    event = obj.event
    return bool(event.active_review_phase and event.active_review_phase.can_tag_submissions == 'use_tags')


@rules.predicate
def orga_can_change_submissions(user, obj):
    event = getattr(obj, 'event', None)
    if not user or user.is_anonymous or not obj or not event:
        return False
    if user.is_administrator:
        return True
    return 'can_change_submissions' in user.get_permissions_for_event(event)


orga_can_view_submissions = orga_can_change_submissions | is_reviewer
orga_or_reviewer_can_change_submission = orga_can_change_submissions | (is_reviewer & reviewer_can_change_submissions)


@rules.predicate
def is_cfp_open(user, obj):
    event = getattr(obj, 'event', None)
    return event and event.talks_published and event.cfp.is_open


def _show_featured_setting(event):
    """Normalized value for org setting ``show_featured`` (stored: never / after_schedule / always).

    ``after_schedule`` means: featured is shown only *after* the first **published** schedule
    version exists (``Schedule.published`` set on a versioned release).
    """
    from eventyay.base.models.event import default_feature_flags

    defaults = default_feature_flags()
    flags = event.feature_flags
    if not isinstance(flags, dict):
        flags = {}
    if 'show_featured' in flags and flags['show_featured'] is not None:
        raw = flags['show_featured']
    else:
        raw = defaults.get('show_featured', 'never')
    if isinstance(raw, bool):
        return 'always' if raw else 'never'
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        if normalized in ('never', 'after_schedule', 'always'):
            return normalized
        # Migrate legacy value saved before rename.
        if normalized == 'pre_schedule':
            return 'after_schedule'
    return defaults.get('show_featured', 'never')


def show_featured_always(event):
    """Whether org setting shows the featured page even before a schedule exists."""
    return _show_featured_setting(event) == 'always'


def featured_submissions_for_event(event):
    """Public featured submissions that may appear before a schedule is released."""
    from eventyay.base.models import SubmissionStates

    return (
        event.submissions.filter(is_featured=True)
        .exclude(
            state__in=(
                SubmissionStates.REJECTED,
                SubmissionStates.CANCELED,
                SubmissionStates.WITHDRAWN,
                SubmissionStates.DELETED,
            )
        )
        .select_related('event', 'event__organizer', 'submission_type')
        .prefetch_related('speakers')
        .order_by('title')
    )


def event_has_featured_submissions(event):
    return featured_submissions_for_event(event).exists()


def _event_has_published_schedule(event):
    """True once at least one schedule version has been published (``published`` is set)."""
    return event.current_schedule is not None


are_featured_exports_available = _event_has_published_schedule


def schedule_widget_featured_cache_key_part(event):
    """Vary schedule widget JSON cache when featured rules or release state change."""
    return f'{_show_featured_setting(event)}|rel={int(_event_has_published_schedule(event))}'


@rules.predicate
def are_featured_submissions_visible(user, event):
    """Whether org "show featured sessions" and schedule state allow public featured content.

    This predicate does **not** grant orga-only access; use ``list_featured`` (which ORs
    ``orga_can_change_submissions``) for API/orga rules. Public pages and nav must use this
    predicate so "Never" is respected for organizers viewing the public site.

    For ``after_schedule``, the featured page is available once a schedule version is
    published (and talks are published), or earlier when featured submissions exist as a
    preview before the schedule is released.
    """
    show_featured = _show_featured_setting(event)
    if show_featured == 'never':
        return False
    # "Always" shows regardless of schedule state or talks_published.
    if show_featured == 'always':
        return True
    if _event_has_published_schedule(event):
        return event.talks_published
    return event_has_featured_submissions(event)


def can_use_featured_exports(user, event):
    """Whether public featured export URLs are allowed for this user and event."""
    return are_featured_submissions_visible(user, event) and are_featured_exports_available(event)


@rules.predicate
def use_tracks(user, obj):
    event = obj.event
    return event.get_feature_flag('use_tracks')


@rules.predicate
def is_speaker(user, obj):
    obj = getattr(obj, 'submission', obj)
    return obj and user in obj.speakers.all()


@rules.predicate
def can_be_withdrawn(user, obj):
    from eventyay.base.models import SubmissionStates

    return obj and SubmissionStates.WITHDRAWN in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_rejected(user, obj):
    from eventyay.base.models import SubmissionStates

    return obj and SubmissionStates.REJECTED in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_accepted(user, obj):
    from eventyay.base.models import SubmissionStates

    return obj and SubmissionStates.ACCEPTED in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_confirmed(user, obj):
    from eventyay.base.models import SubmissionStates

    return obj and SubmissionStates.CONFIRMED in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_canceled(user, obj):
    from eventyay.base.models import SubmissionStates

    return obj and SubmissionStates.CANCELED in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_removed(user, obj):
    from eventyay.base.models import SubmissionStates

    return obj and SubmissionStates.DELETED in SubmissionStates.valid_next_states.get(obj.state, [])


@rules.predicate
def can_be_edited(user, obj):
    return obj and obj.editable


@rules.predicate
def can_request_speakers(user, submission):
    from eventyay.base.models import SubmissionStates

    return submission.state != SubmissionStates.DRAFT and submission.event.cfp.request_additional_speaker


@rules.predicate
def reviews_are_open(user, obj):
    event = obj.event
    return bool(event.active_review_phase and event.active_review_phase.can_review)


@rules.predicate
def can_view_all_reviews(user, obj):
    event = obj.event
    return bool(event.active_review_phase and event.active_review_phase.can_see_other_reviews == 'always')


@rules.predicate
def can_view_reviewer_names(user, obj):
    event = obj.event
    return bool(event.active_review_phase and event.active_review_phase.can_see_reviewer_names)


@rules.predicate
def can_view_reviews(user, obj):
    if can_view_all_reviews(user, obj):
        return True
    phase = obj.event.active_review_phase
    return bool(phase and phase.can_see_other_reviews == 'after_review' and obj.reviews.filter(user=user).exists())


@rules.predicate
def can_be_reviewed(user, obj):
    from eventyay.base.models import SubmissionStates

    if not obj:
        return False
    obj = getattr(obj, 'submission', obj)
    phase = obj.event.active_review_phase and obj.event.active_review_phase.can_review
    state = obj.state == SubmissionStates.SUBMITTED
    return bool(state and phase)


@rules.predicate
def has_reviewer_access(user, obj):
    obj = getattr(obj, 'submission', obj)
    if not obj or not obj.event or not obj.event.active_review_phase:
        return False
    if obj.event.active_review_phase.proposal_visibility == 'all':
        return obj.event.teams.filter(
            Q(limit_tracks__isnull=True) | Q(limit_tracks__in=[obj.track]),
            members__in=[user],
            is_reviewer=True,
        ).exists()
    return user in obj.assigned_reviewers.all()


def questions_for_user(request, event, user):
    """Used to retrieve synced querysets in the orga list and the API list."""
    from django.db.models import Q

    from eventyay.base.models import TalkQuestionTarget
    from eventyay.common.permissions import is_admin_mode_active
    from eventyay.talk_rules.orga import can_view_speaker_names

    if user.has_perm('base.update_talkquestion', event) or is_admin_mode_active(request):
        # Organizers with edit permissions can see everything
        return event.talkquestions(manager='all_objects').filter(is_imported=False)
    if not user.is_anonymous and is_only_reviewer(user, event) and can_view_speaker_names(user, event):
        return event.talkquestions(manager='all_objects').filter(
            Q(is_visible_to_reviewers=True) | Q(target=TalkQuestionTarget.REVIEWER),
            active=True,
            is_imported=False,
        )
    if user.has_perm('base.orga_list_talkquestion', event):
        # Other team members can either view all active talkquestions
        # or only talkquestions open to reviewers
        return event.talkquestions(manager='all_objects').filter(is_imported=False)

    # Now we are left with anonymous users or users with very limited permissions.
    # They can see all public (non-reviewer) talkquestions if they are already publicly
    # visible in the schedule. Otherwise, nothing.
    if user.has_perm('base.list_talkquestion', event):
        return event.talkquestions.all().filter(is_public=True, is_imported=False)
    return event.talkquestions.none()


def annotate_assigned(queryset, event, user):
    assigned = user.assigned_reviews.filter(event=event, pk=OuterRef('pk'))
    return queryset.annotate(is_assigned=Exists(Subquery(assigned)))


def get_reviewer_tracks(event, user):
    teams = event.teams.filter(members__in=[user], limit_tracks__isnull=False).prefetch_related(
        'limit_tracks', 'limit_tracks__event'
    )
    tracks = set()
    for team in teams:
        tracks.update(team.limit_tracks.filter(event=event))
    return tracks


def limit_for_reviewers(queryset, event, user, reviewer_tracks=None, add_assignments=False):
    if not (phase := event.active_review_phase):
        queryset = event.submissions.none()
    queryset = queryset.exclude(speakers__in=[user])
    if phase and phase.proposal_visibility == 'assigned':
        queryset = annotate_assigned(queryset, event, user)
        return queryset.filter(is_assigned__gte=1)
    if add_assignments:
        queryset = annotate_assigned(queryset, event, user)
    if reviewer_tracks is None:
        reviewer_tracks = get_reviewer_tracks(event, user)
    if reviewer_tracks:
        return queryset.filter(track__in=reviewer_tracks)
    return queryset


def submissions_for_user(event, user):
    from eventyay.base.models import Submission
    from eventyay.talk_rules.agenda import can_view_wip_schedule

    if not user.is_anonymous:
        if is_only_reviewer(user, event):
            return limit_for_reviewers(event.submissions.all(), event, user)
        if user.has_perm('base.orga_list_submission', event):
            return event.submissions.all()

    # Fall through: both anon users and users without permissions
    # get here, e.g. speakers or attendees.
    wip = event.wip_schedule
    if not user.is_anonymous and wip and can_view_wip_schedule(user, event):
        return Submission.objects.filter(
            pk__in=wip.talks.filter(submission__isnull=False).values_list('submission_id', flat=True)
        )

    if user.has_perm('base.list_schedule', event):
        schedule = event.current_schedule
        if not schedule:
            return event.submissions.none()
        return event.submissions.filter(
            pk__in=schedule.talks.filter(
                is_visible=True,
                submission__isnull=False,
            ).values_list('submission_id', flat=True)
        )
    return event.submissions.none()


@rules.predicate
def is_wip(user, obj):
    schedule = getattr(obj, 'schedule', None)
    if schedule is None and hasattr(obj, 'version') and hasattr(obj, 'event'):
        schedule = obj
    if schedule is None and hasattr(obj, 'current_schedule'):
        schedule = obj.current_schedule
    if schedule is None:
        return True
    return getattr(schedule, 'version', None) is None


@rules.predicate
def is_feedback_ready(user, obj):
    return obj.does_accept_feedback


@rules.predicate
def is_break(user, obj):
    return not obj.submission


@rules.predicate
def is_review_author(user, obj):
    return obj and obj.user == user


@rules.predicate
def is_comment_author(user, obj):
    return obj and obj.user == user


@rules.predicate
def submission_comments_active(user, obj):
    return obj.event.get_feature_flag('use_submission_comments')


def speaker_profiles_for_user(event, user, submissions=None):
    submissions = submissions or submissions_for_user(event, user)
    from eventyay.base.models import SpeakerProfile, User

    return SpeakerProfile.objects.filter(event=event, user__in=User.objects.filter(submissions__in=submissions))


def get_reviewable_submissions(event, user, queryset=None):
    """Returns all submissions the user is permitted to review.

    Excludes submissions this user has submitted, and takes track team permissions,
    assignments and review phases into account. The result is ordered by review count.
    """
    from eventyay.base.models import SubmissionStates

    if queryset is None:
        queryset = event.submissions.filter(state=SubmissionStates.SUBMITTED)
    queryset = limit_for_reviewers(queryset, event, user, add_assignments=True)
    queryset = queryset.annotate(review_count=Count('reviews'))
    # This is not randomised, because order_by("review_count", "?") sets all annotated
    # review_count values to 1.
    return queryset.order_by('-is_assigned', 'review_count')


def get_missing_reviews(event, user, ignore=None):
    from eventyay.base.models import SubmissionStates

    queryset = event.submissions.filter(state=SubmissionStates.SUBMITTED).exclude(reviews__user=user)
    if ignore:
        queryset = queryset.exclude(pk__in=ignore)
    return get_reviewable_submissions(event, user, queryset=queryset)

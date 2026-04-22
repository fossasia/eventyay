import logging

from django.http import HttpRequest
from django_scopes import scope

logger = logging.getLogger(__name__)


def is_admin_mode_active(request: HttpRequest) -> bool:
    if request and hasattr(request.user, 'has_active_staff_session') and request.user.has_active_staff_session(request.session.session_key):
        logger.debug(
            'User %s has active staff session - granting admin access to %s',
            request.user,
            request.path
        )
        return True

    return False


def is_event_organiser(user, request, event=None) -> bool:
    """Check if a user is an organiser for the given event.

    Returns True only if the user is a platform admin, has an active
    staff session, or is a member of a team assigned to this event
    (including teams with ``all_events=True``).
    """
    if not user.is_authenticated or not event:
        return False
    if user.is_administrator:
        return True
    return user.has_event_permission(
        event.organizer, event, request=request
    )


def user_has_cfp_submissions(request: HttpRequest, event=None) -> bool:
    if not request or not event:
        return False
    if not request.user.is_authenticated:
        return False

    submission_cache = getattr(request, 'eventyay_user_has_cfp_submissions_cache', None)
    if submission_cache is None:
        submission_cache = {}
        request.eventyay_user_has_cfp_submissions_cache = submission_cache

    event_pk = event.pk
    if event_pk not in submission_cache:
        with scope(event=event):
            submission_cache[event_pk] = event.submissions.filter(speakers=request.user).exists()

    return submission_cache[event_pk]

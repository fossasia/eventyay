import datetime as dt
from enum import StrEnum

from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import Event, Order, OrderPosition, User
from eventyay.talk_rules.agenda import is_agenda_submission_visible


class TicketCheckResult(StrEnum):
    HAS_TICKET = 'has_ticket'
    MISCONFIGURED = 'missing_configuration'
    NO_TICKET = 'no_ticket'


def user_has_event_ticket(user: User, event: Event) -> TicketCheckResult:
    """Return whether the user owns a valid admission ticket for the event."""
    if not user or not user.is_authenticated or not user.email:
        return TicketCheckResult.NO_TICKET

    allowed_statuses = [Order.STATUS_PAID]
    if event.settings.venueless_allow_pending:
        allowed_statuses.append(Order.STATUS_PENDING)

    with scope(organizer=event.organizer):
        with scope(event=event):
            if event.settings.venueless_all_products:
                has_ticket = OrderPosition.objects.filter(
                    order__event=event,
                    order__email__iexact=user.email,
                    order__status__in=allowed_statuses,
                    product__admission=True,
                    canceled=False,
                    addon_to__isnull=True,
                ).exists()
            else:
                allowed_products = event.settings.venueless_products or []
                if not allowed_products:
                    return TicketCheckResult.NO_TICKET
                has_ticket = OrderPosition.objects.filter(
                    order__event=event,
                    order__email__iexact=user.email,
                    order__status__in=allowed_statuses,
                    product_id__in=allowed_products,
                    canceled=False,
                    addon_to__isnull=True,
                ).exists()

    if has_ticket:
        return TicketCheckResult.HAS_TICKET
    return TicketCheckResult.NO_TICKET


def _session_end(slot):
    return slot.end or slot.start


def feedback_period_open(submission) -> bool:
    """Return whether the feedback window is open for new comments on this submission."""
    event = submission.event
    if not event.get_feature_flag('use_feedback'):
        return False

    slot = submission.slot
    if not slot:
        return False

    enable_time = event.get_feature_flag('feedback_enable_time') or 'finished'
    if enable_time == 'published':
        if not is_agenda_submission_visible(None, submission):
            return False
    elif not _session_end(slot) or _session_end(slot) >= now():
        return False

    close_after_days = event.get_feature_flag('feedback_close_after_days')
    if close_after_days:
        try:
            close_after_days = int(close_after_days)
        except (TypeError, ValueError):
            close_after_days = 0
        if close_after_days > 0:
            deadline = _session_end(slot) + dt.timedelta(days=close_after_days)
            if now() >= deadline:
                return False

    return True


def user_can_give_feedback(user, submission) -> bool:
    """Return whether the given user may submit new feedback on this submission."""
    if not user or not user.is_authenticated:
        return False
    if not feedback_period_open(submission):
        return False

    event = submission.event
    if event.banned_users.filter(id=user.id).exists():
        return False

    if user.has_perm('base.orga_update_submission', submission):
        return True

    who_can_comment = event.get_feature_flag('feedback_who_can_comment') or 'attendees'
    if who_can_comment == 'registered':
        return True

    return user_has_event_ticket(user, event) == TicketCheckResult.HAS_TICKET


def get_feedback_anonymous_mode(event) -> str:
    """Return how anonymous feedback is handled for this event.

    Modes:
    - ``public``: all feedback is public; users cannot post anonymously
    - ``optional``: users can choose public or anonymous feedback
    - ``always``: all feedback is anonymous
    """
    mode = event.get_feature_flag('feedback_anonymous_mode')
    if mode in ('public', 'optional', 'always'):
        return mode
    if event.get_feature_flag('feedback_allow_anonymous'):
        return 'optional'
    return 'public'


def feedback_is_public_for_submission(event, is_public=None) -> bool:
    """Resolve whether a new feedback submission should be public."""
    mode = get_feedback_anonymous_mode(event)
    if mode == 'always':
        return False
    if mode == 'public':
        return True
    return bool(is_public)

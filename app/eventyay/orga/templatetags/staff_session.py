from django import template
from django.conf import settings
from django.db.models import Q

from eventyay.common.permissions import is_admin_mode_active
from eventyay.base.models.auth import StaffSession, User

register = template.Library()


@register.simple_tag()
def has_event_perm(perm, user, request, obj=None):
    if not user.is_authenticated:
        return False
    return is_admin_mode_active(request) or User.has_perm(user, perm, obj)


@register.simple_tag()
def is_event_organiser(user, request, event=None):
    """Check if a user is an organiser for the given event.

    Returns True only if the user is a platform admin, has an active
    staff session, or is a member of a team assigned to this event.
    """
    if not user.is_authenticated or not event:
        return False
    if is_admin_mode_active(request):
        return True
    if user.is_administrator:
        return True
    return event.teams.filter(members__in=[user]).exists()


@register.filter
def has_active_staff_session(user, session_key):
    return user.has_active_staff_session(session_key)


@register.simple_tag
def staff_need_to_explain(user):
    if user.is_staff and settings.EVENTYAY_ADMIN_AUDIT_COMMENTS:
        return StaffSession.objects.filter(
            user=user, date_end__isnull=False
        ).filter(Q(comment__isnull=True) | Q(comment=''))
    return StaffSession.objects.none()

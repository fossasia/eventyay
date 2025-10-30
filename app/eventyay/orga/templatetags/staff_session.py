from django import template
from django.conf import settings
from django.db.models import Q

from eventyay.common.permissions import check_admin_mode
from eventyay.base.models.auth import StaffSession, User

register = template.Library()


@register.simple_tag()
def has_event_perm(perm, user, request, obj=None):
    return check_admin_mode(request) or User.has_perm(user, perm, obj)


@register.filter
def has_active_staff_session(user, session_key):
    return user.has_active_staff_session(session_key)


@register.simple_tag
def staff_need_to_explain(user):
    if user.is_staff and settings.PRETIX_ADMIN_AUDIT_COMMENTS:
        return StaffSession.objects.filter(
            user=user, date_end__isnull=False
        ).filter(Q(comment__isnull=True) | Q(comment=''))
    return StaffSession.objects.none()

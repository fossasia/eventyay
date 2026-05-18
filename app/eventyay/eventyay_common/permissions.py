"""Shared permission helpers for eventyay_common and related UI."""

from django.http import HttpRequest

from eventyay.base.models import Event, Organizer
from eventyay.base.models.auth import User

TICKET_DASHBOARD_PERMISSIONS = (
    'can_view_orders',
    'can_change_orders',
    'can_change_items',
    'can_change_event_settings',
    'can_checkin_orders',
    'can_view_vouchers',
    'can_change_vouchers',
)


def user_has_ticket_dashboard_access(
    user: User,
    organizer: Organizer,
    event: Event,
    request: HttpRequest | None = None,
) -> bool:
    return user.has_event_permission(
        organizer,
        event,
        TICKET_DASHBOARD_PERMISSIONS,
        request=request,
    )


def filter_timeline_entry_for_ticket_access(entry, has_ticket_access):
    """Hide ticket control edit links on the common dashboard for talk-only users."""
    if has_ticket_access or not entry.edit_url:
        return entry
    if '/control/' in entry.edit_url:
        return entry._replace(edit_url=None)
    return entry

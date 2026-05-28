"""Shared permission helpers for eventyay_common and related UI."""

from urllib.parse import urlparse

from django.http import HttpRequest
from django.urls import Resolver404, resolve

from eventyay.base.models import Event, Organizer
from eventyay.base.models.auth import User
from eventyay.eventyay_common.video.permissions import VIDEO_PERMISSION_DEFINITIONS

TICKET_DASHBOARD_PERMISSIONS = (
    'can_view_orders',
    'can_change_orders',
    'can_change_items',
    'can_change_event_settings',
    'can_checkin_orders',
    'can_view_vouchers',
    'can_change_vouchers',
)

TALK_DASHBOARD_PERMISSIONS = (
    'can_change_submissions',
    'is_reviewer',
)

VIDEO_DASHBOARD_PERMISSIONS = tuple(VIDEO_PERMISSION_DEFINITIONS.keys())


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


def user_has_talk_dashboard_access(
    user: User,
    organizer: Organizer,
    event: Event,
    request: HttpRequest | None = None,
) -> bool:
    return user.has_event_permission(
        organizer,
        event,
        TALK_DASHBOARD_PERMISSIONS,
        request=request,
    )


def user_has_video_dashboard_access(
    user: User,
    organizer: Organizer,
    event: Event,
    request: HttpRequest | None = None,
) -> bool:
    return user.has_event_permission(
        organizer,
        event,
        VIDEO_DASHBOARD_PERMISSIONS,
        request=request,
    )


def _is_control_url(url: str) -> bool:
    if not url:
        return False
    path = urlparse(url).path if '://' in url else url
    if not path.startswith('/'):
        path = f'/{path}'
    try:
        match = resolve(path)
    except Resolver404:
        return False
    return match.namespace == 'control'


def filter_timeline_entry_for_ticket_access(entry, has_ticket_access):
    """Hide pretix control edit links on the common dashboard timeline for talk-only users."""
    if has_ticket_access or not entry.edit_url:
        return entry
    if _is_control_url(entry.edit_url):
        return entry._replace(edit_url=None)
    return entry

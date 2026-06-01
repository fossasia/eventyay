"""Shared permission helpers for eventyay_common and related UI."""

from urllib.parse import urlparse

from django.http import HttpRequest
from django.urls import Resolver404, resolve, reverse

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
    if not user.is_authenticated:
        return False
    return bool(
        user.has_event_permission(
            organizer,
            event,
            TICKET_DASHBOARD_PERMISSIONS,
            request=request,
        )
    )


def user_has_talk_dashboard_access(
    user: User,
    organizer: Organizer,
    event: Event,
    request: HttpRequest | None = None,
) -> bool:
    if not user.is_authenticated:
        return False
    return bool(
        user.has_event_permission(
            organizer,
            event,
            TALK_DASHBOARD_PERMISSIONS,
            request=request,
        )
    )


def user_has_video_dashboard_access(
    user: User,
    organizer: Organizer,
    event: Event,
    request: HttpRequest | None = None,
) -> bool:
    if not user.is_authenticated:
        return False
    return bool(
        user.has_event_permission(
            organizer,
            event,
            VIDEO_DASHBOARD_PERMISSIONS,
            request=request,
        )
    )


def _control_path_prefix() -> str:
    """Path prefix for URLs in the ``control`` namespace (includes ``FORCE_SCRIPT_NAME``)."""
    return urlparse(reverse('control:index')).path.rstrip('/')


def _is_control_url(url: str) -> bool:
    """True when ``url`` resolves to a view in the ``control`` URL namespace."""
    if not url:
        return False
    path = urlparse(url).path
    if not path.startswith('/'):
        path = f'/{path}'
    prefix = _control_path_prefix()
    resolve_path = path
    if prefix and resolve_path.startswith(f'{prefix}/'):
        resolve_path = resolve_path[len(prefix) :]
        if not resolve_path.startswith('/'):
            resolve_path = f'/{resolve_path}'
    elif resolve_path == prefix:
        resolve_path = '/'
    try:
        match = resolve(resolve_path)
    except Resolver404:
        return path == prefix or path.startswith(f'{prefix}/')
    return bool(match.namespaces and match.namespaces[0] == 'control')


def filter_timeline_entry_for_ticket_access(entry, has_ticket_access):
    """Hide pretix control edit links on the common dashboard timeline for talk-only users."""
    if has_ticket_access or not entry.edit_url:
        return entry
    if _is_control_url(entry.edit_url):
        return entry._replace(edit_url=None)
    return entry

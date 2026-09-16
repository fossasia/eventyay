"""Build the event-scoped API endpoint catalog for the organiser API area."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable
from urllib.parse import urljoin

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from eventyay.base.meetup import is_meetup_event
from eventyay.base.models import Event, Team
from eventyay.eventyay_common.utils import EventCreatedFor
from eventyay.helpers.plugin_enable import is_video_enabled


ACCESS_PUBLIC = 'public'
ACCESS_AUTHENTICATED = 'authenticated'
ACCESS_RESTRICTED = 'restricted'

ACCESS_LABELS = {
    ACCESS_PUBLIC: _('Public'),
    ACCESS_AUTHENTICATED: _('Authenticated'),
    ACCESS_RESTRICTED: _('Restricted'),
}

# Any of these grants access to the Event → API page (OR semantics).
API_PAGE_PERMISSIONS = (
    'can_change_event_settings',
    'can_change_items',
    'can_view_orders',
    'can_change_orders',
    'can_view_vouchers',
    'can_change_vouchers',
    'can_checkin_orders',
    'can_change_submissions',
    'can_change_teams',
)


@dataclass(frozen=True)
class ApiEndpoint:
    name: str
    url: str
    access: str
    methods: str
    description: str
    required_permission: str | None = None
    write_permission: str | None = None
    user_can_write: bool = False
    read_permission_label: str | None = None
    write_permission_label: str | None = None


@dataclass(frozen=True)
class ApiEndpointGroup:
    key: str
    label: str
    description: str
    endpoints: tuple[ApiEndpoint, ...]


def _site_base() -> str:
    return settings.SITE_URL.rstrip('/') + '/'


def tickets_api_base(event: Event) -> str:
    return urljoin(
        _site_base(),
        f'api/v1/organizers/{event.organizer.slug}/events/{event.slug}/',
    )


def talks_api_base(event: Event) -> str:
    # Event.api_urls already encodes TALK_BASE_PATH; prefer that when available.
    # urlman exposes ``.full`` as a method; call it so templates get a real URL.
    return event.api_urls.base.full()


def docs_urls() -> dict[str, str]:
    return {
        'reference': 'https://docs.eventyay.com/api-reference/index.html',
        'swagger': urljoin(_site_base(), 'api/v1/docs/'),
        'schema': urljoin(_site_base(), 'api/v1/schema/'),
    }


def permission_label(perm: str | None) -> str | None:
    if not perm:
        return None
    try:
        return str(Team._meta.get_field(perm).verbose_name)
    except FieldDoesNotExist:
        return perm


def event_has_tickets_component(event: Event) -> bool:
    """Whether ticketing APIs are relevant for this event."""
    if is_meetup_event(event):
        return True
    create_for = event.settings.get('create_for', EventCreatedFor.BOTH.value)
    return create_for in (EventCreatedFor.BOTH.value, EventCreatedFor.TICKET.value)


def event_has_talks_component(event: Event) -> bool:
    """Whether talks/schedule APIs are relevant for this event."""
    if is_meetup_event(event):
        return False
    create_for = event.settings.get('create_for', EventCreatedFor.BOTH.value)
    if create_for in (EventCreatedFor.BOTH.value, EventCreatedFor.TALK.value):
        return True
    # Migrated events may have talk settings without create_for=talk.
    return event.settings.get('talk_schedule_public') is not None


def user_can_access_event_api(request: HttpRequest, event: Event) -> bool:
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'is_administrator', False):
        return True
    perm_request = request if hasattr(request, 'session') else None
    return user.has_event_permission(
        event.organizer,
        event,
        API_PAGE_PERMISSIONS,
        request=perm_request,
    )


def _has_perm(request: HttpRequest, event: Event, perm: str | None) -> bool:
    if not perm:
        return True
    user = request.user
    if not user.is_authenticated:
        return False
    if getattr(user, 'is_administrator', False):
        return True
    perm_request = request if hasattr(request, 'session') else None
    return user.has_event_permission(event.organizer, event, perm, request=perm_request)


def _annotate_endpoint(request: HttpRequest, event: Event, endpoint: ApiEndpoint) -> ApiEndpoint:
    can_write = bool(endpoint.write_permission) and _has_perm(
        request, event, endpoint.write_permission
    )
    return replace(
        endpoint,
        user_can_write=can_write,
        read_permission_label=permission_label(endpoint.required_permission),
        write_permission_label=permission_label(endpoint.write_permission),
    )


def _filter_endpoints(
    request: HttpRequest,
    event: Event,
    endpoints: Iterable[ApiEndpoint],
) -> tuple[ApiEndpoint, ...]:
    """Show endpoints the user can read or write; annotate write capability."""
    visible = []
    for endpoint in endpoints:
        can_read = _has_perm(request, event, endpoint.required_permission)
        can_write = bool(endpoint.write_permission) and _has_perm(
            request, event, endpoint.write_permission
        )
        if endpoint.access != ACCESS_PUBLIC and not can_read and not can_write:
            continue
        visible.append(_annotate_endpoint(request, event, endpoint))
    return tuple(visible)


def build_api_catalog(request: HttpRequest, event: Event) -> list[ApiEndpointGroup]:
    """Return endpoint groups the current user may see for this event."""
    tickets_base = tickets_api_base(event)
    talks_base = talks_api_base(event)
    show_tickets = event_has_tickets_component(event)
    show_talks = event_has_talks_component(event)
    show_video = bool(event.is_video_creation) or is_video_enabled(event)

    groups: list[ApiEndpointGroup] = []

    event_defs: list[ApiEndpoint] = []
    if show_tickets:
        event_defs.append(
            ApiEndpoint(
                name=_('Event (tickets API)'),
                url=tickets_base,
                access=ACCESS_AUTHENTICATED,
                methods='GET',
                description=_('Event metadata via the organiser-scoped tickets API.'),
                required_permission='can_change_event_settings',
            )
        )
    if show_talks:
        event_defs.append(
            ApiEndpoint(
                name=_('Event (talks API)'),
                url=talks_base,
                access=ACCESS_PUBLIC,
                methods='GET',
                description=_('Public event resource for talks, schedule, and speakers.'),
            )
        )
    event_endpoints = _filter_endpoints(request, event, event_defs)
    if event_endpoints:
        groups.append(
            ApiEndpointGroup(
                key='event',
                label=_('Event'),
                description=_('Core event resources.'),
                endpoints=event_endpoints,
            )
        )

    if show_tickets:
        ticket_endpoints = _filter_endpoints(
            request,
            event,
            (
                ApiEndpoint(
                    name=_('Products'),
                    url=urljoin(tickets_base, 'products/'),
                    access=ACCESS_AUTHENTICATED,
                    methods='GET, POST, PATCH, DELETE',
                    description=_('Ticket products and variations. Any event team token can read.'),
                    write_permission='can_change_items',
                ),
                ApiEndpoint(
                    name=_('Categories'),
                    url=urljoin(tickets_base, 'categories/'),
                    access=ACCESS_AUTHENTICATED,
                    methods='GET, POST, PATCH, DELETE',
                    description=_('Product categories.'),
                    write_permission='can_change_items',
                ),
                ApiEndpoint(
                    name=_('Quotas'),
                    url=urljoin(tickets_base, 'quotas/'),
                    access=ACCESS_AUTHENTICATED,
                    methods='GET, POST, PATCH, DELETE',
                    description=_('Availability quotas for products.'),
                    write_permission='can_change_items',
                ),
                ApiEndpoint(
                    name=_('Questions'),
                    url=urljoin(tickets_base, 'questions/'),
                    access=ACCESS_AUTHENTICATED,
                    methods='GET, POST, PATCH, DELETE',
                    description=_('Attendee questions attached to ticket products.'),
                    write_permission='can_change_items',
                ),
                ApiEndpoint(
                    name=_('Orders'),
                    url=urljoin(tickets_base, 'orders/'),
                    access=ACCESS_RESTRICTED,
                    methods='GET, POST, PATCH',
                    description=_('Orders and payments.'),
                    required_permission='can_view_orders',
                    write_permission='can_change_orders',
                ),
                ApiEndpoint(
                    name=_('Vouchers'),
                    url=urljoin(tickets_base, 'vouchers/'),
                    access=ACCESS_RESTRICTED,
                    methods='GET, POST, PATCH, DELETE',
                    description=_('Discount and access vouchers.'),
                    required_permission='can_view_vouchers',
                    write_permission='can_change_vouchers',
                ),
                ApiEndpoint(
                    name=_('Invoices'),
                    url=urljoin(tickets_base, 'invoices/'),
                    access=ACCESS_RESTRICTED,
                    methods='GET',
                    description=_('Generated invoices for orders.'),
                    required_permission='can_view_orders',
                ),
                ApiEndpoint(
                    name=_('Waiting list'),
                    url=urljoin(tickets_base, 'waitinglistentries/'),
                    access=ACCESS_RESTRICTED,
                    methods='GET, POST, PATCH, DELETE',
                    description=_('Waiting list entries.'),
                    required_permission='can_view_orders',
                    write_permission='can_change_orders',
                ),
            ),
        )
        if ticket_endpoints:
            groups.append(
                ApiEndpointGroup(
                    key='tickets',
                    label=_('Tickets'),
                    description=_('Ticketing products, orders, vouchers, and related resources.'),
                    endpoints=ticket_endpoints,
                )
            )

        attendee_endpoints = _filter_endpoints(
            request,
            event,
            (
                ApiEndpoint(
                    name=_('Order positions'),
                    url=urljoin(tickets_base, 'orderpositions/'),
                    access=ACCESS_RESTRICTED,
                    methods='GET, PATCH',
                    description=_('Individual ticket positions (attendees) within orders.'),
                    required_permission='can_view_orders',
                    write_permission='can_change_orders',
                ),
                ApiEndpoint(
                    name=_('Check-in lists'),
                    url=urljoin(tickets_base, 'checkinlists/'),
                    access=ACCESS_RESTRICTED,
                    methods='GET, POST, PATCH, DELETE',
                    description=_('Check-in lists. Writes require event settings permission.'),
                    required_permission='can_view_orders',
                    write_permission='can_change_event_settings',
                ),
            ),
        )
        if attendee_endpoints:
            groups.append(
                ApiEndpointGroup(
                    key='attendees',
                    label=_('Attendees'),
                    description=_('Attendee positions and check-in.'),
                    endpoints=attendee_endpoints,
                )
            )

    if show_talks:
        talk_endpoints = _filter_endpoints(
            request,
            event,
            (
                ApiEndpoint(
                    name=_('Submissions / sessions'),
                    url=urljoin(talks_base, 'submissions/'),
                    access=ACCESS_PUBLIC,
                    methods='GET, POST, PATCH, DELETE',
                    description=_('Talk submissions. Public read; writes need organiser access.'),
                    write_permission='can_change_submissions',
                ),
                ApiEndpoint(
                    name=_('Reviews'),
                    url=urljoin(talks_base, 'reviews/'),
                    access=ACCESS_RESTRICTED,
                    methods='GET, POST, PATCH, DELETE',
                    description=_('Proposal reviews. Restricted to review teams.'),
                    required_permission='can_change_submissions',
                    write_permission='can_change_submissions',
                ),
                ApiEndpoint(
                    name=_('Tracks'),
                    url=urljoin(talks_base, 'tracks/'),
                    access=ACCESS_PUBLIC,
                    methods='GET, POST, PATCH, DELETE',
                    description=_('Session tracks.'),
                    write_permission='can_change_event_settings',
                ),
                ApiEndpoint(
                    name=_('Submission types'),
                    url=urljoin(talks_base, 'submission-types/'),
                    access=ACCESS_PUBLIC,
                    methods='GET, POST, PATCH, DELETE',
                    description=_('Talk types (talk, workshop, …).'),
                    write_permission='can_change_event_settings',
                ),
                ApiEndpoint(
                    name=_('Tags'),
                    url=urljoin(talks_base, 'tags/'),
                    access=ACCESS_PUBLIC,
                    methods='GET, POST, PATCH, DELETE',
                    description=_('Submission tags.'),
                    write_permission='can_change_submissions',
                ),
            ),
        )
        if talk_endpoints:
            groups.append(
                ApiEndpointGroup(
                    key='talks',
                    label=_('Talks'),
                    description=_('Sessions, reviews, tracks, and related talk resources.'),
                    endpoints=talk_endpoints,
                )
            )

        speaker_endpoints = _filter_endpoints(
            request,
            event,
            (
                ApiEndpoint(
                    name=_('Speakers'),
                    url=urljoin(talks_base, 'speakers/'),
                    access=ACCESS_PUBLIC,
                    methods='GET, PATCH',
                    description=_('Speaker profiles linked to this event.'),
                    write_permission='can_change_submissions',
                ),
            ),
        )
        if speaker_endpoints:
            groups.append(
                ApiEndpointGroup(
                    key='speakers',
                    label=_('Speakers'),
                    description=_('Speaker profiles for this event.'),
                    endpoints=speaker_endpoints,
                )
            )

        schedule_endpoints = _filter_endpoints(
            request,
            event,
            (
                ApiEndpoint(
                    name=_('Schedules'),
                    url=urljoin(talks_base, 'schedules/'),
                    access=ACCESS_PUBLIC,
                    methods='GET',
                    description=_('Published and draft schedule versions.'),
                ),
                ApiEndpoint(
                    name=_('Slots'),
                    url=urljoin(talks_base, 'slots/'),
                    access=ACCESS_PUBLIC,
                    methods='GET',
                    description=_('Scheduled talk slots.'),
                ),
                ApiEndpoint(
                    name=_('Rooms'),
                    url=urljoin(talks_base, 'rooms/'),
                    access=ACCESS_PUBLIC,
                    methods='GET, POST, PATCH, DELETE',
                    description=_('Venue rooms used by the schedule.'),
                    write_permission='can_change_event_settings',
                ),
            ),
        )
        if schedule_endpoints:
            groups.append(
                ApiEndpointGroup(
                    key='schedule',
                    label=_('Schedule'),
                    description=_('Schedule releases, slots, and rooms.'),
                    endpoints=schedule_endpoints,
                )
            )

    if show_video:
        video_endpoints = _filter_endpoints(
            request,
            event,
            (
                ApiEndpoint(
                    name=_('Video (WebSocket)'),
                    url=urljoin(_site_base(), f'ws/event/{event.slug}/'),
                    access=ACCESS_AUTHENTICATED,
                    methods='WS',
                    description=_('Realtime video platform connection. Uses event JWT authentication.'),
                    required_permission='can_change_event_settings',
                ),
                ApiEndpoint(
                    name=_('Stream schedules'),
                    url=urljoin(talks_base, 'rooms/'),
                    access=ACCESS_RESTRICTED,
                    methods='GET, POST, PATCH, DELETE',
                    description=_('Per-room stream schedules nested under rooms.'),
                    required_permission='can_change_event_settings',
                    write_permission='can_change_event_settings',
                ),
            ),
        )
        if video_endpoints:
            groups.append(
                ApiEndpointGroup(
                    key='video',
                    label=_('Video'),
                    description=_('Live video and streaming-related access.'),
                    endpoints=video_endpoints,
                )
            )

    return groups


def access_levels() -> list[dict[str, str]]:
    return [
        {
            'key': ACCESS_PUBLIC,
            'label': str(ACCESS_LABELS[ACCESS_PUBLIC]),
            'description': str(
                _(
                    'Readable without authentication. Organiser tokens may still return '
                    'additional private fields.'
                )
            ),
        },
        {
            'key': ACCESS_AUTHENTICATED,
            'label': str(ACCESS_LABELS[ACCESS_AUTHENTICATED]),
            'description': str(
                _('Requires a valid API token, device token, session, or OAuth credential.')
            ),
        },
        {
            'key': ACCESS_RESTRICTED,
            'label': str(ACCESS_LABELS[ACCESS_RESTRICTED]),
            'description': str(
                _(
                    'Requires organiser or admin permissions matching the endpoint '
                    '(for example order or team permissions).'
                )
            ),
        },
        {
            'key': 'organiser',
            'label': str(_('Organiser API access')),
            'description': str(
                _(
                    'Team API tokens inherit the permissions of the team they belong to. '
                    'They do not have a separate per-token scope. Talk User API tokens can '
                    'be limited to specific events and endpoints.'
                )
            ),
        },
        {
            'key': 'admin',
            'label': str(_('Admin API access')),
            'description': str(
                _('System administrators can access all organiser APIs for troubleshooting.')
            ),
        },
        {
            'key': 'read_write',
            'label': str(_('Read vs write')),
            'description': str(
                _(
                    'Safe methods (GET) often need weaker permissions than create, update, '
                    'or delete. Each endpoint lists the team permission required for reads '
                    'and for writes when they differ.'
                )
            ),
        },
    ]

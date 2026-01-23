import logging
from collections.abc import Sequence
from typing import List, TypedDict

from django.http import HttpRequest
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import Event
from eventyay.control.navigation import merge_in
from eventyay.control.signals import nav_global, nav_organizer

logger = logging.getLogger(__name__)


class MenuItem(TypedDict):
    label: str
    url: str
    active: bool
    icon: str


def get_global_navigation(request: HttpRequest) -> List[MenuItem]:
    """Generate navigation items for global."""
    url = request.resolver_match
    if not url:
        return []
    nav = [
        {
            'label': _('My Orders'),
            'url': reverse('eventyay_common:orders'),
            'active': 'orders' in url.url_name,
            'icon': 'shopping-cart',
        },
        {
            'label': _('My Sessions'),
            'url': reverse('eventyay_common:sessions'),
            'active': 'sessions' in url.url_name,
            'icon': 'sticky-note-o',
        },
        {
            'label': _('My Events'),
            'url': reverse('eventyay_common:events'),
            'active': 'events' in url.url_name,
            'icon': 'calendar',
        },
        {
            'label': _('Organizers'),
            'url': reverse('eventyay_common:organizers'),
            'active': 'organizers' in url.url_name,
            'icon': 'group',
        },
    ]

    # Merge plugin-provided navigation items
    plugin_responses = nav_global.send(request, request=request)
    plugin_nav_items = []
    for receiver, response in plugin_responses:
        if response:
            plugin_nav_items.extend(response)

    # Sort navigation items, prioritizing non-parent items and alphabetically
    sorted_plugin_items = sorted(plugin_nav_items, key=lambda r: (1 if r.get('parent') else 0, r['label']))

    # Merge plugin items into default navigation
    merge_in(nav, sorted_plugin_items)

    return nav


def get_event_navigation(request: HttpRequest, event: Event) -> List[MenuItem]:
    """Generate navigation items for an event."""
    url = request.resolver_match
    if not url:
        return []
    has_settings_perm = request.user.has_event_permission(
        event.organizer,
        event,
        'can_change_event_settings',
        request=request,
    )
    if not has_settings_perm:
        return []
    nav = [
        {
            'label': _('Settings'),
            'url': reverse(
                'eventyay_common:event.update',
                kwargs={
                    'event': event.slug,
                    'organizer': event.organizer.slug,
                },
            ),
            'active': (url.url_name == 'event.update'),
            'icon': 'wrench',
        },
        {
            'label': _('Plugins'),
            'url': reverse(
                'eventyay_common:event.plugins',
                kwargs={
                    'event': event.slug,
                    'organizer': event.organizer.slug,
                },
            ),
            'active': (url.url_name == 'event.plugins'),
            'icon': 'plug',
        },
    ]

    return nav


def get_organizer_navigation(request: HttpRequest) -> List[MenuItem]:
    url = request.resolver_match
    if not url:
        return []
    nav = [
        {
            'label': _('Events'),
            'url': reverse('eventyay_common:organizer.events', kwargs={'organizer': request.organizer.slug}),
            'active': url.url_name == 'organizer.events',
            'icon': 'calendar',
        },
    ]
    orgapermset = getattr(request, 'orgapermset', None)
    if orgapermset is None:
        return get_global_navigation(request)
    if 'can_change_organizer_settings' in orgapermset:
        nav.append(
            {
                'label': _('Settings'),
                'url': reverse(
                    'eventyay_common:organizer.edit',
                    kwargs={'organizer': request.organizer.slug},
                ),
                'icon': 'wrench',
                'children': [
                    {
                        'label': _('General'),
                        'url': reverse(
                            'eventyay_common:organizer.edit',
                            kwargs={'organizer': request.organizer.slug},
                        ),
                        'active': url.url_name == 'organizer.edit',
                    },
                    # Temporary disabled
                    # {
                    #     'label': _('Event metadata'),
                    #     'url': reverse('control:organizer.properties', kwargs={
                    #         'organizer': request.organizer.slug
                    #     }),
                    #     'active': url.url_name.startswith('organizer.propert'),
                    # },
                    # {
                    #     'label': _('Webhooks'),
                    #     'url': reverse('control:organizer.webhooks', kwargs={
                    #         'organizer': request.organizer.slug
                    #     }),
                    #     'active': 'organizer.webhook' in url.url_name,
                    #     'icon': 'bolt',
                    # },
                    {
                        'label': _('Billing settings'),
                        'url': reverse(
                            'eventyay_common:organizer.billing',
                            kwargs={'organizer': request.organizer.slug},
                        ),
                        'active': url.url_name == 'organizer.billing',
                    },
                ],
            }
        )
    if 'can_change_teams' in request.orgapermset:
        nav.append(
            {
                'label': _('Teams'),
                'url': reverse(
                    'eventyay_common:organizer.teams',
                    kwargs={'organizer': request.organizer.slug},
                )
                + '?section=permissions',
                'active': url.url_name == 'organizer.teams',
                'icon': 'group',
            }
        )

    # if 'can_manage_gift_cards' in request.orgapermset:
    #     nav.append({
    #         'label': _('Gift cards'),
    #         'url': reverse('control:organizer.giftcards', kwargs={
    #             'organizer': request.organizer.slug
    #         }),
    #         'active': 'organizer.giftcard' in url.url_name,
    #         'icon': 'credit-card',
    #     })
    if 'can_change_organizer_settings' in request.orgapermset:
        nav.append(
            {
                'label': _('Devices'),
                'url': reverse(
                    'eventyay_common:organizer.devices',
                    kwargs={'organizer': request.organizer.slug},
                ),
                'icon': 'tablet',
                'children': [
                    {
                        'label': _('Devices'),
                        'url': reverse(
                            'eventyay_common:organizer.devices',
                            kwargs={'organizer': request.organizer.slug},
                        ),
                        'active': 'organizer.device' in url.url_name,
                    },
                    {
                        'label': _('Gates'),
                        'url': reverse(
                            'eventyay_common:organizer.gates',
                            kwargs={'organizer': request.organizer.slug},
                        ),
                        'active': 'organizer.gate' in url.url_name,
                    },
                ],
            }
        )

    nav.append(
        {
            'label': _('Export'),
            'url': reverse(
                'eventyay_common:organizer.export',
                kwargs={
                    'organizer': request.organizer.slug,
                },
            ),
            'active': 'organizer.export' in url.url_name,
            'icon': 'download',
        }
    )

    merge_in(
        nav,
        sorted(
            sum(
                (
                    list(a[1])
                    for a in nav_organizer.send(request.organizer, request=request, organizer=request.organizer)
                ),
                [],
            ),
            key=lambda r: (1 if r.get('parent') else 0, r['label']),
        ),
    )
    return nav


def get_account_navigation(request: HttpRequest) -> List[MenuItem]:
    """Generate navigation items for account."""
    resolver_match = request.resolver_match
    if not resolver_match:
        return []
    # Note that it does not include the "eventyay_common" namespace.
    visiting_url_name = resolver_match.url_name
    return [
        {
            'label': _('General'),
            'url': reverse('eventyay_common:account.general'),
            'active': is_url_matched(visiting_url_name, ('account.general', 'account.email')),
            'icon': 'user',
        },
        {
            'label': _('Notifications'),
            'url': reverse('eventyay_common:account.notifications'),
            'active': is_url_matched(visiting_url_name, ('account.notifications',)),
            'icon': 'bell',
        },
        {
            'label': _('Two-factor authentication'),
            'url': reverse('eventyay_common:account.2fa'),
            'active': is_url_matched(visiting_url_name, ('account.2fa',)),
            'icon': 'lock',
        },
        {
            'label': _('OAuth applications'),
            'url': reverse('eventyay_common:account.oauth.authorized-apps'),
            'active': is_url_matched(visiting_url_name, ('account.oauth',)),
            'icon': 'key',
        },
        {
            'label': _('History'),
            'url': reverse('eventyay_common:account.history'),
            'active': is_url_matched(visiting_url_name, ('account.history',)),
            'icon': 'history',
        },
    ]


def is_url_matched(url_name: str | None, prefixes: Sequence[str]) -> bool:
    """Check if the current URL name matches the given prefix."""
    return bool(url_name) and any(url_name.startswith(prefix) for prefix in prefixes)

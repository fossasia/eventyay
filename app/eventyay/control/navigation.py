from django.http import HttpRequest
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from eventyay.control.signals import (
    nav_event,
    nav_event_settings,
    nav_global,
    nav_organizer,
)


def get_event_navigation(request: HttpRequest):
    url = request.resolver_match
    if not url:
        return []
    nav = []
    if 'can_change_event_settings' in request.eventpermset:
        event_settings = [
            {
                'label': _('General'),
                'url': reverse(
                    'control:event.settings',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name == 'event.settings',
            },
            {
                'label': _('Payment'),
                'url': reverse(
                    'control:event.settings.payment',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name == 'event.settings.payment',
            },
            {
                'label': _('Tickets'),
                'url': reverse(
                    'control:event.settings.tickets',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name == 'event.settings.tickets',
            },
            {
                'label': _('E-mail'),
                'url': reverse(
                    'control:event.settings.mail',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name == 'event.settings.mail',
            },
            {
                'label': _('Tax rules'),
                'url': reverse(
                    'control:event.settings.tax',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name.startswith('event.settings.tax'),
            },
            {
                'label': _('Invoicing'),
                'url': reverse(
                    'control:event.settings.invoice',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name == 'event.settings.invoice',
            },
            {
                'label': pgettext_lazy('action', 'Cancellation'),
                'url': reverse(
                    'control:event.settings.cancel',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name == 'event.settings.cancel',
            },
            {
                'label': _('Widget'),
                'url': reverse(
                    'control:event.settings.widget',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name == 'event.settings.widget',
            },
        ]
        event_settings += sorted(
            sum(
                (list(a[1]) for a in nav_event_settings.send(request.event, request=request)),
                [],
            ),
            key=lambda r: r['label'],
        )
        nav.append(
            {
                'label': _('Settings'),
                'url': reverse(
                    'control:event.settings',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': False,
                'icon': 'wrench',
                'children': event_settings,
            }
        )
        if request.event.has_subevents:
            nav.append(
                {
                    'label': pgettext_lazy('subevent', 'Dates'),
                    'url': reverse(
                        'control:event.subevents',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': ('event.subevent' in url.url_name),
                    'icon': 'calendar',
                }
            )

    if 'can_change_items' in request.eventpermset:
        children = [
            {
                'label': _('Products'),
                'url': reverse(
                    'control:event.products',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name in ('event.product', 'event.products.add', 'event.products')
                or 'event.product.' in url.url_name,
            },
            {
                'label': _('Quotas'),
                'url': reverse(
                    'control:event.products.quotas',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': 'event.products.quota' in url.url_name,
            },
            {
                'label': _('Categories'),
                'url': reverse(
                    'control:event.products.categories',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': 'event.products.categories' in url.url_name,
            },
            {
                'label': _('Order forms'),
                'url': reverse(
                    'control:event.products.orderforms',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': 'event.products.orderforms' in url.url_name,
            },
            {
                'label': _('Forms'),
                'url': reverse(
                    'control:event.products.questions',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': 'event.products.questions' in url.url_name,
            },
        ]

        if 'can_view_vouchers' in request.eventpermset:
            children.extend(
                [
                    {
                        'label': _('Vouchers'),
                        'url': reverse(
                            'control:event.vouchers',
                            kwargs={
                                'event': request.event.slug,
                                'organizer': request.event.organizer.slug,
                            },
                        ),
                        'active': 'event.vouchers' in url.url_name,
                    }
                ]
            )

        nav.append(
            {
                'label': _('Products'),
                'url': reverse(
                    'control:event.products',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': False,
                'icon': 'ticket',
                'children': children,
            }
        )

    if 'can_view_orders' in request.eventpermset:
        children = [
            {
                'label': _('All orders'),
                'url': reverse(
                    'control:event.orders',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': url.url_name in ('event.orders', 'event.order', 'event.orders.search')
                or 'event.order.' in url.url_name,
            },
            {
                'label': _('Overview'),
                'url': reverse(
                    'control:event.orders.overview',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': 'event.orders.overview' in url.url_name,
            },
            {
                'label': _('Refunds'),
                'url': reverse(
                    'control:event.orders.refunds',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': 'event.orders.refunds' in url.url_name,
            },
            {
                'label': _('Export'),
                'url': reverse(
                    'control:event.orders.export',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': 'event.orders.export' in url.url_name,
            },
            {
                'label': _('Waiting list'),
                'url': reverse(
                    'control:event.orders.waitinglist',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': 'event.orders.waitinglist' in url.url_name,
            },
        ]
        if 'can_change_orders' in request.eventpermset:
            children.append(
                {
                    'label': _('Import'),
                    'url': reverse(
                        'control:event.orders.import',
                        kwargs={
                            'event': request.event.slug,
                            'organizer': request.event.organizer.slug,
                        },
                    ),
                    'active': 'event.orders.import' in url.url_name,
                }
            )
        nav.append(
            {
                'label': _('Orders'),
                'url': reverse(
                    'control:event.orders',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': False,
                'icon': 'shopping-cart',
                'children': children,
            }
        )

    if 'can_view_orders' in request.eventpermset:
        nav.append(
            {
                'label': pgettext_lazy('navigation', 'Check-in'),
                'url': reverse(
                    'control:event.orders.checkinlists',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    },
                ),
                'active': False,
                'icon': 'check-square-o',
                'children': [
                    {
                        'label': _('Check-in lists'),
                        'url': reverse(
                            'control:event.orders.checkinlists',
                            kwargs={
                                'event': request.event.slug,
                                'organizer': request.event.organizer.slug,
                            },
                        ),
                        'active': 'event.orders.checkin' in url.url_name,
                    },
                ],
            }
        )

    merge_in(
        nav,
        sorted(
            sum((list(a[1]) for a in nav_event.send(request.event, request=request)), []),
            key=lambda r: (1 if r.get('parent') else 0, r['label']),
        ),
    )

    return nav


def get_global_navigation(request):
    url = request.resolver_match
    if not url:
        return []
    nav = [
        {
            'label': _('My events'),
            'url': reverse('eventyay_common:events'),
            'active': 'events' in url.url_name,
            'icon': 'calendar',
        },
        {
            'label': _('Organizers'),
            'url': reverse('control:organizers'),
            'active': 'organizers' in url.url_name,
            'icon': 'group',
        },
        {
            'label': _('Order search'),
            'url': reverse('control:search.orders'),
            'active': 'search.orders' in url.url_name,
            'icon': 'search',
        },
    ]

    merge_in(
        nav,
        sorted(
            sum((list(a[1]) for a in nav_global.send(request, request=request)), []),
            key=lambda r: (1 if r.get('parent') else 0, r['label']),
        ),
    )
    return nav


def merge_in(nav, newnav):
    for product in newnav:
        if 'parent' in product:
            parents = [n for n in nav if n['url'] == product['parent']]
            if parents:
                if 'children' not in parents[0]:
                    parents[0]['children'] = [dict(parents[0])]
                    parents[0]['active'] = False
                parents[0]['children'].append(product)
                continue
        nav.append(product)


def get_admin_navigation(request):
    url = request.resolver_match
    if not url:
        return []
    nav = [
        {
            'label': _('Admin Dashboard'),
            'url': reverse('eventyay_admin:admin.dashboard'),
            'active': 'dashboard' in url.url_name,
            'icon': 'dashboard',
        },
        {
            'label': _('All Events'),
            'url': reverse('eventyay_admin:admin.events'),
            'active': 'events' in url.url_name,
            'icon': 'calendar',
        },
        {
            'label': _('All Organizers'),
            'url': reverse('eventyay_admin:admin.organizers'),
            'active': 'organizers' in url.url_name,
            'icon': 'group',
        },
        {
            'label': _('All Attendees'),
            'url': reverse('eventyay_admin:admin.attendees'),
            'active': 'attendees' in url.url_name,
            'icon': 'ticket',
        },
        {
            'label': _('All Sessions'),
            'url': reverse('eventyay_admin:admin.submissions'),
            'active': 'submissions' in url.url_name,
            'icon': 'sticky-note-o',
        },
        {
            'label': _('Task management'),
            'url': reverse('eventyay_admin:admin.task_management'),
            'active': 'task_management' in url.url_name,
            'icon': 'tasks',
        },
        {
            'label': _('Pages'),
            'url': reverse('eventyay_admin:admin.pages'),
            'active': 'pages' in url.url_name,
            'icon': 'file-text',
        },
        {
            'label': _('Users'),
            'url': reverse('eventyay_admin:admin.users'),
            'active': False,
            'icon': 'user',
            'children': [
                {
                    'label': _('All users'),
                    'url': reverse('eventyay_admin:admin.users'),
                    'active': ('users' in url.url_name),
                },
                {
                    'label': _('Admin sessions'),
                    'url': reverse('eventyay_admin:admin.user.sudo.list'),
                    'active': ('sudo' in url.url_name),
                },
            ],
        },
        {
            'label': _('Vouchers'),
            'url': reverse('eventyay_admin:admin.vouchers'),
            'active': 'vouchers' in url.url_name,
            'icon': 'tags',
        },
        {
            'label': _('Global settings'),
            'url': reverse('eventyay_admin:admin.global.settings'),
            'active': False,
            'icon': 'wrench',
            'children': [
                {
                    'label': _('Settings'),
                    'url': reverse('eventyay_admin:admin.global.settings'),
                    'active': (url.url_name == 'admin.global.settings'),
                },
                {
                    'label': _('Update check'),
                    'url': reverse('eventyay_admin:admin.global.update'),
                    'active': (url.url_name == 'admin.global.update'),
                },
                {
                    'label': _('Generate keys for SSO'),
                    'url': reverse('eventyay_admin:admin.global.sso'),
                    'active': (url.url_name == 'admin.global.sso'),
                },
                {
                    'label': _('Social login settings'),
                    'url': reverse('plugins:socialauth:admin.global.social.auth.settings'),
                    'active': (url.url_name == 'admin.global.social.auth.settings'),
                },
            ],
        },
        {
            'label': _('System information'),
            'url': reverse('eventyay_admin:admin.config'),
            'active': 'config' in url.url_name,
            'icon': 'cog',
        },
    ]

    # --- Inject Video Admin navigation (now part of admin sidebar) -------------
    if request.user.is_authenticated and request.user.is_staff:
        path = request.path.rstrip('/')
        video_root = '/admin/video'
        def is_active(prefix, exact=False):
            if exact:
                return path == prefix.rstrip('/')
            return path == prefix.rstrip('/') or path.startswith(prefix.rstrip('/') + '/')
        video_children = [
            {
                'label': _('Dashboard'),
                'url': reverse('eventyay_admin:video_admin:index'),
                'active': is_active('/admin/video', exact=True),
            },
            {
                'label': _('Events'),
                'url': reverse('eventyay_admin:video_admin:event.list'),
                'active': is_active('/admin/video/events'),
            },
            {
                'label': _('BBB servers'),
                'url': reverse('eventyay_admin:video_admin:bbbserver.list'),
                'active': is_active('/admin/video/bbbs') and 'moveroom' not in path,
            },
            {
                'label': _('Move BBB room'),
                'url': reverse('eventyay_admin:video_admin:bbbserver.moveroom'),
                'active': is_active('/admin/video/bbbs/moveroom', exact=True),
            },
            {
                'label': _('Janus servers'),
                'url': reverse('eventyay_admin:video_admin:janusserver.list'),
                'active': is_active('/admin/video/janus'),
            },
            {
                'label': _('TURN servers'),
                'url': reverse('eventyay_admin:video_admin:turnserver.list'),
                'active': is_active('/admin/video/turns'),
            },
            {
                'label': _('Streaming servers'),
                'url': reverse('eventyay_admin:video_admin:streamingserver.list'),
                'active': is_active('/admin/video/streamingservers'),
            },
            {
                'label': _('Streamkey generator'),
                'url': reverse('eventyay_admin:video_admin:streamkey'),
                'active': is_active('/admin/video/streamkey', exact=True),
            },
            {
                'label': _('System log'),
                'url': reverse('eventyay_admin:video_admin:systemlog.list'),
                'active': is_active('/admin/video/systemlog'),
            },
            {
                'label': _('Conftool posters'),
                'url': reverse('eventyay_admin:video_admin:conftool.syncposters'),
                'active': is_active('/admin/video/conftool/syncposters', exact=True),
            },
            
            # {
            #     'label': _('Users'),
            #     'url': f'{video_root}/users/',
            #     'active': is_active(f'{video_root}/users'),
            # },
        ]
        parent_active = any(c['active'] for c in video_children) or is_active(video_root)
        nav.append(
            {
                'label': _('Video Admin'),
                'url': reverse('eventyay_admin:video_admin:index'),
                'active': parent_active,
                'icon': 'video-camera',
                'children': video_children,
            }
        )
    # --------------------------------------------------------------------------

    merge_in(
        nav,
        sorted(
            sum((list(a[1]) for a in nav_global.send(request, request=request)), []),
            key=lambda r: (1 if r.get('parent') else 0, r['label']),
        ),
    )
    return nav

import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import (
    Count,
    Exists,
    IntegerField,
    Max,
    Min,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Sum,
)
from django.db.models.functions import Coalesce, Greatest
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils.formats import date_format
from django.utils.html import escape, format_html
from django.utils.timezone import now
from django.utils.translation import gettext, ngettext
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from django_scopes import scope


from eventyay.base.decimal import round_decimal
from eventyay.base.models import (
    Event,
    Order,
    OrderPosition,
    OrderRefund,
    Product,
    ProductCategory,
    Question,
    Quota,
    RequiredAction,
    SpeakerProfile,
    SubEvent,
    Submission,
    SubmissionStates,
    User,
    Voucher,
)
from eventyay.base.meetup import is_meetup_event
from eventyay.base.timeline import timeline_for_event
from eventyay.control.forms.event import CommentForm
from eventyay.control.signals import (
    event_dashboard_widgets,
    user_dashboard_widgets,
)
from eventyay.plugins.statistics.views import get_statistics_context
from eventyay.helpers.daterange import daterange
from eventyay.helpers.plugin_enable import is_video_enabled
from eventyay.multidomain.urlreverse import eventreverse

from .meetup import get_meetup_analytics_context

from ...base.models.orders import CancellationRequest
from ..onboarding import build_onboarding_context, build_organiser_dashboard_context, user_needs_onboarding
from ..permissions import (
    filter_timeline_entry_for_ticket_access,
    get_cached_event_dashboard_access,
    user_has_talk_dashboard_access,
    user_has_ticket_dashboard_access,
    user_has_video_dashboard_access,
)
from ..utils import EventCreatedFor, get_subevent

logger = logging.getLogger(__name__)

OVERVIEW_BANLIST = ['eventyay.plugins.sendmail.order.email.sent']

SHOP_STATE_WIDGET_KEY = 'shop_state'
# Widget producers that should remain visible to talk-only users must set
# ``key='shop_state'`` on their dashboard widget payload (see shop_state_widget).
EVENT_SETTINGS_PERMISSION_DIALOG_ID = 'event-settings-permission-dialog'
TICKET_PERMISSION_DIALOG_ID = 'ticket-permission-dialog'
TALK_PERMISSION_DIALOG_ID = 'talk-permission-dialog'
VIDEO_PERMISSION_DIALOG_ID = 'video-permission-dialog'


def _sanitize_widget_content_for_permission_dialog(content: str) -> str:
    """Return widget HTML safe to show inside a permission-dialog trigger."""
    if not content:
        return content
    soup = BeautifulSoup(content, 'html.parser')
    for a in soup.find_all('a'):
        a.unwrap()
    return str(soup).replace(gettext('Click here to change'), '')


def get_event_dashboard_widget_permissions(request: HttpRequest) -> dict[str, bool]:
    access = get_cached_event_dashboard_access(
        request, request.user, request.organizer, request.event
    )
    return {
        'has_ticket_dashboard_access': access['has_ticket_access'],
        'can_change_event_settings': access['can_change_event_settings'],
        'can_view_orders': access['can_view_orders'],
    }


def filter_event_dashboard_widgets_for_request(
    request: HttpRequest,  # kept for backward compatibility at call sites
    widgets: List[Dict[str, Any]] | None,
    permissions: dict[str, bool] | None = None,
) -> List[Dict[str, Any]]:
    if permissions is None:
        permissions = get_event_dashboard_widget_permissions(request)
    return filter_common_event_dashboard_widgets(
        widgets,
        has_ticket_dashboard_access=permissions['has_ticket_dashboard_access'],
        can_change_event_settings=permissions['can_change_event_settings'],
        can_view_orders=permissions.get('can_view_orders', False),
    )


# Widget ``lazy`` keys whose data comes from orders (attendees, revenue, etc.).
# These require ``can_view_orders`` even for users who have general ticket access.
_ORDER_DATA_WIDGET_LAZY_KEYS = (
    'attendees-ordered',
    'attendees-paid',
    'total-revenue',
)
_ORDER_DATA_WIDGET_LAZY_PREFIXES = (
    'waitinglist-',
    'checkin-',
)


def _is_order_data_widget(widget: Dict[str, Any]) -> bool:
    """Return True when a widget displays order-level data (attendees, revenue, etc.)."""
    lazy_key = widget.get('lazy', '')
    if lazy_key in _ORDER_DATA_WIDGET_LAZY_KEYS:
        return True
    return any(lazy_key.startswith(prefix) for prefix in _ORDER_DATA_WIDGET_LAZY_PREFIXES)


def filter_common_event_dashboard_widgets(
    widgets: List[Dict[str, Any]] | None,
    *,
    has_ticket_dashboard_access: bool,
    can_change_event_settings: bool,
    can_view_orders: bool = False,
) -> List[Dict[str, Any]]:
    """Limit dashboard widgets on the common event home for talk-only users.

    Users without ticket dashboard access only see widgets whose ``key`` is
    ``shop_state`` (ticket shop live status). Other widgets are omitted unless
    they declare that key or the user gains ticket dashboard access.

    Additionally, widgets that expose order data (attendee counts, revenue,
    waiting-list lengths, check-in stats) are suppressed for users who have
    generic ticket access (e.g. ``can_change_items``) but lack the specific
    ``can_view_orders`` permission.
    """
    if widgets is None:
        widgets = []
    elif isinstance(widgets, dict):
        widgets = [widgets]
    elif not isinstance(widgets, (list, tuple)):
        logger.warning(
            'Expected list of dashboard widgets, got %s',
            type(widgets).__name__,
        )
        widgets = []
    filtered: List[Dict[str, Any]] = []
    for widget in widgets:
        if not isinstance(widget, dict):
            continue
        widget = dict(widget)
        if not has_ticket_dashboard_access and widget.get('key') != SHOP_STATE_WIDGET_KEY:
            continue
        if widget.get('key') == SHOP_STATE_WIDGET_KEY and not can_change_event_settings:
            widget.pop('url', None)
            widget.pop('link', None)
            widget['content'] = _sanitize_widget_content_for_permission_dialog(widget.get('content', ''))
            widget['permission_dialog_id'] = EVENT_SETTINGS_PERMISSION_DIALOG_ID
        # Suppress order-data widgets (attendees, revenue, etc.) for users
        # who have ticket dashboard access but not can_view_orders.
        if not can_view_orders and _is_order_data_widget(widget):
            continue
        filtered.append(widget)
    return filtered


def event_index_widgets_lazy(request: HttpRequest, **kwargs) -> JsonResponse:
    subevent = get_subevent(request)
    permissions = get_event_dashboard_widget_permissions(request)

    widgets: List[Dict[str, Any]] = []
    for r, result in event_dashboard_widgets.send(
        sender=request.event,
        subevent=subevent,
        lazy=False,
        request=request,
    ):
        widgets.extend(filter_event_dashboard_widgets_for_request(request, result, permissions))

    return JsonResponse({'widgets': widgets})


def classify_log_category(log) -> str:
    """Classify log entry into standard category badge."""
    if not log.content_type:
        return 'System'
    model = log.content_type.model.lower()
    if model in ('order', 'orderposition', 'orderrefund', 'cancellationrequest'):
        return 'Order'
    elif model in ('submission', 'talk'):
        return 'Talk'
    elif model in ('speakerprofile', 'speaker'):
        return 'Speaker'
    elif model in ('product', 'productvariation', 'productcategory', 'quota'):
        return 'Product'
    elif model in ('checkin', 'checkinlist'):
        return 'Check-in'
    elif model in ('event', 'eventsettings'):
        return 'Settings'
    elif 'video' in model or 'stage' in model:
        return 'Video'
    return model.capitalize()


class EventIndexView(TemplateView):
    """
    A class-based view for rendering the event index dashboard.
    """

    template_name = 'eventyay_common/event/index.html'

    def get_template_names(self):
        if is_meetup_event(self.request.event):
            return ['eventyay_common/event/meetup_dashboard.html']
        return [self.template_name]

    def render_to_response(self, context, **response_kwargs):
        resp = super().render_to_response(context, **response_kwargs)
        if context.get('can_view_orders') and context.get('stats_has_orders'):
            resp['Content-Security-Policy'] = "script-src 'unsafe-eval'; style-src 'unsafe-inline'"
            resp._csp_update = {'script-src': ["'unsafe-eval'"], 'style-src': ["'unsafe-inline'"]}
        return resp

    @staticmethod
    def rearrange(widgets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort widget boxes according to priority.
        """
        mapping = {
            'small': 1,
            'big': 2,
            'full': 3,
        }

        def sort_key(element: Dict[str, Any]) -> tuple:
            return (
                element.get('priority', 1),
                mapping.get(element.get('display_size', 'small'), 1),
            )

        return sorted(widgets, key=sort_key, reverse=True)

    def _get_user_permissions(self) -> Dict[str, bool]:
        """
        Centralize permission checks for the event.
        """
        request = self.request
        return {
            'can_view_orders': request.user.has_event_permission(
                request.organizer, request.event, 'can_view_orders', request=request
            ),
            'can_change_orders': request.user.has_event_permission(
                request.organizer, request.event, 'can_change_orders', request=request
            ),
            'can_change_event_settings': request.user.has_event_permission(
                request.organizer,
                request.event,
                'can_change_event_settings',
                request=request,
            ),
            'can_view_vouchers': request.user.has_event_permission(
                request.organizer, request.event, 'can_view_vouchers', request=request
            ),
            'can_change_items': request.user.has_event_permission(
                request.organizer, request.event, 'can_change_items', request=request
            ),
        }

    def _collect_dashboard_widgets(self, subevent: Optional[SubEvent]) -> List[Dict[str, Any]]:
        """
        Collect and filter dashboard widgets based on permissions.

        Talk-only users see the event live-status widget but not ticket metrics.
        """
        request = self.request
        widget_permissions = get_event_dashboard_widget_permissions(request)
        widgets: List[Dict[str, Any]] = []
        for caller, result in event_dashboard_widgets.send(
            sender=request.event,
            subevent=subevent,
            lazy=True,
            request=request,
        ):
            widgets.extend(
                filter_event_dashboard_widgets_for_request(request, result, widget_permissions)
            )
        return self.rearrange(widgets)

    def _filter_log_entries(self, qs: QuerySet, permissions: Dict[str, bool]) -> QuerySet:
        """
        Apply log entry filtering based on user permissions.

        :param qs: Queryset of log entries
        :param permissions: Dictionary of user permissions
        :return: Filtered queryset
        """
        qs = qs.exclude(action_type__in=OVERVIEW_BANLIST)

        if not permissions['can_view_orders']:
            qs = qs.exclude(content_type=ContentType.objects.get_for_model(Order))

        if not permissions['can_view_vouchers']:
            qs = qs.exclude(content_type=ContentType.objects.get_for_model(Voucher))

        if not permissions['can_change_event_settings']:
            allowed_types = [
                ContentType.objects.get_for_model(Voucher),
                ContentType.objects.get_for_model(Order),
            ]

            if permissions['can_change_items']:
                allowed_types += [
                    ContentType.objects.get_for_model(Product),
                    ContentType.objects.get_for_model(ProductCategory),
                    ContentType.objects.get_for_model(Quota),
                    ContentType.objects.get_for_model(Question),
                ]

            qs = qs.filter(content_type__in=allowed_types)

        return qs

    def _check_event_statuses(self, can_view_orders: bool) -> Dict[str, Any]:
        """
        Centralize various event status checks.
        """
        request = self.request
        return {
            'has_overpaid_orders': can_view_orders
            and Order.annotate_overpayments(request.event.orders)
            .filter(
                Q(~Q(status=Order.STATUS_CANCELED) & Q(pending_sum_t__lt=0))
                | Q(Q(status=Order.STATUS_CANCELED) & Q(pending_sum_rc__lt=0))
            )
            .exists(),
            'has_pending_orders_with_full_payment': can_view_orders
            and Order.annotate_overpayments(request.event.orders)
            .filter(
                Q(status__in=(Order.STATUS_EXPIRED, Order.STATUS_PENDING))
                & Q(pending_sum_t__lte=0)
                & Q(require_approval=False)
            )
            .exists(),
            'has_pending_refunds': can_view_orders
            and OrderRefund.objects.filter(
                order__event=request.event,
                state__in=(
                    OrderRefund.REFUND_STATE_CREATED,
                    OrderRefund.REFUND_STATE_EXTERNAL,
                ),
            ).exists(),
            'has_pending_approvals': can_view_orders
            and request.event.orders.filter(status=Order.STATUS_PENDING, require_approval=True).exists(),
            'has_cancellation_requests': can_view_orders
            and CancellationRequest.objects.filter(order__event=request.event).exists(),
        }

    def _get_header_data(self, event: Event, request: HttpRequest) -> Dict[str, Any]:
        """Generate event header and status badges."""
        if not event.live:
            event_status_label = _('Draft')
            event_status_class = 'draft'
        elif event.date_to and event.date_to < now():
            event_status_label = _('Past')
            event_status_class = 'past'
        else:
            event_status_label = _('Live')
            event_status_class = 'live'

        ticket_shop_status = event.ticket_component_presale_status
        public_url = eventreverse(event, 'presale:event.index')
        try:
            full_public_url = request.build_absolute_uri(public_url)
        except (NoReverseMatch, AttributeError, ValueError):
            full_public_url = public_url

        return {
            'event_status': event_status_label,
            'event_status_class': event_status_class,
            'is_testmode': bool(event.testmode),
            'is_private_testmode': bool(event.private_testmode),
            'ticket_shop_status': ticket_shop_status,
            'timezone': event.cache.get_or_set('timezone', lambda e=event: e.settings.timezone),
            'public_url': full_public_url,
            'date_range': event.get_date_range_display(),
        }

    def _get_workflow_timeline(self, event: Event, permissions: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate 6-step event lifecycle workflow timeline."""
        has_products = event.products.exists()
        setup_done = has_products and (event.live or bool(event.settings.get('payment_providers', None)))
        setup_url = (
            reverse('eventyay_common:event.update', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
            if permissions.get('can_change_event_settings')
            else None
        )

        shop_status = event.ticket_component_presale_status
        is_shop_public = bool(
            event.live
            and event.tickets_published
            and not event.testmode
            and not event.private_testmode_tickets_enabled
        )
        is_shop_testmode = bool(event.testmode or event.private_testmode_tickets_enabled)
        ticketing_url = (
            reverse('control:event.index', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
            if permissions.get('has_ticket_access')
            else None
        )

        has_cfp = hasattr(event, 'cfp') and bool(event.cfp)
        cfp_open = bool(has_cfp and event.cfp.is_open)
        cfp_closed = bool(has_cfp and event.cfp.max_deadline and now() > event.cfp.max_deadline)
        cfp_url = None
        if permissions.get('has_talk_access'):
            try:
                cfp_url = reverse('orga:cfp.overview', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
            except NoReverseMatch:
                pass

        current_sched = getattr(event, 'current_schedule', None)
        wip_sched = event.schedules.filter(version__isnull=True).first() if hasattr(event, 'schedules') else None
        has_scheduled_talks = bool(
            (wip_sched and wip_sched.talks.filter(start__isnull=False).exists())
            or (current_sched and current_sched.talks.filter(start__isnull=False).exists())
        )
        schedule_url = None
        if permissions.get('has_talk_access'):
            try:
                schedule_url = reverse('orga:schedule.main', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
            except NoReverseMatch:
                pass

        is_event_past = bool(event.date_to and now() > event.date_to)
        is_event_live = bool(event.date_from and event.date_to and event.date_from <= now() <= event.date_to)
        video_url = (
            reverse('eventyay_common:event.create_access_to_video', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
            if permissions.get('has_video_access')
            else None
        )

        wrapup_active = is_event_past

        if is_shop_public:
            ticketing_phase = 'current'
            ticketing_status = _('Live')
        elif is_shop_testmode:
            ticketing_phase = 'current'
            ticketing_status = _('In test mode')
        elif has_products:
            ticketing_phase = 'done'
            ticketing_status = _('Configured')
        else:
            ticketing_phase = 'todo'
            ticketing_status = _('Upcoming')

        return [
            {
                'name': _('Setup'),
                'icon': 'cogs',
                'phase': 'done' if setup_done else 'current',
                'status_text': _('Completed') if setup_done else _('In progress'),
                'summary': _('Configured') if setup_done else _('Setup required'),
                'url': setup_url,
            },
            {
                'name': _('Ticketing'),
                'icon': 'ticket',
                'phase': ticketing_phase,
                'status_text': ticketing_status,
                'summary': shop_status.get('text', ''),
                'url': ticketing_url,
            },
            {
                'name': _('Call for Proposals'),
                'icon': 'bullhorn',
                'phase': 'current' if cfp_open else ('done' if cfp_closed else 'todo'),
                'status_text': _('Open') if cfp_open else (_('Closed') if cfp_closed else _('Upcoming')),
                'summary': event.cfp.max_deadline.strftime('%b %d') if (has_cfp and event.cfp.max_deadline and cfp_open) else '',
                'url': cfp_url,
            },
            {
                'name': _('Schedule'),
                'icon': 'calendar',
                'phase': 'done' if current_sched else ('current' if has_scheduled_talks else 'todo'),
                'status_text': _('Published') if current_sched else (_('In progress') if has_scheduled_talks else _('Upcoming')),
                'summary': _('Published') if current_sched else (_('Draft') if has_scheduled_talks else ''),
                'url': schedule_url,
            },
            {
                'name': _('Live Event'),
                'icon': 'video-camera',
                'phase': 'done' if is_event_past else ('current' if is_event_live else 'todo'),
                'status_text': _('Completed') if is_event_past else (_('Live now') if is_event_live else _('Upcoming')),
                'summary': _('Active') if is_event_live else '',
                'url': video_url,
            },
            {
                'name': _('Wrap-up'),
                'icon': 'flag-checkered',
                'phase': 'current' if wrapup_active else 'todo',
                'status_text': _('In progress') if wrapup_active else _('Upcoming'),
                'summary': _('Reports & review') if wrapup_active else '',
                'url': None,
            },
        ]

    def _get_action_required(self, event: Event, permissions: Dict[str, Any], subevent=None) -> List[Dict[str, Any]]:
        """Collect cross-event actionable alert cards."""
        actions = []
        if permissions.get('can_view_orders'):
            order_qs = event.orders.all()
            if subevent:
                order_qs = order_qs.filter(all_positions__subevent=subevent).distinct()

            pending_approvals = order_qs.filter(status=Order.STATUS_PENDING, require_approval=True).count()
            if pending_approvals > 0:
                approval_url = (
                    reverse('control:event.orders', kwargs={'event': event.slug, 'organizer': event.organizer.slug})
                    + '?status=pa'
                )
                if subevent:
                    approval_url += f'&subevent={subevent.id}'
                actions.append({
                    'id': 'orders-approval',
                    'icon': 'clock-o',
                    'title': _('Orders need approval'),
                    'count': pending_approvals,
                    'desc': ngettext(
                        '%(count)d order needs review and approval.',
                        '%(count)d orders need review and approval.',
                        pending_approvals,
                    ) % {'count': pending_approvals},
                    'severity': 'danger',
                    'btn_text': _('Review orders'),
                    'url': approval_url,
                })

            overpaid_orders = Order.annotate_overpayments(order_qs).filter(
                Q(~Q(status=Order.STATUS_CANCELED) & Q(pending_sum_t__lt=0))
                | Q(Q(status=Order.STATUS_CANCELED) & Q(pending_sum_rc__lt=0))
            ).count()
            if overpaid_orders > 0:
                overpaid_url = (
                    reverse('control:event.orders', kwargs={'event': event.slug, 'organizer': event.organizer.slug})
                    + '?status=overpaid'
                )
                if subevent:
                    overpaid_url += f'&subevent={subevent.id}'
                actions.append({
                    'id': 'overpaid-orders',
                    'icon': 'money',
                    'title': _('Overpaid orders'),
                    'count': overpaid_orders,
                    'desc': ngettext(
                        '%(count)d overpaid order. Consider refunding extra amount.',
                        '%(count)d overpaid orders. Consider refunding extra amount.',
                        overpaid_orders,
                    ) % {'count': overpaid_orders},
                    'severity': 'warning',
                    'btn_text': _('View overpaid orders'),
                    'url': overpaid_url,
                })

        if permissions.get('can_change_event_settings') and not event.products.exists():
            actions.append({
                'id': 'setup-products',
                'icon': 'wrench',
                'title': _('Setup tasks remaining'),
                'count': 1,
                'desc': _('No ticket products configured yet. Set up ticketing to start sales.'),
                'severity': 'info',
                'btn_text': _('Go to setup'),
                'url': reverse('control:event.quick', kwargs={'event': event.slug, 'organizer': event.organizer.slug}),
            })

        if permissions.get('has_talk_access'):
            wip_schedule = event.schedules.filter(version__isnull=True).first() if hasattr(event, 'schedules') else None
            if wip_schedule:
                unscheduled = wip_schedule.talks.filter(
                    Q(start__isnull=True) | Q(room__isnull=True),
                    is_visible=True,
                    submission__state=SubmissionStates.CONFIRMED,
                ).count()
                if unscheduled > 0:
                    actions.append({
                        'id': 'unscheduled-sessions',
                        'icon': 'calendar-times-o',
                        'title': _('Unscheduled sessions'),
                        'count': unscheduled,
                        'desc': ngettext(
                            '%(count)d confirmed session is not yet scheduled to a slot.',
                            '%(count)d confirmed sessions are not yet scheduled to a slot.',
                            unscheduled,
                        ) % {'count': unscheduled},
                        'severity': 'warning',
                        'btn_text': _('Open schedule'),
                        'url': reverse(
                            'orga:schedule.main',
                            kwargs={'organizer': event.organizer.slug, 'event': event.slug},
                        ),
                    })

            confirmed_speakers_qs = User.objects.filter(
                submissions__event=event,
                submissions__state=SubmissionStates.CONFIRMED,
            ).distinct()
            incomplete_speakers = SpeakerProfile.objects.filter(
                Q(event=event, user__in=confirmed_speakers_qs)
                & (Q(biography__isnull=True) | Q(biography='') | Q(user__avatar__isnull=True) | Q(user__avatar=''))
            ).distinct().count()
            if incomplete_speakers > 0:
                actions.append({
                    'id': 'incomplete-speakers',
                    'icon': 'user-times',
                    'title': _('Incomplete speaker profiles'),
                    'count': incomplete_speakers,
                    'desc': ngettext(
                        '%(count)d speaker is missing bio or photo.',
                        '%(count)d speakers are missing bio or photo.',
                        incomplete_speakers,
                    ) % {'count': incomplete_speakers},
                    'severity': 'caution',
                    'btn_text': _('Review speakers'),
                    'url': reverse(
                        'orga:speakers.list',
                        kwargs={'event': event.slug, 'organizer': event.organizer.slug},
                    ),
                })

        if permissions.get('has_video_access') and not is_video_enabled(event):
            actions.append({
                'id': 'video-configuration',
                'icon': 'video-camera',
                'title': _('Video room configuration'),
                'count': 1,
                'desc': _('Video streaming and room settings need configuration.'),
                'severity': 'info',
                'btn_text': _('Open video settings'),
                'url': reverse('eventyay_common:event.create_access_to_video', kwargs={'event': event.slug, 'organizer': event.organizer.slug}),
            })

        return actions

    def _get_shared_order_metrics(
        self, event: Event, subevent: Optional[SubEvent], can_view_orders: bool
    ) -> Dict[str, Any]:
        """Compute shared paid order aggregates once per request to avoid redundant queries."""
        if not can_view_orders:
            return {
                'paid_orders_count': 0,
                'revenue_sum': Decimal('0.00'),
            }

        paid_positions = OrderPosition.objects.filter(
            order__event=event,
            order__status=Order.STATUS_PAID,
        )
        if subevent:
            paid_positions = paid_positions.filter(subevent=subevent)

        metrics = paid_positions.aggregate(
            rev_sum=Sum('price'),
            order_count=Count('order_id', distinct=True),
        )
        return {
            'paid_orders_count': metrics['order_count'] or 0,
            'revenue_sum': metrics['rev_sum'] or Decimal('0.00'),
        }

    def _get_at_a_glance_kpis(
        self,
        event: Event,
        permissions: Dict[str, Any],
        subevent=None,
        header_data: Optional[Dict[str, Any]] = None,
        shared_order_metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Aggregate high-level cross-event KPIs."""
        can_view_orders = permissions.get('can_view_orders', False)
        has_talk = permissions.get('has_talk_access', False)

        if can_view_orders:
            opqs = OrderPosition.objects.filter(
                order__event=event,
                product__admission=True,
            )
            if subevent:
                opqs = opqs.filter(subevent=subevent)
            attendees_ordered = opqs.filter(
                order__status__in=(Order.STATUS_PAID, Order.STATUS_PENDING)
            ).count()
            attendees_paid = opqs.filter(
                order__status=Order.STATUS_PAID
            ).count()
            if shared_order_metrics is not None:
                revenue_sum = shared_order_metrics['revenue_sum']
            else:
                rev_qs = OrderPosition.objects.filter(
                    order__event=event,
                    order__status=Order.STATUS_PAID
                )
                if subevent:
                    rev_qs = rev_qs.filter(subevent=subevent)
                revenue_sum = rev_qs.aggregate(sum=Sum('price'))['sum'] or Decimal('0.00')
        else:
            attendees_ordered = 0
            attendees_paid = 0
            revenue_sum = Decimal('0.00')

        if has_talk:
            sessions_confirmed = event.submissions.filter(state=SubmissionStates.CONFIRMED).count()
            speakers_confirmed = User.objects.filter(
                submissions__event=event,
                submissions__state=SubmissionStates.CONFIRMED,
            ).distinct().count()
        else:
            sessions_confirmed = 0
            speakers_confirmed = 0

        if header_data:
            event_status_text = header_data.get('event_status', _('Draft'))
            event_status_class = header_data.get('event_status_class', 'draft')
        elif not event.live:
            event_status_text = _('Draft')
            event_status_class = 'draft'
        elif event.date_to and event.date_to < now():
            event_status_text = _('Past')
            event_status_class = 'past'
        else:
            event_status_text = _('Live')
            event_status_class = 'live'

        return {
            'event_status_text': event_status_text,
            'event_status_class': event_status_class,
            'attendees_ordered': attendees_ordered,
            'attendees_paid': attendees_paid,
            'sessions_confirmed': sessions_confirmed,
            'speakers_confirmed': speakers_confirmed,
            'revenue_sum': revenue_sum,
            'currency': event.currency,
        }

    def _get_component_cards(
        self,
        event: Event,
        permissions: Dict[str, Any],
        subevent=None,
        shared_order_metrics: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Generate status cards for tickets, talks, video, and active plugins."""
        cards = []
        plugins = event.get_plugins()

        # 1. Tickets Card
        if permissions.get('has_ticket_access'):
            shop_status = event.ticket_component_presale_status
            opqs = OrderPosition.objects.filter(order__event=event, product__admission=True)
            if subevent:
                opqs = opqs.filter(subevent=subevent)
            ordered_c = opqs.filter(order__status__in=(Order.STATUS_PAID, Order.STATUS_PENDING)).count() if permissions.get('can_view_orders') else 0
            paid_c = opqs.filter(order__status=Order.STATUS_PAID).count() if permissions.get('can_view_orders') else 0

            order_qs = event.orders.all()
            if subevent:
                order_qs = order_qs.filter(all_positions__subevent=subevent).distinct()
            pending_appr = order_qs.filter(status=Order.STATUS_PENDING, require_approval=True).count() if permissions.get('can_view_orders') else 0

            if permissions.get('can_view_orders'):
                if shared_order_metrics is not None:
                    rev_sum = shared_order_metrics['revenue_sum']
                else:
                    rev_qs = OrderPosition.objects.filter(order__event=event, order__status=Order.STATUS_PAID)
                    if subevent:
                        rev_qs = rev_qs.filter(subevent=subevent)
                    rev_sum = rev_qs.aggregate(sum=Sum('price'))['sum'] or Decimal('0.00')
            else:
                rev_sum = Decimal('0.00')

            cards.append({
                'id': 'tickets',
                'name': _('Tickets'),
                'icon': 'ticket',
                'status': shop_status.get('text', _('Active')),
                'status_class': shop_status.get('class', 'live'),
                'metrics': [
                    {'label': _('Ordered attendees'), 'value': ordered_c},
                    {'label': _('Paid attendees'), 'value': paid_c},
                    {'label': _('Awaiting approval'), 'value': pending_appr},
                    {'label': _('Revenue'), 'value': f'{event.currency} {rev_sum:,.2f}' if permissions.get('can_view_orders') else '-'},
                ],
                'btn_text': _('Open tickets dashboard'),
                'url': reverse('control:event.index', kwargs={'event': event.slug, 'organizer': event.organizer.slug}),
                'enabled': True,
            })

        # 2. Talks & Speakers Card
        if permissions.get('has_talk_access'):
            total_proposals = event.submissions.count()
            accepted_c = event.submissions.filter(state__in=[SubmissionStates.ACCEPTED, SubmissionStates.CONFIRMED]).count()
            acc_rate = round((accepted_c / total_proposals) * 100, 1) if total_proposals else 0
            talk_status = _('CfP Open') if (hasattr(event, 'cfp') and event.cfp and event.cfp.is_open) else (_('Active') if total_proposals else _('Setup'))
            confirmed_speakers_count = User.objects.filter(
                submissions__event=event,
                submissions__state=SubmissionStates.CONFIRMED,
            ).distinct().count()

            cards.append({
                'id': 'talks',
                'name': _('Talks & Speakers'),
                'icon': 'bullhorn',
                'status': talk_status,
                'status_class': 'live' if (hasattr(event, 'cfp') and event.cfp and event.cfp.is_open) else 'info',
                'metrics': [
                    {'label': _('Sessions'), 'value': accepted_c},
                    {'label': _('Speakers'), 'value': confirmed_speakers_count},
                    {'label': _('Proposals'), 'value': total_proposals},
                    {'label': _('Acceptance rate'), 'value': f'{acc_rate}%'},
                ],
                'btn_text': _('Open talks dashboard'),
                'url': reverse('orga:event.dashboard', kwargs={'event': event.slug, 'organizer': event.organizer.slug}),
                'enabled': True,
            })

        # 3. Video Card
        if permissions.get('has_video_access'):
            video_active = is_video_enabled(event)
            cards.append({
                'id': 'video',
                'name': _('Video'),
                'icon': 'video-camera',
                'status': _('Configured') if video_active else _('Not configured'),
                'status_class': 'live' if video_active else 'off',
                'metrics': [
                    {'label': _('Status'), 'value': _('Configured') if video_active else _('Inactive')},
                ] if video_active else [],
                'empty_state': _('No video rooms configured yet.') if not video_active else None,
                'btn_text': _('Open video dashboard'),
                'url': reverse('eventyay_common:event.create_access_to_video', kwargs={'event': event.slug, 'organizer': event.organizer.slug}),
                'enabled': True,
            })

        # 4. Social Media Card
        has_social = 'socialmedia' in plugins
        can_access_social = permissions.get('can_change_event_settings', False)
        social_url = None
        if has_social and can_access_social:
            try:
                social_url = reverse(
                    'plugins:socialmedia:index',
                    kwargs={'event': event.slug, 'organizer': event.organizer.slug},
                )
            except NoReverseMatch:
                social_url = None

        cards.append({
            'id': 'socialmedia',
            'name': _('Social Media'),
            'icon': 'share-alt',
            'status': _('Active') if has_social else _('Not configured'),
            'status_class': 'live' if has_social else 'off',
            'metrics': [],
            'empty_state': _('No social posts scheduled yet.') if has_social else _('Plugin not enabled'),
            'btn_text': _('Open social dashboard') if social_url else None,
            'url': social_url,
            'enabled': has_social and can_access_social,
        })

        # 5. TeamShifts Card
        has_teamshifts = 'teamshifts' in plugins
        can_access_teamshifts = (
            self.request.user.has_organizer_permission(event.organizer, 'can_change_teams', request=self.request)
            or self.request.user.has_organizer_permission(
                event.organizer, 'can_change_organizer_settings', request=self.request
            )
        )
        teamshifts_url = None
        if has_teamshifts and can_access_teamshifts:
            try:
                teamshifts_url = reverse(
                    'plugins:teamshifts:organizer_dashboard',
                    kwargs={'organizer': event.organizer.slug},
                )
            except NoReverseMatch:
                teamshifts_url = None

        cards.append({
            'id': 'teamshifts',
            'name': _('TeamShifts'),
            'icon': 'users',
            'status': _('Active') if has_teamshifts else _('Not configured'),
            'status_class': 'live' if has_teamshifts else 'off',
            'metrics': [],
            'empty_state': _('No TeamShifts configured yet.') if has_teamshifts else _('Plugin not enabled'),
            'btn_text': _('Open TeamShifts dashboard') if teamshifts_url else None,
            'url': teamshifts_url,
            'enabled': has_teamshifts and can_access_teamshifts,
        })

        # 6. Exhibitors & Sponsors Card
        has_exhibition = 'exhibition' in plugins
        can_access_exhibition = (
            permissions.get('can_change_event_settings', False)
            or permissions.get('can_change_items', False)
        )
        exhibition_url = None
        if has_exhibition and can_access_exhibition:
            try:
                exhibition_url = reverse(
                    'plugins:exhibition:index',
                    kwargs={'event': event.slug, 'organizer': event.organizer.slug},
                )
            except NoReverseMatch:
                exhibition_url = None

        cards.append({
            'id': 'exhibition',
            'name': _('Exhibitors & Sponsors'),
            'icon': 'handshake-o',
            'status': _('Active') if has_exhibition else _('Not configured'),
            'status_class': 'live' if has_exhibition else 'off',
            'metrics': [],
            'empty_state': _('No exhibitors configured yet.') if has_exhibition else _('Plugin not enabled'),
            'btn_text': _('Open exhibitors dashboard') if exhibition_url else None,
            'url': exhibition_url,
            'enabled': has_exhibition and can_access_exhibition,
        })

        return cards

    def _get_upcoming_milestones(self, event: Event) -> List[Dict[str, Any]]:
        """Collect upcoming and completed milestones."""
        milestones = []
        if hasattr(event, 'cfp') and event.cfp and event.cfp.max_deadline:
            milestones.append({
                'title': _('Call for Proposals closes'),
                'date': event.cfp.max_deadline,
            })
        if event.date_from:
            milestones.append({
                'title': _('Event starts'),
                'date': event.date_from,
            })
        if event.date_to and event.date_to != event.date_from:
            milestones.append({
                'title': _('Event ends'),
                'date': event.date_to,
            })
            milestones.append({
                'title': _('Event wrap-up & reports'),
                'date': event.date_to + timedelta(days=14),
            })

        milestones.sort(key=lambda m: m['date'])
        now_dt = now()
        for m in milestones:
            m['is_past'] = m['date'] < now_dt

        first_future_found = False
        for m in milestones:
            if not m['is_past']:
                if not first_future_found:
                    m['is_current'] = True
                    first_future_found = True
                else:
                    m['is_current'] = False
            else:
                m['is_current'] = False
        return milestones

    def _get_milestones_schedule_url(self, event: Event, permissions: Dict[str, Any]) -> Optional[str]:
        """Return schedule URL for milestones card if user has talk permissions."""
        if permissions.get('has_talk_access'):
            try:
                return reverse('orga:schedule.main', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
            except NoReverseMatch:
                return None
        return None

    def _get_organiser_teams(self, event: Event) -> Dict[str, Any]:
        """Collect organiser name and assigned teams."""
        can_manage_teams = self.request.user.has_organizer_permission(
            event.organizer, 'can_change_teams', request=self.request
        )
        can_change_organizer_settings = self.request.user.has_organizer_permission(
            event.organizer, 'can_change_organizer_settings', request=self.request
        )
        manage_url = None
        if can_manage_teams and can_change_organizer_settings:
            try:
                manage_url = (
                    reverse('eventyay_common:organizer.teams', kwargs={'organizer': event.organizer.slug})
                    + '?section=permissions'
                )
            except NoReverseMatch:
                manage_url = None

        return {
            'organizer_name': event.organizer.name,
            'teams': list(event.teams.values('id', 'name')),
            'manage_url': manage_url,
        }

    def _get_analytics_overview(
        self,
        event: Event,
        permissions: Dict[str, Any],
        subevent: Optional[SubEvent] = None,
        shared_order_metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Aggregate cross-event analytics metrics."""
        can_view_orders = permissions.get('can_view_orders', False)
        has_talk = permissions.get('has_talk_access', False)

        if can_view_orders and shared_order_metrics is not None:
            order_count = shared_order_metrics['paid_orders_count']
            revenue_total = shared_order_metrics['revenue_sum']
        elif can_view_orders:
            order_metrics = self._get_shared_order_metrics(event, subevent, can_view_orders)
            order_count = order_metrics['paid_orders_count']
            revenue_total = order_metrics['revenue_sum']
        else:
            order_count = 0
            revenue_total = Decimal('0.00')

        proposal_stats = {}
        if has_talk:
            proposal_stats = {
                'submitted': event.submissions.count(),
                'accepted': event.submissions.filter(state=SubmissionStates.ACCEPTED).count(),
                'confirmed': event.submissions.filter(state=SubmissionStates.CONFIRMED).count(),
                'rejected': event.submissions.filter(state=SubmissionStates.REJECTED).count(),
            }

        stats_url = None
        if can_view_orders:
            stats_url = reverse(
                'control:event.orders',
                kwargs={'event': event.slug, 'organizer': event.organizer.slug},
            )
            if subevent:
                stats_url += f'?subevent={subevent.id}'

        return {
            'order_count': order_count,
            'revenue_total': revenue_total,
            'currency': event.currency,
            'proposal_stats': proposal_stats,
            'stats_url': stats_url,
        }

    def _get_recent_activity(self, event: Event, permissions: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect recent cross-event activity."""
        qs = (
            event.logentry_set.all()
            .select_related('user', 'content_type', 'api_token', 'oauth_application', 'device')
            .order_by('-datetime')
        )
        qs = self._filter_log_entries(qs, permissions)
        entries = []
        for log in qs[:8]:
            entries.append({
                'datetime': log.datetime,
                'actor': str(log.user) if log.user else (_('System') if not log.api_token else _('API Token')),
                'category': self._classify_log_category(log),
                'display': log.display(self.request),
            })
        return entries

    def _classify_log_category(self, log) -> str:
        """Classify log entry into standard category badge."""
        return classify_log_category(log)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request

        # Get subevent and permissions
        subevent = get_subevent(request)
        permissions = self._get_user_permissions()

        access = get_cached_event_dashboard_access(
            request, request.user, request.organizer, request.event
        )
        permissions['has_ticket_access'] = access['has_ticket_access']
        permissions['has_talk_access'] = access['has_talk_access']
        permissions['has_video_access'] = access['has_video_access']

        # Collect widgets
        widgets = self._collect_dashboard_widgets(subevent)

        # Filter log entries
        qs = (
            request.event.logentry_set.all()
            .select_related('user', 'content_type', 'api_token', 'oauth_application', 'device')
            .order_by('-datetime')
        )
        qs = self._filter_log_entries(qs, permissions)
        can_view_orders = permissions['can_view_orders']

        # Wrap event queries with scope
        with scope(event=request.event):
            shared_order_metrics = self._get_shared_order_metrics(request.event, subevent, can_view_orders)
            header_data = self._get_header_data(request.event, request)
            workflow_timeline = self._get_workflow_timeline(request.event, permissions)
            action_required = self._get_action_required(request.event, permissions, subevent=subevent)
            at_a_glance = self._get_at_a_glance_kpis(
                request.event,
                permissions,
                subevent=subevent,
                header_data=header_data,
                shared_order_metrics=shared_order_metrics,
            )
            component_cards = self._get_component_cards(
                request.event,
                permissions,
                subevent=subevent,
                shared_order_metrics=shared_order_metrics,
            )
            upcoming_milestones = self._get_upcoming_milestones(request.event)
            milestones_schedule_url = self._get_milestones_schedule_url(request.event, permissions)
            organiser_info = self._get_organiser_teams(request.event)
            analytics_overview = self._get_analytics_overview(
                request.event,
                permissions,
                subevent=subevent,
                shared_order_metrics=shared_order_metrics,
            )
            recent_activity = self._get_recent_activity(request.event, permissions)

        # Prepare context
        context.update(
            {
                'widgets': widgets,
                'logs': qs[:5],
                'subevent': subevent,
                'actions': (
                    request.event.requiredaction_set.filter(done=False)[:5] if permissions['can_change_orders'] else []
                ),
                'comment_form': CommentForm(
                    initial={'comment': request.event.comment},
                    readonly=not permissions['can_change_event_settings'],
                ),
                'has_ticket_access': access['has_ticket_access'],
                'has_talk_access': access['has_talk_access'],
                'has_video_access': access['has_video_access'],
                'is_video_enabled': is_video_enabled(request.event),
                'can_change_event_settings': permissions['can_change_event_settings'],
                'can_view_orders': can_view_orders,
                'header_data': header_data,
                'workflow_timeline': workflow_timeline,
                'action_required': action_required,
                'at_a_glance': at_a_glance,
                'component_cards': component_cards,
                'upcoming_milestones': upcoming_milestones,
                'milestones_schedule_url': milestones_schedule_url,
                'organiser_info': organiser_info,
                'analytics_overview': analytics_overview,
                'recent_activity': recent_activity,
                **self._check_event_statuses(can_view_orders),
            }
        )

        if is_meetup_event(request.event):
            if can_view_orders:
                tz = ZoneInfo(request.event.timezone)
                context.update(get_meetup_analytics_context(request.event, tz=tz))
        elif can_view_orders:
            context.update(get_statistics_context(request, subevent=subevent))

        # Process actions
        for action in context['actions']:
            action.display = action.display(request)

        # Add timeline information
        context['timeline'] = [
            {
                'date': t.datetime.astimezone(ZoneInfo(request.event.timezone)).date(),
                'entry': filter_timeline_entry_for_ticket_access(t, access['has_ticket_access']),
                'time': t.datetime.astimezone(ZoneInfo(request.event.timezone)),
            }
            for t in timeline_for_event(request.event, subevent)
        ]

        context['today'] = now().astimezone(ZoneInfo(request.event.timezone)).date()
        context['nearly_now'] = now().astimezone(ZoneInfo(request.event.timezone)) - timedelta(seconds=20)
        context['organizer_teams'] = request.event.teams.values_list('id', 'name')
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.has_event_permission(
            request.organizer, request.event, 'can_change_event_settings', request=request
        ):
            messages.error(request, _("You do not have permission to change event settings."))
            return redirect(self.get_success_url())

        if 'toggle_video_visibility' in request.POST:
            current_setting = request.event.settings.get('venueless_show_public_link', False)
            new_setting = not current_setting
            request.event.settings.set('venueless_show_public_link', new_setting)

            if new_setting:
                messages.success(request, _("Video link is now visible on public pages."))
            else:
                messages.success(request, _("Video link is now hidden from public pages."))

            return redirect(self.get_success_url())

        return self.get(request, *args, **kwargs)

    def get_success_url(self):
        return reverse(
            'eventyay_common:event.index',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )


class EventWidgetGenerator:
    """
    Generates dashboard widgets for events with advanced formatting and lazy loading.
    """

    @staticmethod
    def get_event_query(qs: QuerySet[Event], nmax: int, lazy: bool = False) -> QuerySet[Event]:
        """
        Prepare event queryset with optimized loading.
        """
        if lazy:
            return qs[:nmax]

        return qs.prefetch_related('_settings_objects', 'organizer___settings_objects').select_related('organizer')[
            :nmax
        ]

    @staticmethod
    def format_event_daterange(event: Event, tz: ZoneInfo) -> str:
        """
        Generate a formatted date range for an event.
        """
        if event.has_subevents:
            return (
                _('No dates')
                if event.min_from is None
                else daterange(
                    event.min_from.astimezone(tz),
                    (event.max_fromto or event.max_to or event.max_from).astimezone(tz),
                )
            )

        if event.date_to:
            return daterange(event.date_from.astimezone(tz), event.date_to.astimezone(tz))

        return date_format(event.date_from.astimezone(tz), 'DATE_FORMAT')

    @staticmethod
    def format_event_times(event: Event, tz: ZoneInfo, request: HttpRequest) -> str:
        """
        Generate a formatted time string for an event.
        """
        if event.has_subevents:
            return _('Event series')

        times = []

        # Add admission time if different from event start
        if event.date_admission and event.date_admission != event.date_from:
            times.append(date_format(event.date_admission.astimezone(tz), 'TIME_FORMAT'))

        # Add event start time
        if event.date_from:
            times.append(date_format(event.date_from.astimezone(tz), 'TIME_FORMAT'))

        formatted_times = ' / '.join(times)

        # Add timezone indicator
        tzname = event.cache.get_or_set('timezone', lambda e=event: e.settings.timezone)
        if tzname != request.timezone and not event.has_subevents:
            formatted_times += f' <span class="fa fa-globe text-muted" data-toggle="tooltip" title="{tzname}"></span>'

        return formatted_times

    @staticmethod
    def generate_video_button(event: Event, request: HttpRequest) -> str:
        """
        Generate a video button based on the user's video permissions.
        The access view will ensure configuration and plugin setup as needed.
        """
        has_video_access = user_has_video_dashboard_access(
            request.user, event.organizer, event, request=request
        )
        if has_video_access:
            url = reverse(
                'eventyay_common:event.create_access_to_video',
                kwargs={'event': event.slug, 'organizer': event.organizer.slug},
            )
            return f'<a href="{url}" class="component">{_("Video")}</a>'

        return format_html(
            '<a href="#" role="button" class="component" aria-haspopup="dialog" '
            'aria-controls="{}" data-dialog-target="#{}" data-toggle="dialog">{}</a>',
            VIDEO_PERMISSION_DIALOG_ID,
            VIDEO_PERMISSION_DIALOG_ID,
            _('Video'),
        )

    @staticmethod
    def generate_talk_button(event: Event, request: HttpRequest) -> str:
        """
        Generate a talk button based on event settings and user permission.
        """
        if event.settings.create_for != EventCreatedFor.BOTH.value and event.settings.talk_schedule_public is None:
            return format_html(
                '<a href="#" data-toggle="modal" data-target="#alert-modal" class="component">{}</a>',
                _('Talks'),
            )

        has_talk_access = user_has_talk_dashboard_access(
            request.user, event.organizer, event, request=request
        )
        if not has_talk_access:
            return format_html(
                '<a href="#" class="component" role="button" aria-haspopup="dialog" '
                'aria-controls="{}" data-dialog-target="#{}" data-toggle="dialog">{}</a>',
                TALK_PERMISSION_DIALOG_ID,
                TALK_PERMISSION_DIALOG_ID,
                _('Talks'),
            )

        talk_url = reverse('orga:event.dashboard', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
        return format_html(
            '<a href="{}" class="component">{}</a>',
            talk_url,
            _('Talks'),
        )

    @staticmethod
    def generate_ticket_button(event: Event, request: HttpRequest) -> str:
        """
        Generate a ticket button based on the user's ticket permissions.

        Users without ticket permissions see a modal trigger instead of a link.
        """
        has_ticket_access = user_has_ticket_dashboard_access(
            request.user, event.organizer, event, request=request
        )
        if has_ticket_access:
            ticket_url = reverse(
                'control:event.index',
                kwargs={'event': event.slug, 'organizer': event.organizer.slug},
            )
            return format_html(
                '<a href="{}" class="component">{}</a>',
                ticket_url,
                _('Tickets'),
            )
        return format_html(
            '<a href="#" role="button" class="component" aria-haspopup="dialog" '
            'aria-controls="{}" data-dialog-target="#{}" data-toggle="dialog">{}</a>',
            TICKET_PERMISSION_DIALOG_ID,
            TICKET_PERMISSION_DIALOG_ID,
            _('Tickets'),
        )

    @classmethod
    def generate_widget(cls, event: Event, request: HttpRequest, lazy: bool = False) -> Dict[str, Any]:
        """
        Generate a complete widget for an event.
        """
        widget_content = ''
        if not lazy:
            tzname = event.cache.get_or_set('timezone', lambda e=event: e.settings.timezone)
            tz = ZoneInfo(tzname)

            widget_template = """
            <a href="{url}" class="event">
                <div class="name">{event}</div>
                <div class="daterange">{daterange}</div>
                <div class="times">{times}</div>
            </a>
            <div class="bottomrow">
                {ticket_button}
                {talk_button}
                {video_button}
            </div>
            """

            widget_content = widget_template.format(
                event=escape(event.name),
                times=cls.format_event_times(event, tz, request),
                daterange=cls.format_event_daterange(event, tz),
                url=reverse(
                    'eventyay_common:event.index',
                    kwargs={
                        'organizer': event.organizer.slug,
                        'event': event.slug,
                    },
                ),
                ticket_button=cls.generate_ticket_button(event, request),
                video_button=cls.generate_video_button(event, request),
                talk_button=cls.generate_talk_button(event, request),
            )

        return {
            'content': widget_content,
            'display_size': 'small',
            'lazy': f'event-{event.pk}',
            'priority': 100,
            'container_class': 'widget-container widget-container-event',
        }


def widgets_for_event_qs(
    request: HttpRequest, qs: QuerySet[Event], nmax: int, lazy: bool = False
) -> List[Dict[str, Any]]:
    """
    Generate event widgets for dashboard display.
    """
    events = EventWidgetGenerator.get_event_query(qs, nmax, lazy)

    return [EventWidgetGenerator.generate_widget(event, request, lazy) for event in events]


def annotated_event_query(request: HttpRequest, lazy: bool = False) -> QuerySet[Event]:
    active_orders = (
        Order.objects.filter(event=OuterRef('pk'), status__in=[Order.STATUS_PENDING, Order.STATUS_PAID])
        .order_by()
        .values('event')
        .annotate(c=Count('*'))
        .values('c')
    )

    required_actions = RequiredAction.objects.filter(event=OuterRef('pk'), done=False)
    qs = request.user.get_events_with_any_permission(request)
    if not lazy:
        qs = qs.annotate(
            order_count=Subquery(active_orders, output_field=IntegerField()),
            has_ra=Exists(required_actions),
        )
    qs = qs.annotate(
        min_from=Min('subevents__date_from'),
        max_from=Max('subevents__date_from'),
        max_to=Max('subevents__date_to'),
        max_fromto=Greatest(Max('subevents__date_to'), Max('subevents__date_from')),
    ).annotate(
        order_to=Coalesce('max_fromto', 'max_to', 'max_from', 'date_to', 'date_from'),
    )
    return qs


def rearrange(widgets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort widget boxes according to priority.
    """
    mapping = {
        'small': 1,
        'big': 2,
        'full': 3,
    }

    def sort_key(element: Dict[str, Any]) -> Tuple[int, int]:
        return (
            element.get('priority', 1),
            mapping.get(element.get('display_size', 'small'), 1),
        )

    return sorted(widgets, key=sort_key, reverse=True)


def eventyay_common_dashboard(request: HttpRequest) -> HttpResponse:
    if user_needs_onboarding(request.user, request):
        ctx = build_onboarding_context(request)
        return render(request, 'eventyay_common/dashboard/dashboard.html', ctx)

    widgets = []
    for r, result in user_dashboard_widgets.send(request, user=request.user):
        widgets.extend(result)

    ctx = build_organiser_dashboard_context(request, annotated_event_query)
    ctx['widgets'] = rearrange(widgets)
    ctx['video_permission_dialog_id'] = VIDEO_PERMISSION_DIALOG_ID
    return render(request, 'eventyay_common/dashboard/dashboard.html', ctx)


def user_index_widgets_lazy(request: HttpRequest) -> JsonResponse:
    widgets = []
    widgets += widgets_for_event_qs(
        request,
        annotated_event_query(request)
        .filter(
            Q(has_subevents=False)
            & Q(
                Q(Q(date_to__isnull=True) & Q(date_from__gte=now()))
                | Q(Q(date_to__isnull=False) & Q(date_to__gte=now()))
            )
        )
        .order_by('date_from', 'order_to', 'pk'),
        7,
    )
    widgets += widgets_for_event_qs(
        request,
        annotated_event_query(request)
        .filter(
            Q(has_subevents=False)
            & Q(
                Q(Q(date_to__isnull=True) & Q(date_from__lt=now())) | Q(Q(date_to__isnull=False) & Q(date_to__lt=now()))
            )
        )
        .order_by('-order_to', 'pk'),
        8,
    )
    widgets += widgets_for_event_qs(
        request,
        annotated_event_query(request).filter(has_subevents=True).order_by('-order_to', 'pk'),
        8,
    )
    return JsonResponse({'widgets': widgets})

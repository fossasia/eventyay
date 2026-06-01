import logging
import re
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

import pytz
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
)
from django.db.models.functions import Coalesce, Greatest
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.html import escape, format_html
from django.utils.timezone import now
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from pytz.tzinfo import DstTzInfo
from zoneinfo import ZoneInfo

from eventyay.base.models import (
    Event,
    Product,
    ProductCategory,
    Order,
    OrderRefund,
    Question,
    Quota,
    RequiredAction,
    SubEvent,
    Voucher,
)
from eventyay.base.timeline import timeline_for_event
from eventyay.control.forms.event import CommentForm
from eventyay.control.signals import (
    event_dashboard_widgets,
    user_dashboard_widgets,
)
from eventyay.helpers.daterange import daterange
from eventyay.helpers.plugin_enable import is_video_enabled

from ...base.models.orders import CancellationRequest
from ..permissions import filter_timeline_entry_for_ticket_access, user_has_ticket_dashboard_access
from ..utils import EventCreatedFor, get_subevent

logger = logging.getLogger(__name__)

OVERVIEW_BANLIST = ['eventyay.plugins.sendmail.order.email.sent']

SHOP_STATE_WIDGET_KEY = 'shop_state'
# Widget producers that should remain visible to talk-only users must set
# ``key='shop_state'`` on their dashboard widget payload (see shop_state_widget).
EVENT_SETTINGS_PERMISSION_DIALOG_ID = 'event-settings-permission-dialog'
TICKET_PERMISSION_DIALOG_ID = 'ticket-permission-dialog'

_ANCHOR_TAG_RE = re.compile(r'<a\b[^>]*>|</a>', re.IGNORECASE)


def _sanitize_widget_content_for_permission_dialog(content: str) -> str:
    """Return widget HTML safe to show inside a permission-dialog trigger."""
    if not content:
        return content
    content = _ANCHOR_TAG_RE.sub('', content)
    return content.replace(gettext('Click here to change'), '')


def get_event_dashboard_widget_permissions(request: HttpRequest) -> dict[str, bool]:
    return {
        'can_view_orders': request.user.has_event_permission(
            request.organizer, request.event, 'can_view_orders', request=request
        ),
        'can_change_event_settings': request.user.has_event_permission(
            request.organizer,
            request.event,
            'can_change_event_settings',
            request=request,
        ),
    }


def filter_event_dashboard_widgets_for_request(
    request: HttpRequest,
    widgets: List[Dict[str, Any]] | None,
) -> List[Dict[str, Any]]:
    permissions = get_event_dashboard_widget_permissions(request)
    return filter_common_event_dashboard_widgets(
        widgets,
        can_view_orders=permissions['can_view_orders'],
        can_change_event_settings=permissions['can_change_event_settings'],
    )


def filter_common_event_dashboard_widgets(
    widgets: List[Dict[str, Any]] | None,
    *,
    can_view_orders: bool,
    can_change_event_settings: bool,
) -> List[Dict[str, Any]]:
    """Limit dashboard widgets on the common event home for talk-only users.

    Users without ``can_view_orders`` only see widgets whose ``key`` is
    ``shop_state`` (ticket shop live status). Other widgets are omitted unless
    they declare that key or the user gains ticket permissions.
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
        if not can_view_orders and widget.get('key') != SHOP_STATE_WIDGET_KEY:
            continue
        if widget.get('key') == SHOP_STATE_WIDGET_KEY and not can_change_event_settings:
            widget = dict(widget)
            widget.pop('url', None)
            widget.pop('link', None)
            widget['content'] = _sanitize_widget_content_for_permission_dialog(widget.get('content', ''))
            widget['permission_dialog_id'] = EVENT_SETTINGS_PERMISSION_DIALOG_ID
        filtered.append(widget)
    return filtered


def event_index_widgets_lazy(request: HttpRequest, **kwargs) -> JsonResponse:
    subevent = get_subevent(request)

    widgets: List[Dict[str, Any]] = []
    for r, result in event_dashboard_widgets.send(
        sender=request.event,
        subevent=subevent,
        lazy=False,
        request=request,
    ):
        widgets.extend(filter_event_dashboard_widgets_for_request(request, result))

    return JsonResponse({'widgets': widgets})


class EventIndexView(TemplateView):
    """
    A class-based view for rendering the event index dashboard.
    """

    template_name = 'eventyay_common/event/index.html'

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

    def _collect_dashboard_widgets(
        self, subevent: Optional[SubEvent], permissions: Dict[str, bool]
    ) -> List[Dict[str, Any]]:
        """
        Collect and filter dashboard widgets based on permissions.

        Talk-only users see the event live-status widget but not ticket metrics.
        """
        request = self.request
        widgets: List[Dict[str, Any]] = []
        for caller, result in event_dashboard_widgets.send(
            sender=request.event,
            subevent=subevent,
            lazy=True,
            request=request,
        ):
            widgets.extend(filter_event_dashboard_widgets_for_request(request, result))
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request

        # Get subevent and permissions
        subevent = get_subevent(request)
        permissions = self._get_user_permissions()

        # Collect widgets
        widgets = self._collect_dashboard_widgets(subevent, permissions)

        # Filter log entries
        qs = (
            request.event.logentry_set.all()
            .select_related('user', 'content_type', 'api_token', 'oauth_application', 'device')
            .order_by('-datetime')
        )
        qs = self._filter_log_entries(qs, permissions)

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
                'is_video_enabled': is_video_enabled(request.event),
                'can_change_event_settings': permissions['can_change_event_settings'],
                **self._check_event_statuses(permissions['can_view_orders']),
            }
        )

        # Process actions
        for action in context['actions']:
            action.display = action.display(request)

        # Add timeline information
        has_ticket_access = user_has_ticket_dashboard_access(
            request.user, request.organizer, request.event, request=request
        )
        context['timeline'] = [
            {
                'date': t.datetime.astimezone(ZoneInfo(request.event.timezone)).date(),
                'entry': filter_timeline_entry_for_ticket_access(t, has_ticket_access),
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
    def format_event_daterange(event: Event, tz: DstTzInfo) -> str:
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
    def format_event_times(event: Event, tz: DstTzInfo, request: HttpRequest) -> str:
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
    def generate_video_button(event: Event) -> str:
        """
        Generate a video button that always links to the video access view.
        The access view will ensure configuration and plugin setup as needed.
        """
        url = reverse(
            'eventyay_common:event.create_access_to_video',
            kwargs={'event': event.slug, 'organizer': event.organizer.slug},
        )
        return f'<a href="{url}" class="component">{_("Video")}</a>'

    @staticmethod
    def generate_talk_button(event: Event) -> str:
        """
        Generate a talk button based on event settings.
        """
        if event.settings.create_for == EventCreatedFor.BOTH.value or event.settings.talk_schedule_public is not None:
            talk_url = reverse('orga:event.dashboard', kwargs={'event': event.slug})
            return f'<a href="{talk_url}" class="middle-component">{_("Talks")}</a>'
        return f"""
            <a href="#" data-toggle="modal" data-target="#alert-modal" class="middle-component">
                {_('Talks')}
            </a>
        """

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
            '<button type="button" class="component" aria-haspopup="dialog" '
            'aria-controls="{}" data-dialog-target="#{}" data-toggle="dialog">{}</button>',
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
            tz = pytz.timezone(tzname)

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
                video_button=cls.generate_video_button(event),
                talk_button=cls.generate_talk_button(event),
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
    widgets = []
    for r, result in user_dashboard_widgets.send(request, user=request.user):
        widgets.extend(result)
    ctx = {
        'widgets': rearrange(widgets),
        'can_create_event': request.user.teams.filter(can_create_events=True).exists(),
        'upcoming': widgets_for_event_qs(
            request,
            annotated_event_query(request, lazy=True)
            .filter(
                Q(has_subevents=False)
                & Q(
                    Q(Q(date_to__isnull=True) & Q(date_from__gte=now()))
                    | Q(Q(date_to__isnull=False) & Q(date_to__gte=now()))
                )
            )
            .order_by('date_from', 'order_to', 'pk'),
            7,
            lazy=True,
        ),
        'past': widgets_for_event_qs(
            request,
            annotated_event_query(request, lazy=True)
            .filter(
                Q(has_subevents=False)
                & Q(
                    Q(Q(date_to__isnull=True) & Q(date_from__lt=now()))
                    | Q(Q(date_to__isnull=False) & Q(date_to__lt=now()))
                )
            )
            .order_by('-order_to', 'pk'),
            8,
            lazy=True,
        ),
        'series': widgets_for_event_qs(
            request,
            annotated_event_query(request, lazy=True).filter(has_subevents=True).order_by('-order_to', 'pk'),
            8,
            lazy=True,
        ),
    }

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

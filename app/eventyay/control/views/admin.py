import json
import logging
import sys
from datetime import UTC, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from allauth.account.models import EmailAddress
from cron_descriptor import Options, get_description
from django.conf import settings
from django.contrib import messages
from django.db.models import (
    Case,
    Count,
    DateTimeField,
    F,
    Min,
    Prefetch,
    Q,
    Sum,
    When,
)
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.functional import cached_property
from django.utils.timezone import make_aware, is_aware, now
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)
from django_celery_beat.models import PeriodicTask, PeriodicTasks
from django_context_decorator import context
from django_scopes import scopes_disabled

from redis.exceptions import RedisError

from eventyay.celery_app import app
from eventyay.control.forms.filter import AttendeeFilterForm
from eventyay.control.forms.admin.admin import UpdateSettingsForm

from eventyay.base.models.auth import User
from eventyay.base.models.checkin import Checkin
from eventyay.base.models.event import Event, Event_SettingsStore
from eventyay.base.models.orders import Order, OrderPosition, OrderPayment, OrderRefund
from eventyay.base.models.organizer import Organizer
from eventyay.base.models.settings import GlobalSettings
from eventyay.base.models.cfp import CfP
from eventyay.base.models.submission import Submission, SubmissionStates
from eventyay.base.models.vouchers import InvoiceVoucher
from eventyay.base.models.product import Product
from eventyay.base.services.update_check import check_result_table, update_check
from eventyay.common.text.phrases import phrases
from eventyay.control.forms.admin.vouchers import InvoiceVoucherForm
from eventyay.control.forms.filter import AdminOrderFilterForm, OrganizerFilterForm, SubmissionFilterForm, TaskFilterForm
from eventyay.control.permissions import AdministratorPermissionRequiredMixin
from eventyay.control.views import PaginationMixin
from eventyay.control.views.main import EventList

logger = logging.getLogger(__name__)


class AdminDashboard(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = 'pretixcontrol/admin/dashboard.html'

    def get_context_data(self, **kwargs) -> dict:
        ctx = super().get_context_data(**kwargs)
        n = now()

        # User KPIs
        user_stats = User.objects.aggregate(
            total=Count('id'),
            new_24h=Count('id', filter=Q(date_joined__gte=n - timedelta(hours=24))),
            new_7d=Count('id', filter=Q(date_joined__gte=n - timedelta(days=7))),
            new_30d=Count('id', filter=Q(date_joined__gte=n - timedelta(days=30))),
            banned=Count('id', filter=Q(moderation_state=User.ModerationState.BANNED)),
            is_spam=Count('id', filter=Q(is_spam=True)),
            recently_active=Count('id', filter=Q(last_login__gte=n - timedelta(days=30), last_login__isnull=False)),
            deleted=Count('id', filter=Q(Q(deleted=True) | Q(email__endswith='@disabled.eventyay.com'))),
            staff=Count('id', filter=Q(Q(is_staff=True) | Q(is_administrator=True))),
        )
        users_verified = EmailAddress.objects.filter(verified=True, primary=True).values('user_id').distinct().count()

        ctx['users_total'] = user_stats['total']
        ctx['users_verified'] = users_verified
        ctx['users_unverified'] = user_stats['total'] - users_verified
        ctx['users_new_24h'] = user_stats['new_24h']
        ctx['users_new_7d'] = user_stats['new_7d']
        ctx['users_new_30d'] = user_stats['new_30d']
        ctx['users_banned'] = user_stats['banned']
        ctx['users_is_spam'] = user_stats['is_spam']
        ctx['users_staff'] = user_stats['staff']
        ctx['users_recently_active'] = user_stats['recently_active']
        ctx['users_deleted'] = user_stats['deleted']

        # Organizer KPIs
        ctx['organizers_total'] = Organizer.objects.count()

        with scopes_disabled():
            # Event KPIs
            event_kpis = Event.objects.aggregate(
                total=Count('id'),
                live=Count('id', filter=Q(live=True)),
                series=Count('id', filter=Q(has_subevents=True)),
            )
            ctx['events_total'] = event_kpis['total']
            ctx['events_live'] = event_kpis['live']
            ctx['events_draft'] = event_kpis['total'] - event_kpis['live']
            ctx['events_past'] = (
                Event.objects.filter(has_subevents=False)
                .filter(
                    Q(Q(date_to__isnull=True) & Q(date_from__lt=n))
                    | Q(Q(date_to__isnull=False) & Q(date_to__lt=n))
                )
                .count()
            )
            ctx['events_series'] = event_kpis['series']

            # Event activity
            ctx['events_running'] = (
                Event.objects.filter(has_subevents=False, live=True, date_from__lte=n)
                .filter(Q(date_to__isnull=True) | Q(date_to__gte=n))
                .count()
            )
            ctx['events_upcoming'] = list(
                Event.objects.filter(has_subevents=False, date_from__gt=n)
                .select_related('organizer')
                .order_by('date_from')[:10]
            )
            ctx['events_recent'] = list(
                Event.objects.filter(has_subevents=False)
                .select_related('organizer')
                .order_by('-pk')[:10]
            )

            # Exclude events with active payment settings at database level to build candidates
            events_with_payment = Event_SettingsStore.objects.filter(
                key__startswith='payment_',
                key__endswith='__enabled',
                value='True',
            ).exclude(
                key__in=[
                    'payment_free__enabled',
                    'payment_boxoffice__enabled',
                    'payment_offsetting__enabled',
                    'payment_giftcard__enabled',
                ]
            ).values_list('object_id', flat=True)

            events_with_paid_products = Product.objects.filter(
                default_price__gt=0
            ).values_list('event_id', flat=True)

            events_no_products = Event.objects.filter(products__isnull=True)
            events_missing_payment = Event.objects.filter(id__in=events_with_paid_products).exclude(
                id__in=events_with_payment
            )

            events_pending_setup = (events_no_products | events_missing_payment).distinct()

            # Fetch candidates (up to 20 candidates is sufficient to find 5)
            candidates = list(
                events_pending_setup.select_related('organizer')
                .prefetch_related('products')
                .order_by('-pk')[:20]
            )

            payment_enabled_event_ids = set(events_with_payment)
            events_pending_setup_list = []
            for event in candidates:
                products = list(event.products.all())
                has_products = bool(products)
                has_paid_products = any(p.default_price > 0 for p in products)
                has_payment_provider = event.pk in payment_enabled_event_ids
                if not has_products or (has_paid_products and not has_payment_provider):
                    event.has_products = has_products
                    events_pending_setup_list.append(event)
                    if len(events_pending_setup_list) == 5:
                        break
            ctx['events_pending_setup_list'] = events_pending_setup_list

            # CfP stats
            ctx['events_cfp_open_count'] = CfP.objects.filter(
                Q(deadline__isnull=True) | Q(deadline__gte=n) | Q(event__submission_types__deadline__gte=n)
            ).distinct().count()

            cfp_closing_until = n + timedelta(days=7)
            cfps_closing_soon = list(
                CfP.objects.filter(
                    Q(deadline__gte=n, deadline__lte=cfp_closing_until)
                    | Q(
                        event__submission_types__deadline__gte=n,
                        event__submission_types__deadline__lte=cfp_closing_until,
                    )
                )
                .distinct()
                .select_related('event', 'event__organizer')
                .annotate(
                    cfp_deadline_soon=Case(
                        When(deadline__gte=n, deadline__lte=cfp_closing_until, then=F('deadline')),
                        output_field=DateTimeField(),
                    ),
                    type_deadline_soon=Min(
                        'event__submission_types__deadline',
                        filter=Q(
                            event__submission_types__deadline__gte=n,
                            event__submission_types__deadline__lte=cfp_closing_until,
                        ),
                    ),
                )
            )
            for cfp in cfps_closing_soon:
                cfp.closing_deadline = min(
                    deadline for deadline in (cfp.cfp_deadline_soon, cfp.type_deadline_soon) if deadline
                )
            ctx['events_cfp_closing_soon'] = sorted(cfps_closing_soon, key=lambda cfp: cfp.closing_deadline)[:5]

            # Order KPIs
            order_stats = Order.objects.aggregate(
                total=Count('id'),
                paid=Count('id', filter=Q(status=Order.STATUS_PAID)),
                pending=Count('id', filter=Q(status=Order.STATUS_PENDING))
            )
            ctx['orders_total'] = order_stats['total']
            ctx['orders_paid'] = order_stats['paid']
            ctx['orders_pending'] = order_stats['pending']

            # Gross Revenue from confirmed payments
            payment_sums = {
                r['order__event__currency']: r['total']
                for r in OrderPayment.objects.filter(state=OrderPayment.PAYMENT_STATE_CONFIRMED)
                .values('order__event__currency')
                .annotate(total=Sum('amount'))
                .order_by()
            }

            refund_sums = {
                r['order__event__currency']: r['total']
                for r in OrderRefund.objects.filter(state=OrderRefund.REFUND_STATE_DONE)
                .values('order__event__currency')
                .annotate(total=Sum('amount'))
                .order_by()
            }

            # Order counts per currency
            currency_counts = Order.objects.values('event__currency').annotate(
                paid=Count('pk', filter=Q(status=Order.STATUS_PAID) & ~Q(total=0), distinct=True),
                pending=Count('pk', filter=Q(status=Order.STATUS_PENDING), distinct=True),
                cancelled=Count('pk', filter=Q(status=Order.STATUS_CANCELED), distinct=True),
                free=Count('pk', filter=Q(status=Order.STATUS_PAID) & Q(total=0), distinct=True)
            ).order_by()

            order_counts_by_currency = {
                entry['event__currency']: {
                    'paid': entry['paid'],
                    'pending': entry['pending'],
                    'cancelled': entry['cancelled'],
                    'free': entry['free']
                }
                for entry in currency_counts
            }

            all_currencies = sorted(list(
                set(payment_sums.keys()) | set(refund_sums.keys()) | set(order_counts_by_currency.keys())
            ))

            ctx['orders_net_revenue'] = []
            for currency in all_currencies:
                gross = payment_sums.get(currency, Decimal('0.00')) or Decimal('0.00')
                refunded = refund_sums.get(currency, Decimal('0.00')) or Decimal('0.00')
                net = gross - refunded
                counts = order_counts_by_currency.get(currency, {})
                ctx['orders_net_revenue'].append({
                    'currency': currency,
                    'gross': gross,
                    'refunded': refunded,
                    'net': net,
                    'paid_count': counts.get('paid', 0),
                    'pending_count': counts.get('pending', 0),
                    'cancelled_count': counts.get('cancelled', 0),
                    'free_count': counts.get('free', 0),
                })

            ctx['orders_revenue'] = sorted(
                [
                    {'event__currency': item['currency'], 'total': item['net']}
                    for item in ctx['orders_net_revenue']
                ],
                key=lambda x: x['total'],
                reverse=True
            )

            # Schedule stats
            ctx['events_with_schedule_count'] = (
                Event.objects.filter(schedules__published__isnull=False).distinct().count()
            )
            ctx['events_without_schedule_count'] = (
                Event.objects.exclude(schedules__published__isnull=False).distinct().count()
            )

            # Programme KPIs
            submission_kpis = Submission.objects.aggregate(
                total=Count('id'),
                submitted=Count('id', filter=Q(state=SubmissionStates.SUBMITTED)),
                total_submitted=Count(
                    'id',
                    filter=~Q(state__in=[SubmissionStates.DRAFT, SubmissionStates.DELETED]),
                ),
                accepted=Count('id', filter=Q(state=SubmissionStates.ACCEPTED)),
                rejected=Count('id', filter=Q(state=SubmissionStates.REJECTED)),
                confirmed=Count('id', filter=Q(state=SubmissionStates.CONFIRMED)),
            )
            ctx['sessions_total'] = submission_kpis['total']
            ctx['sessions_submitted'] = submission_kpis['submitted']
            ctx['sessions_total_submitted'] = submission_kpis['total_submitted']
            ctx['sessions_accepted'] = submission_kpis['accepted']
            ctx['sessions_rejected'] = submission_kpis['rejected']
            ctx['sessions_confirmed'] = submission_kpis['confirmed']

            ctx['sessions_recent_submissions'] = list(
                Submission.objects.filter(state=SubmissionStates.SUBMITTED)
                .select_related('event', 'event__organizer')
                .order_by('-pk')[:5]
            )

            ctx['speakers_total'] = (
                Submission.speakers.through.objects
                .exclude(submission__state__in=[SubmissionStates.DRAFT, SubmissionStates.DELETED])
                .values('user_id')
                .distinct()
                .count()
            )
            ctx['speakers_confirmed'] = (
                Submission.speakers.through.objects
                .filter(submission__state=SubmissionStates.CONFIRMED)
                .values('user_id').distinct().count()
            )
            ctx['speakers_unconfirmed'] = (
                Submission.speakers.through.objects
                .exclude(submission__state__in=[
                    SubmissionStates.CONFIRMED,
                    SubmissionStates.REJECTED,
                    SubmissionStates.CANCELED,
                    SubmissionStates.WITHDRAWN,
                    SubmissionStates.DELETED,
                    SubmissionStates.DRAFT,
                ])
                .values('user_id').distinct().count()
            )

            # Attendee / ticket KPIs
            attendee_stats = OrderPosition.objects.filter(
                order__status=Order.STATUS_PAID
            ).aggregate(
                attendees_total=Count('id', filter=Q(addon_to__isnull=True)),
                tickets_issued=Count('id')
            )
            ctx['attendees_total'] = attendee_stats['attendees_total']
            ctx['tickets_issued'] = attendee_stats['tickets_issued']

        return ctx


class OrganizerList(AdministratorPermissionRequiredMixin, PaginationMixin, ListView):
    model = Organizer
    context_object_name = 'organizers'
    template_name = 'pretixcontrol/admin/organizers.html'

    def get_queryset(self):
        qs = Organizer.objects.all()
        if self.filter_form.is_valid():
            qs = self.filter_form.filter_qs(qs)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form
        return ctx

    @cached_property
    def filter_form(self):
        return OrganizerFilterForm(data=self.request.GET, request=self.request)


class AdminEventList(AdministratorPermissionRequiredMixin, EventList):
    """Inherit from EventList to add a custom template for the admin event list."""

    template_name = 'pretixcontrol/admin/events/index.html'

    def get_queryset(self):
        # Keep settings prefetched for component test-mode state checks in the list.
        return super().get_queryset().prefetch_related('_settings_objects')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        for event in ctx.get('events', []):
            event.component_testmode = event.has_component_testmode
            event.startpage_toggle_locked = bool(event.component_testmode or not event.live)
        return ctx


class AdminEventStartpageToggle(AdministratorPermissionRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        data = request.POST
        if not data:
            try:
                data = json.loads(request.body.decode('utf-8'))
            except (ValueError, AttributeError):
                data = {}

        event_id = data.get('event_id')
        field = data.get('field')
        value = data.get('value')

        if field not in {'startpage_visible', 'startpage_featured'}:
            return JsonResponse({'ok': False, 'error': _('Invalid field.')}, status=400)
        if event_id is None:
            return JsonResponse({'ok': False, 'error': _('Event not found.')}, status=404)

        event = get_object_or_404(Event, pk=event_id)
        enable = str(value).lower() in {'true', '1', 'yes', 'on'}

        if event.has_component_testmode or not event.live:
            return JsonResponse(
                {
                    'ok': False,
                    'error': _('Only published events without test mode can be shown on the start page.'),
                },
                status=400,
            )

        if field == 'startpage_featured':
            event.startpage_featured = enable
            if enable:
                event.startpage_visible = True
            event.save(update_fields=['startpage_featured', 'startpage_visible'])
        else:
            event.startpage_visible = enable
            if not enable and event.startpage_featured:
                event.startpage_featured = False
            event.save(update_fields=['startpage_visible', 'startpage_featured'])

        return JsonResponse(
            {
                'ok': True,
                'startpage_visible': event.startpage_visible,
                'startpage_featured': event.startpage_featured,
                'startpage_locked': bool(event.has_component_testmode or not event.live),
            }
        )


class AttendeeListView(AdministratorPermissionRequiredMixin, ListView):
    template_name = 'pretixcontrol/admin/attendees/index.html'
    context_object_name = 'attendees'
    paginate_by = 25

    @cached_property
    def filter_form(self):
        return AttendeeFilterForm(data=self.request.GET)

    def get_queryset(self):
        qs = (
            OrderPosition.objects.select_related('order', 'product', 'order__event', 'order__event__organizer')
            .prefetch_related(
                Prefetch(
                    'checkins',
                    queryset=Checkin.objects.order_by('-datetime'),
                )
            )
            .filter(order__status='p')
        )

        if self.filter_form.is_valid():
            qs = self.filter_form.filter_qs(qs)

        ordering = self.request.GET.get('ordering')
        ordering_map = {
            'name': 'attendee_name_cached',
            '-name': '-attendee_name_cached',
            'email': 'attendee_email',
            '-email': '-attendee_email',
            'event': 'order__event__name',
            '-event': '-order__event__name',
            'order_code': 'order__code',
            '-order_code': '-order__code',
            'product': 'product__name',
            '-product': '-product__name',
        }

        if ordering in ordering_map:
            qs = qs.order_by(ordering_map[ordering])
        else:
            qs = qs.order_by('-order__event__date_from', 'order__event__name')

        return qs

    @staticmethod
    def _checkin_status(pos):
        def parse_dt(dt):
            if not dt:
                return None
            return dt if is_aware(dt) else make_aware(dt, UTC)

        checkins = pos.checkins.all()
        entry_time = parse_dt(next((c.datetime for c in checkins if c.type == Checkin.TYPE_ENTRY), None))
        exit_time = parse_dt(next((c.datetime for c in checkins if c.type == Checkin.TYPE_EXIT), None))

        if not entry_time and not exit_time:
            return 'Not checked in'
        if entry_time and not exit_time:
            return 'Checked in'
        if not entry_time and exit_time:
            return 'Checked out (no entry record)'
        if exit_time < entry_time:
            return 'Invalid check-in data (exit before entry)'
        if exit_time == entry_time:
            return 'Checked in and out at same time'
        return 'Checked in but left'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form

        ctx['attendees'] = [
            {
                'name': pos.attendee_name_cached or '',
                'email': pos.attendee_email or pos.order.email,
                'event': pos.order.event.name,
                'event_slug': pos.order.event.slug,
                'organizer_slug': pos.order.event.organizer.slug,
                'order_code': pos.order.code,
                'product': str(pos.product.name),
                'check_in_status': self._checkin_status(pos),
                'testmode': pos.order.testmode,
            }
            for pos in ctx['attendees']
        ]
        return ctx


class SubmissionListView(AdministratorPermissionRequiredMixin, ListView):
    template_name = 'pretixcontrol/admin/submissions/index.html'
    context_object_name = 'submissions'
    paginate_by = 25

    @cached_property
    def filter_form(self):
        return SubmissionFilterForm(data=self.request.GET)

    def get(self, request, *args, **kwargs):
        with scopes_disabled():
            return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = (
            Submission.objects.select_related(
                'event', 'event__organizer', 'submission_type', 'track'
            )
            .prefetch_related('speakers', 'tags')
        )

        if self.filter_form.is_valid():
            qs = self.filter_form.filter_qs(qs)

        ordering = self.request.GET.get('ordering')
        ordering_map = {
            'title': 'title',
            '-title': '-title',
            'event': 'event__name',
            '-event': '-event__name',
            'speakers': 'speakers__fullname',
            '-speakers': '-speakers__fullname',
            'state': 'state',
            '-state': '-state',
            'session_type': 'submission_type__name',
            '-session_type': '-submission_type__name',
        }

        if ordering in ordering_map:
            qs = qs.order_by(ordering_map[ordering])
        else:
            qs = qs.order_by('-event__date_from', 'title')

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form

        ctx['submissions'] = [
            {
                'title': s.title,
                'speakers': ', '.join(sp.get_display_name() for sp in s.speakers.all()),
                'event': s.event.name,
                'session_type': s.submission_type.name if s.submission_type else '',
                'proposal_state': s.state,
                'event_slug': s.event.slug,
                'organizer_slug': s.event.organizer.slug,
                'code': s.code,
                'track': s.track.name if s.track else '',
                'tags': ', '.join(t.tag for t in s.tags.all()),
            }
            for s in ctx['submissions']
        ]
        return ctx


class AdminOrderListView(PaginationMixin, AdministratorPermissionRequiredMixin, ListView):
    template_name = 'pretixcontrol/admin/orders/index.html'
    context_object_name = 'orders'
    paginate_by = 25

    @cached_property
    def filter_form(self):
        return AdminOrderFilterForm(data=self.request.GET)

    def get(self, request, *args, **kwargs):
        with scopes_disabled():
            return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = Order.objects.select_related('event', 'event__organizer')

        if self.filter_form.is_valid():
            qs = self.filter_form.filter_qs(qs)

        ordering = self.request.GET.get('ordering')
        ordering_map = {
            'code': 'code',
            '-code': '-code',
            'email': 'email',
            '-email': '-email',
            'event': 'event__name',
            '-event': '-event__name',
            'organizer': 'event__organizer__name',
            '-organizer': '-event__organizer__name',
            'status': 'status',
            '-status': '-status',
            'total': 'total',
            '-total': '-total',
            'date': 'datetime',
            '-date': '-datetime',
        }
        sort_field = ordering_map.get(ordering, '-datetime')
        tie_breaker = '-pk' if sort_field.startswith('-') else 'pk'
        qs = qs.order_by(sort_field, tie_breaker)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form
        ctx['orders'] = [
            {
                'order_code': o.code,
                'event': o.event.name,
                'event_slug': o.event.slug,
                'organizer': o.event.organizer.name,
                'organizer_slug': o.event.organizer.slug,
                'email': o.email or '',
                'status': o.get_status_display(),
                'status_code': o.status,
                'total': o.total,
                'currency': o.event.currency,
                'date': o.datetime,
                'testmode': o.testmode,
            }
            for o in ctx['orders']
        ]
        return ctx


class TaskList(AdministratorPermissionRequiredMixin, PaginationMixin, ListView):
    template_name = 'pretixcontrol/admin/task_management/task_management.html'
    context_object_name = 'tasks'
    model = PeriodicTask

    @cached_property
    def filter_form(self):
        return TaskFilterForm(data=self.request.GET)

    def get_queryset(self):
        queryset = super().get_queryset().exclude(name='celery.backend_cleanup').select_related('crontab')

        if self.filter_form.is_valid():
            queryset = self.filter_form.filter_qs(queryset)

        return queryset

    def process_task_data(self, task):
        if task.last_run_at is None:
            task.formatted_last_run_at = '-'
        else:
            local_timezone = ZoneInfo(settings.TIME_ZONE)
            task.formatted_last_run_at = date_format(
                task.last_run_at.astimezone(local_timezone), format='M. d, Y, g:i a'
            )

        task.name = task.name.replace('_', ' ').capitalize()

        options = Options()
        options.locale_code = settings.LANGUAGE_CODE
        options.verbose = True
        schedule = task.crontab
        if schedule:
            cron_expression = (
                f'{schedule.minute} {schedule.hour} {schedule.day_of_month} {schedule.month_of_year} {schedule.day_of_week}'
            )
            task.run_at = get_description(cron_expression, options)
        elif task.interval:
            task.run_at = f"Every {task.interval.every} {task.interval.period}"
        elif task.solar:
            task.run_at = f"Solar: {task.solar.event}"
        elif task.clocked:
            task.run_at = f"Clocked: {task.clocked.clocked_time}"
        else:
            task.run_at = "-"

        return task

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['tasks'] = [self.process_task_data(task) for task in context['tasks']]

        context['filter_form'] = self.filter_form
        return context

    def post(self, request, *args, **kwargs):
        task_id = request.POST.get('task_id')
        current_enabled = request.POST.get('enabled') == 'true'

        if task_id:
            task = get_object_or_404(PeriodicTask, id=task_id)
            new_status = not current_enabled

            PeriodicTask.objects.filter(id=task_id).update(enabled=new_status)
            PeriodicTasks.changed(task)

            status_text = 'enabled' if new_status else 'disabled'
            messages.success(
                self.request,
                f'The task {task.name} has been successfully {status_text}.',
            )

            return HttpResponseRedirect(reverse('eventyay_admin:admin.task_management'))


class VoucherList(PaginationMixin, AdministratorPermissionRequiredMixin, ListView):
    model = InvoiceVoucher
    context_object_name = 'vouchers'
    template_name = 'pretixcontrol/admin/vouchers/index.html'

    def get_queryset(self):
        qs = InvoiceVoucher.objects.all()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        return ctx

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class VoucherCreate(AdministratorPermissionRequiredMixin, CreateView):
    model = InvoiceVoucher
    template_name = 'pretixcontrol/admin/vouchers/detail.html'
    context_object_name = 'voucher'

    def get_form_class(self):
        form_class = InvoiceVoucherForm
        return form_class

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['currency'] = settings.DEFAULT_CURRENCY
        return ctx

    def get_success_url(self) -> str:
        return reverse('eventyay_admin:admin.vouchers')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        return kwargs

    def form_valid(self, form):
        req = super().form_valid(form)
        return req

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class VoucherUpdate(AdministratorPermissionRequiredMixin, UpdateView):
    model = InvoiceVoucher
    template_name = 'pretixcontrol/admin/vouchers/detail.html'
    context_object_name = 'voucher'

    def get_form_class(self):
        form_class = InvoiceVoucherForm
        return form_class

    def get_object(self, queryset=None) -> InvoiceVoucherForm:
        try:
            return InvoiceVoucher.objects.get(id=self.kwargs['voucher'])
        except InvoiceVoucher.DoesNotExist:
            raise Http404(_('The requested voucher does not exist.'))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['currency'] = settings.DEFAULT_CURRENCY
        return ctx

    def form_valid(self, form):
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse('eventyay_admin:admin.vouchers')


class VoucherDelete(AdministratorPermissionRequiredMixin, DeleteView):
    model = InvoiceVoucher
    template_name = 'pretixcontrol/admin/vouchers/delete.html'
    context_object_name = 'invoice_voucher'

    def get_object(self, queryset=None) -> InvoiceVoucher:
        try:
            return InvoiceVoucher.objects.get(id=self.kwargs['voucher'])
        except InvoiceVoucher.DoesNotExist:
            raise Http404(_('The requested voucher does not exist.'))

    def get(self, request, *args, **kwargs):
        if self.get_object().redeemed > 0:
            messages.error(
                request,
                _('A voucher can not be deleted if it already has been redeemed.'),
            )
            return HttpResponseRedirect(self.get_success_url())
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = self.get_object()
        success_url = self.get_success_url()

        if self.object.redeemed > 0:
            messages.error(
                self.request,
                _('A voucher can not be deleted if it already has been redeemed.'),
            )
        else:
            self.object.delete()
            messages.success(self.request, _('The selected voucher has been deleted.'))
        return HttpResponseRedirect(success_url)

    def get_success_url(self) -> str:
        return reverse('eventyay_admin:admin.vouchers')


class SystemConfigView(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = 'pretixcontrol/admin/systemconfig.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_name'] = settings.INSTANCE_NAME
        context['base_path'] = settings.BASE_PATH
        context['settings'] = settings
        return context

    @context
    def queue_length(self):
        if settings.CELERY_TASK_ALWAYS_EAGER:
            return None
        try:
            client = app.broker_connection().channel().client
            return client.llen('celery')
        except Exception as e:
            return str(e)

    @context
    def executable(self):
        return sys.executable

    @context
    def eventyay_version(self):
        return settings.EVENTYAY_VERSION


class UpdateCheckView(AdministratorPermissionRequiredMixin, FormView):
    template_name = 'pretixcontrol/admin/update.html'
    form_class = UpdateSettingsForm

    def post(self, request, *args, **kwargs):
        if 'trigger' in request.POST:
            update_check.apply()
            return redirect(self.get_success_url())
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        messages.success(self.request, phrases.base.saved)
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, phrases.base.error_saving_changes)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        result['gs'] = GlobalSettings()
        result['gs'].settings.set('update_check_ack', True)
        return result

    @context
    def result_table(self):
        return check_result_table()

    def get_success_url(self):
        return reverse('eventyay_admin:admin.update')

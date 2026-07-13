import datetime
import json

import dateutil.rrule
from django.contrib.contenttypes.models import ContentType
from django.db.models import (
    Count,
    DateTimeField,
    Exists,
    OuterRef,
    Q,
    Sum,
)
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.views.generic import TemplateView
from django_scopes import scopes_disabled

from eventyay.base.models import (
    Checkin,
    CheckinList,
    LogEntry,
    Order,
    OrderPayment,
    OrderPosition,
    Submission,
    SubmissionStates,
)
from eventyay.control.permissions import OrganizerPermissionRequiredMixin
from eventyay.control.views.organizer import OrganizerDetailViewMixin


class OrganizerAnalyticsView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, TemplateView):

    template_name = 'eventyay_common/organizers/analytics.html'
    permission = None

    def _event_ids_for_orders(self):
        if not hasattr(self, '_cached_event_ids_for_orders'):
            self._cached_event_ids_for_orders = list(
                self.request.user.get_events_with_permission('can_view_orders', request=self.request)
                .filter(organizer=self.request.organizer)
                .values_list('pk', flat=True)
            )
        return self._cached_event_ids_for_orders

    def _event_ids_for_proposals(self):
        if not hasattr(self, '_cached_event_ids_for_proposals'):
            self._cached_event_ids_for_proposals = list(
                self.request.user.get_events_with_permission('can_change_submissions', request=self.request)
                .filter(organizer=self.request.organizer)
                .values_list('pk', flat=True)
            )
        return self._cached_event_ids_for_proposals

    def _event_ids_for_checkins(self):
        if not hasattr(self, '_cached_event_ids_for_checkins'):
            self._cached_event_ids_for_checkins = list(
                self.request.user.get_events_with_permission('can_checkin_orders', request=self.request)
                .filter(organizer=self.request.organizer)
                .values_list('pk', flat=True)
            )
        return self._cached_event_ids_for_checkins

    def _get_tickets_data(self):
        event_ids = self._event_ids_for_orders()
        if not event_ids:
            return {
                'orders_over_time_json': '[]',
                'orders_by_status_json': '[]',
                'revenue_over_time_json': '[]',
                'top_events': [],
                'has_orders': False,
            }

        tz = timezone.get_current_timezone()
        since = timezone.now() - datetime.timedelta(days=30)

        with scopes_disabled():
            placed_qs = (
                Order.objects.filter(event_id__in=event_ids, datetime__gte=since)
                .annotate(day=TruncDate('datetime', tzinfo=tz))
                .values('day')
                .annotate(cnt=Count('pk'))
                .order_by('day')
            )
            ordered_by_day = {row['day']: row['cnt'] for row in placed_qs}

            payment_day_qs = (
                OrderPayment.objects.filter(
                    order__event_id__in=event_ids,
                    state=OrderPayment.PAYMENT_STATE_CONFIRMED,
                    payment_date__gte=since,
                )
                .annotate(day=TruncDate('payment_date', tzinfo=tz))
                .values('day')
                .annotate(
                    cnt=Count('order', distinct=True),
                    revenue=Sum('amount')
                )
                .order_by('day')
            )
            payment_data = list(payment_day_qs)
            paid_by_day = {row['day']: row['cnt'] for row in payment_data}
            rev_by_day = {row['day']: float(row['revenue'] or 0) for row in payment_data}

            status_qs = (
                Order.objects.filter(event_id__in=event_ids)
                .values('status')
                .annotate(cnt=Count('pk'))
            )
            status_rows = list(status_qs)

            top_qs = list(
                Order.objects.filter(event_id__in=event_ids)
                .values('event', 'event__name', 'event__slug')
                .annotate(
                    total_orders=Count('pk'),
                    paid_orders=Count('pk', filter=Q(status=Order.STATUS_PAID)),
                )
                .order_by('-total_orders')[:10]
            )

            rev_qs = (
                OrderPayment.objects.filter(
                    order__event_id__in=event_ids,
                    state=OrderPayment.PAYMENT_STATE_CONFIRMED,
                )
                .values('order__event_id')
                .annotate(total=Sum('amount'))
            )
            event_revenue = {row['order__event_id']: row['total'] for row in rev_qs}

        orders_over_time = []
        if ordered_by_day or paid_by_day:
            all_keys = set(ordered_by_day.keys()) | set(paid_by_day.keys())
            start = min(all_keys)
            end = max(all_keys)
            for d in dateutil.rrule.rrule(dateutil.rrule.DAILY, dtstart=start, until=end):
                d = d.date()
                orders_over_time.append({
                    'x': d.strftime('%Y-%m-%d'),
                    'ordered': ordered_by_day.get(d, 0),
                    'paid': paid_by_day.get(d, 0)
                })

        label_map = {
            Order.STATUS_PENDING: str(Order.STATUS_CHOICE[0][1]),
            Order.STATUS_PAID: str(Order.STATUS_CHOICE[1][1]),
            Order.STATUS_EXPIRED: str(Order.STATUS_CHOICE[2][1]),
            Order.STATUS_CANCELED: str(Order.STATUS_CHOICE[3][1]),
        }
        orders_by_status = [
            {'label': label_map.get(row['status'], row['status']), 'value': row['cnt']}
            for row in status_rows
            if row['cnt'] > 0
        ]

        revenue_over_time = []
        cumulative = 0.0
        if rev_by_day:
            for d in dateutil.rrule.rrule(
                dateutil.rrule.DAILY,
                dtstart=min(rev_by_day.keys()),
                until=max(rev_by_day.keys()),
            ):
                d = d.date()
                cumulative += rev_by_day.get(d, 0.0)
                revenue_over_time.append({'x': d.strftime('%Y-%m-%d'), 'y': round(cumulative, 2)})

        top_events = [
            {
                'name': str(row['event__name']),
                'slug': row['event__slug'],
                'total_orders': row['total_orders'],
                'paid_orders': row['paid_orders'],
                'gross_revenue': float(event_revenue.get(row['event'], 0) or 0),
            }
            for row in top_qs
        ]

        return {
            'orders_over_time_json': json.dumps(orders_over_time),
            'orders_by_status_json': json.dumps(orders_by_status),
            'revenue_over_time_json': json.dumps(revenue_over_time),
            'top_events': top_events,
            'has_orders': bool(orders_over_time or orders_by_status),
        }

    def _get_proposals_data(self):
        event_ids = self._event_ids_for_proposals()
        if not event_ids:
            return {
                'has_proposals': False,
                'proposals_by_state_json': '[]',
                'proposals_over_time_json': '[]',
                'pending_proposal_events': [],
            }

        tz = timezone.get_current_timezone()
        since = timezone.now() - datetime.timedelta(days=60)

        with scopes_disabled():
            state_qs = list(
                Submission.objects.filter(event_id__in=event_ids)
                .values('state')
                .annotate(cnt=Count('pk'))
            )
            has_proposals = bool(state_qs)
            if not has_proposals:
                return {
                    'has_proposals': False,
                    'proposals_by_state_json': '[]',
                    'proposals_over_time_json': '[]',
                    'pending_proposal_events': [],
                }

            content_type = ContentType.objects.get_for_model(Submission)
            talk_ids = list(
                Submission.objects.filter(event_id__in=event_ids)
                .exclude(state=SubmissionStates.DELETED)
                .values_list('id', flat=True)
            )

            proposals_over_time = []
            if talk_ids:
                timeline_qs = list(
                    LogEntry.objects.filter(
                        event_id__in=event_ids,
                        action_type='eventyay.submission.create',
                        content_type=content_type,
                        object_id__in=talk_ids,
                        datetime__gte=since,
                    )
                    .annotate(day=TruncDate('datetime', tzinfo=tz))
                    .values('day')
                    .annotate(cnt=Count('pk'))
                    .order_by('day')
                )
                by_day = {row['day']: row['cnt'] for row in timeline_qs}
                if by_day:
                    for d in dateutil.rrule.rrule(
                        dateutil.rrule.DAILY,
                        dtstart=min(by_day.keys()),
                        until=max(by_day.keys()),
                    ):
                        d = d.date()
                        proposals_over_time.append({'x': d.strftime('%Y-%m-%d'), 'y': by_day.get(d, 0)})

            pending_qs = list(
                Submission.objects.filter(
                    event_id__in=event_ids,
                    state=SubmissionStates.SUBMITTED,
                )
                .values('event__name', 'event__slug')
                .annotate(pending=Count('pk'))
                .order_by('-pending')
            )

        label_map = dict(SubmissionStates.get_choices())
        proposals_by_state = [
            {'label': str(label_map.get(row['state'], row['state'])), 'value': row['cnt']}
            for row in state_qs
            if row['cnt'] > 0
        ]

        pending_proposal_events = [
            {
                'name': str(row['event__name']),
                'slug': row['event__slug'],
                'pending': row['pending'],
            }
            for row in pending_qs
        ]

        return {
            'has_proposals': True,
            'proposals_by_state_json': json.dumps(proposals_by_state),
            'proposals_over_time_json': json.dumps(proposals_over_time),
            'pending_proposal_events': pending_proposal_events,
        }

    def _get_checkins_data(self):
        event_ids = self._event_ids_for_checkins()
        if not event_ids:
            return {
                'show_checkins': False,
                'checkin_rate_json': '[]',
                'checkins_over_time_json': '[]',
            }

        tz = timezone.get_current_timezone()
        since = timezone.now() - datetime.timedelta(days=30)

        with scopes_disabled():
            show_checkins = CheckinList.objects.filter(event_id__in=event_ids).exists()
            if not show_checkins:
                return {
                    'show_checkins': False,
                    'checkin_rate_json': '[]',
                    'checkins_over_time_json': '[]',
                }

            event_stats = {}
            stats_qs = (
                OrderPosition.objects.filter(
                    order__event_id__in=event_ids,
                    order__status=Order.STATUS_PAID,
                )
                .annotate(
                    checkedin=Exists(
                        Checkin.objects.filter(
                            position_id=OuterRef('pk'),
                            type=Checkin.TYPE_ENTRY,
                        )
                    )
                )
                .values('order__event_id', 'order__event__name')
                .annotate(
                    total=Count('pk'),
                    checked_in=Count('pk', filter=Q(checkedin=True))
                )
            )
            for row in stats_qs:
                event_stats[row['order__event_id']] = {
                    'event': str(row['order__event__name']),
                    'total': row['total'],
                    'checked_in': row['checked_in']
                }

            timeline_qs = list(
                Checkin.objects.filter(
                    list__event_id__in=event_ids,
                    type=Checkin.TYPE_ENTRY,
                    datetime__gte=since,
                )
                .annotate(day=TruncDate('datetime', tzinfo=tz))
                .values('day')
                .annotate(cnt=Count('pk'))
                .order_by('day')
            )

        checkin_rate = sorted(
            [stats for stats in event_stats.values() if stats['total'] > 0],
            key=lambda r: r['event']
        )

        by_day = {row['day']: row['cnt'] for row in timeline_qs}
        checkins_over_time = []
        if by_day:
            for d in dateutil.rrule.rrule(
                dateutil.rrule.DAILY,
                dtstart=min(by_day.keys()),
                until=max(by_day.keys()),
            ):
                d = d.date()
                checkins_over_time.append({'x': d.strftime('%Y-%m-%d'), 'y': by_day.get(d, 0)})

        return {
            'show_checkins': True,
            'checkin_rate_json': json.dumps(checkin_rate),
            'checkins_over_time_json': json.dumps(checkins_over_time),
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        organizer = self.request.organizer

        cache = organizer.cache
        cache_key = f'organizer_analytics_{organizer.pk}_{self.request.user.pk}'
        cached = cache.get(cache_key)

        if 'refresh' in self.request.GET:
            cached = None

        if cached:
            ctx.update(cached)
            return ctx

        data = {}
        data.update(self._get_tickets_data())
        data.update(self._get_proposals_data())
        data.update(self._get_checkins_data())

        cache.set(cache_key, data, 600)
        ctx.update(data)
        return ctx

import datetime
import json

import dateutil.rrule
from django.db.models import (
    Count,
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
    Event,
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
                .values('day', 'order__event__currency')
                .annotate(
                    cnt=Count('order', distinct=True),
                    revenue=Sum('amount')
                )
                .order_by('day')
            )
            payment_data = list(payment_day_qs)
            paid_by_day = {}
            rev_by_day = {}
            currencies = set()
            for row in payment_data:
                day = row['day']
                currency = row['order__event__currency']
                paid_by_day[day] = paid_by_day.get(day, 0) + row['cnt']
                currencies.add(currency)
                day_revenue = rev_by_day.setdefault(day, {})
                day_revenue[currency] = float(row['revenue'] or 0)

            status_qs = (
                Order.objects.filter(event_id__in=event_ids)
                .values('status')
                .annotate(cnt=Count('pk'))
            )
            status_rows = list(status_qs)

            top_qs = list(
                Order.objects.filter(event_id__in=event_ids)
                .values('event')
                .annotate(
                    total_orders=Count('pk'),
                    paid_orders=Count('pk', filter=Q(status=Order.STATUS_PAID)),
                )
                .order_by('-total_orders')[:10]
            )
            top_event_ids = [row['event'] for row in top_qs]
            events_by_id = {
                e.pk: e for e in Event.objects.filter(pk__in=top_event_ids)
            }

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
        start_date = timezone.localdate(since, timezone=tz)
        end_date = timezone.localdate(timezone=tz)
        for d in dateutil.rrule.rrule(dateutil.rrule.DAILY, dtstart=start_date, until=end_date):
            d = d.date()
            orders_over_time.append({
                'x': d.strftime('%Y-%m-%d'),
                'ordered': ordered_by_day.get(d, 0),
                'paid': paid_by_day.get(d, 0)
            })

        label_map = dict(Order.STATUS_CHOICE)
        orders_by_status = [
            {'label': str(label_map.get(row['status'], row['status'])), 'value': row['cnt']}
            for row in status_rows
            if row['cnt'] > 0
        ]

        revenue_over_time = []
        sorted_currencies = sorted(currencies)
        cumulative = {curr: 0.0 for curr in sorted_currencies}
        for d in dateutil.rrule.rrule(dateutil.rrule.DAILY, dtstart=start_date, until=end_date):
            d = d.date()
            day_data = {'x': d.strftime('%Y-%m-%d')}
            day_revs = rev_by_day.get(d, {})
            for curr in sorted_currencies:
                cumulative[curr] += day_revs.get(curr, 0.0)
                day_data[curr] = round(cumulative[curr], 2)
            revenue_over_time.append(day_data)

        top_events = [
            {
                'name': str(events_by_id[row['event']].name),
                'slug': events_by_id[row['event']].slug,
                'total_orders': row['total_orders'],
                'paid_orders': row['paid_orders'],
                'gross_revenue': float(event_revenue.get(row['event'], 0) or 0),
                'currency': events_by_id[row['event']].currency,
            }
            for row in top_qs
            if row['event'] in events_by_id
        ]

        return {
            'orders_over_time_json': json.dumps(orders_over_time),
            'orders_by_status_json': json.dumps(orders_by_status),
            'revenue_over_time_json': json.dumps(revenue_over_time),
            'currencies_json': json.dumps(sorted_currencies),
            'top_events': top_events,
            'has_orders': bool(status_rows),
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

            timeline_qs = list(
                Submission.objects.filter(
                    event_id__in=event_ids,
                    created__gte=since,
                )
                .annotate(day=TruncDate('created', tzinfo=tz))
                .values('day')
                .annotate(cnt=Count('pk'))
                .order_by('day')
            )
            by_day = {row['day']: row['cnt'] for row in timeline_qs}
            proposals_over_time = []
            start_date = timezone.localdate(since, timezone=tz)
            end_date = timezone.localdate(timezone=tz)
            for d in dateutil.rrule.rrule(dateutil.rrule.DAILY, dtstart=start_date, until=end_date):
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
                .values('order__event_id')
                .annotate(
                    total=Count('pk'),
                    checked_in=Count('pk', filter=Q(checkedin=True))
                )
            )
            checkin_event_ids = [row['order__event_id'] for row in stats_qs]
            events_by_id = {
                e.pk: e for e in Event.objects.filter(pk__in=checkin_event_ids)
            }
            for row in stats_qs:
                event_id = row['order__event_id']
                if event_id in events_by_id:
                    event_stats[event_id] = {
                        'event': str(events_by_id[event_id].name),
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
        start_date = timezone.localdate(since, timezone=tz)
        end_date = timezone.localdate(timezone=tz)
        for d in dateutil.rrule.rrule(dateutil.rrule.DAILY, dtstart=start_date, until=end_date):
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
        cache_key = f'organizer_analytics_{organizer.pk}_{self.request.user.pk}_{self.request.LANGUAGE_CODE}'
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

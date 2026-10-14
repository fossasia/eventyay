"""Presentation and activity aggregates for the administrator dashboard."""

from datetime import UTC, timedelta
from decimal import Decimal

from django.db.models import Count, Min, Sum
from django.db.models.functions import TruncDay, TruncHour, TruncMonth
from django.urls import reverse
from django.utils.timezone import localtime, now
from django.utils.translation import gettext_lazy as _
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Order, OrderPayment, User


ACTIVITY_RANGES = {'24h': 1, '7d': 7, '30d': 30, '90d': 90, 'all': None}


def activity_context(selected_range='30d'):
    """Aggregate platform activity in bounded time buckets, separating currencies."""
    selected_range = selected_range if selected_range in ACTIVITY_RANGES else '30d'
    end = now().astimezone(UTC) if selected_range == '24h' else localtime(now())
    days = ACTIVITY_RANGES[selected_range]
    truncate = TruncHour if selected_range == '24h' else TruncMonth if days is None else TruncDay
    with scopes_disabled():
        sources = [
            ('orders', _('Orders over time'), Order.objects.all(), 'datetime'),
            (
                'revenue',
                _('Revenue over time'),
                OrderPayment.objects.filter(state=OrderPayment.PAYMENT_STATE_CONFIRMED),
                'payment_date',
            ),
            ('users', _('New users over time'), User.objects.all(), 'date_joined'),
            ('events', _('Events created over time'), Event.objects.all(), 'created'),
        ]
        if days is None:
            earliest = [query.aggregate(first=Min(field))['first'] for _, _, query, field in sources]
            start = localtime(min([value for value in earliest if value] + [end])).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
        else:
            start = (end - timedelta(days=days - (selected_range != '24h'))).replace(minute=0, second=0, microsecond=0)
            if selected_range != '24h':
                start = start.replace(hour=0)
        query_start = end - timedelta(hours=24) if selected_range == '24h' else start
        buckets = []
        cursor = start
        while cursor <= end:
            buckets.append(cursor)
            if days is None:
                cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
            else:
                cursor += timedelta(hours=1) if selected_range == '24h' else timedelta(days=1)
        charts = []
        for key, title, query, field in sources:
            filtered = query.filter(**{f'{field}__gte': query_start, f'{field}__lte': end})
            group_fields = ['bucket', 'order__event__currency'] if key == 'revenue' else ['bucket']
            rows = (
                filtered.annotate(bucket=truncate(field, tzinfo=end.tzinfo))
                .values(*group_fields)
                .annotate(value=Sum('amount') if key == 'revenue' else Count('pk'))
                .order_by('bucket')
            )
            grouped = {}
            for row in rows:
                currency = row.get('order__event__currency', '')
                grouped.setdefault(currency, {})[row['bucket']] = row['value']
            series = []
            for currency, values in sorted(grouped.items()) or [('', {})]:
                points = [values.get(bucket, Decimal('0')) for bucket in buckets]
                maximum = max(points, default=0) or 1
                series.append(
                    {
                        'currency': currency,
                        'total': sum(points),
                        'maximum': maximum,
                        'points': ' '.join(
                            f'{10 + index * 280 / max(len(points) - 1, 1):.2f},{100 - float(value / maximum) * 90:.2f}'
                            for index, value in enumerate(points)
                        ),
                        'rows': list(zip(buckets, points)),
                    }
                )
            charts.append(
                {
                    'key': key,
                    'title': title,
                    'series': series,
                    'start': query_start,
                    'end': end,
                    'url': reverse('eventyay_admin:admin.analytics.metric', kwargs={'metric': key})
                    + f'?range={selected_range}',
                }
            )
    return {
        'activity_charts': charts,
        'activity_range': selected_range,
        'activity_ranges': [(key, _('All time') if key == 'all' else key) for key in ACTIVITY_RANGES],
        'last_updated': end,
    }


def dashboard_cards(ctx):
    """Map measured dashboard values to summaries and existing detail pages."""
    routes = {
        key: reverse(f'eventyay_admin:admin.{key}')
        for key in (
            'users',
            'events',
            'organizers',
            'orders',
            'submissions',
            'attendees',
            'operations',
            'task_management',
        )
    }
    metrics = [
        ('users_total', _('Users'), 'users', 'users'),
        ('events_total', _('Events'), 'events', 'calendar'),
        ('organizers_total', _('Organizers'), 'organizers', 'building'),
        ('orders_total', _('Orders'), 'orders', 'shopping-cart'),
        ('tickets_issued', _('Tickets issued'), 'attendees', 'ticket'),
        ('sessions_total', _('Sessions'), 'submissions', 'desktop'),
        ('speakers_total', _('Speakers'), 'submissions', 'microphone'),
        ('attendees_total', _('Attendees'), 'attendees', 'users'),
    ]
    ctx['metric_cards'] = [
        {'value': ctx[key], 'label': label, 'url': routes[route], 'icon': icon} for key, label, route, icon in metrics
    ]
    ctx['metric_cards'].insert(
        4,
        {
            'kind': 'revenue',
            'revenues': ctx['orders_revenue'],
            'label': _('Revenue'),
            'icon': 'money',
            'url': reverse('eventyay_admin:admin.analytics.metric', kwargs={'metric': 'revenue'}),
        },
    )
    ctx['action_cards'] = [
        {
            'value': ctx.get('email_unsent_count'),
            'label': _('Unsent emails'),
            'icon': 'envelope-o',
            'url': routes['operations'] + '#admin-email-config-heading',
            'link': _('View emails'),
        },
        {
            'value': None,
            'label': _('Failed tasks (last 24 hours)'),
            'icon': 'exclamation-triangle',
            'url': routes['task_management'],
            'link': _('View tasks'),
        },
        {
            'value': ctx.get('refunds_pending_count'),
            'label': _('Refunds pending'),
            'icon': 'undo',
            'url': routes['orders'],
            'link': _('View orders'),
        },
        {
            'value': ctx['events_missing_payment_count'],
            'label': _('Events missing payment setup'),
            'icon': 'calendar',
            'url': routes['operations'] + '#admin-events-heading',
            'link': _('View events'),
        },
        {
            'value': ctx.get('active_tokens'),
            'label': _('Active API tokens'),
            'icon': 'key',
            'url': routes['operations'] + '#admin-api-heading',
            'link': _('View tokens'),
        },
    ]
    ctx['programme_rows'] = [
        (_('Total proposals'), ctx['sessions_total_submitted']),
        (_('Accepted'), ctx['sessions_accepted']),
        (_('Confirmed'), ctx['sessions_confirmed']),
        (_('Pending'), ctx['sessions_submitted']),
        (_('Rejected'), ctx['sessions_rejected']),
        (_('Total speakers'), ctx['speakers_total']),
        (_('Confirmed speakers'), ctx['speakers_confirmed']),
        (_('Unconfirmed speakers'), ctx['speakers_unconfirmed']),
    ]
    health = [
        (_('Celery tasks active'), ctx.get('celery_depth'), False),
        (_('Failed tasks (last 24 hours)'), None, True),
        (_('Failed payments (last 24 hours)'), ctx.get('payments_failed_24h'), True),
        (_('Failed webhooks (last 24 hours)'), ctx.get('webhook_failed_24h'), True),
        (_('Unsent emails'), ctx.get('email_unsent_count'), True),
        (_('Active check-in devices'), ctx.get('active_devices_count'), False),
    ]
    ctx['health_rows'] = [
        {
            'label': label,
            'value': value,
            'status': _('Warning') if value is None or (failure and value) else _('OK'),
            'style': 'warning' if value is None or (failure and value) else 'success',
        }
        for label, value, failure in health
    ]
    for row in ctx['health_rows']:
        if row['value'] is None:
            row['status'] = _('Not available')
    if ctx.get('platform_health_unavailable') or ctx.get('celery_depth_unavailable'):
        ctx['health_rows'][0].update(status=_('Error'), style='danger')
    config_unavailable = ctx.get('config_status_unavailable', False)
    configurations = [
        (_('SMTP / Email'), ctx.get('config_smtp_ok'), config_unavailable),
        (_('SSO / Social authentication'), ctx.get('config_sso_ok'), config_unavailable),
        (_('Video'), ctx.get('config_video_ok'), False),
        (
            _('API & Webhooks'),
            ctx.get('active_webhooks_count') or ctx.get('active_tokens'),
            ctx.get('api_status_unavailable', False),
        ),
    ]
    ctx['configuration_rows'] = [
        {
            'label': label,
            'status': _('Error') if unavailable else _('Configured') if configured else _('Needs setup'),
            'style': 'danger' if unavailable else 'success' if configured else 'warning',
        }
        for label, configured, unavailable in configurations
    ]

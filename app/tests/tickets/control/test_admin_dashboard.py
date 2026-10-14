from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import Event, Order, OrderPayment, Organizer, User
from eventyay.control.platform_dashboard import activity_context, dashboard_cards


@pytest.fixture
def dashboard_admin(client, db):
    user = User.objects.create_user('dashboard-admin@example.test', 'test', is_staff=True)
    client.force_login(user)
    user.staffsession_set.create(date_start=now(), session_key=client.session.session_key)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize('period, expected', [('24h', 25), ('7d', 7), ('30d', 30), ('90d', 90), ('bad', 30)])
def test_activity_ranges_zero_fill_empty_days(period, expected):
    data = activity_context(period)
    assert len(data['activity_charts']) == 4
    for chart in data['activity_charts']:
        assert len(chart['series'][0]['rows']) == expected
        assert chart['series'][0]['total'] == 0


@pytest.mark.django_db
def test_activity_separates_currencies_and_uses_payment_date():
    organizer = Organizer.objects.create(name='Dashboard tests', slug='dashboard-tests')
    for currency, amount in [('EUR', Decimal('12')), ('USD', Decimal('18'))]:
        event = Event.objects.create(
            organizer=organizer, name=currency, slug=currency.lower(), currency=currency, date_from=now()
        )
        with scope(event=event, organizer=organizer):
            order = Order.objects.create(
                event=event, total=amount, status=Order.STATUS_PAID, datetime=now(), email='buyer@example.test'
            )
            OrderPayment.objects.create(
                order=order,
                amount=amount,
                provider='manual',
                state=OrderPayment.PAYMENT_STATE_CONFIRMED,
                payment_date=now(),
            )
            OrderPayment.objects.create(
                order=order, amount=100, provider='manual', state=OrderPayment.PAYMENT_STATE_FAILED, payment_date=now()
            )
            OrderPayment.objects.create(
                order=order,
                amount=200,
                provider='manual',
                state=OrderPayment.PAYMENT_STATE_CONFIRMED,
                payment_date=now() - timedelta(days=100),
            )
    charts = {chart['key']: chart for chart in activity_context()['activity_charts']}
    assert charts['orders']['series'][0]['total'] == 2
    assert charts['events']['series'][0]['total'] == 2
    assert {series['currency']: series['total'] for series in charts['revenue']['series']} == {
        'EUR': Decimal('12'),
        'USD': Decimal('18'),
    }
    all_time = {chart['key']: chart for chart in activity_context('all')['activity_charts']}
    assert all_time['revenue']['series'][0]['total'] == Decimal('212')


@pytest.mark.django_db
def test_hourly_activity_excludes_records_older_than_24_hours(settings):
    settings.TIME_ZONE = 'Europe/Berlin'
    end = datetime(2026, 10, 25, 12, 30, tzinfo=UTC)
    for index, age in enumerate((timedelta(hours=24, minutes=1), timedelta(hours=23), timedelta(hours=1))):
        user = User.objects.create_user(f'boundary-{index}@example.test')
        User.objects.filter(pk=user.pk).update(date_joined=end - age)
    with patch('eventyay.control.platform_dashboard.now', return_value=end):
        users = next(chart for chart in activity_context('24h')['activity_charts'] if chart['key'] == 'users')
    assert users['series'][0]['total'] == 2
    assert users['start'] == end - timedelta(hours=24)


@pytest.mark.django_db
def test_dashboard_and_analytics_require_admin_session(client):
    user = User.objects.create_user('ordinary@example.test', 'test')
    client.force_login(user)
    for path in ('admin.dashboard', 'admin.analytics', 'admin.operations'):
        assert client.get(reverse(f'eventyay_admin:{path}')).status_code == 403
    user.is_staff = True
    user.save(update_fields=['is_staff'])
    assert client.get(reverse('eventyay_admin:admin.analytics')).status_code == 302


@pytest.mark.django_db
def test_dashboard_sections_and_analytics_render(dashboard_admin, settings):
    settings.HAS_CELERY = False
    response = dashboard_admin.get(reverse('eventyay_admin:admin.dashboard'))
    assert response.status_code == 200
    html = response.content.decode()
    for heading in (
        'Platform Dashboard',
        'Action required',
        'System health',
        'Events overview',
        'Programme overview',
        'Configuration status',
        'Tickets issued',
    ):
        assert heading in html
    assert html.count('data-expand-chart=') == 4
    assert 'Enabled Periodic Tasks' not in html
    assert len(response.context['metric_cards']) == 9
    navigation = {str(item['label']): item for item in response.context['admin_nav_items']}
    assert [str(item['label']) for item in navigation['Video']['children']] == [
        'Dashboard',
        'Events',
        'Settings',
        'System log',
    ]
    assert [str(item['label']) for item in navigation['System']['children']] == [
        'System operations',
        'Tasks & queues',
        'Logs',
    ]
    assert 'Platform data' in navigation
    unavailable = dict(response.context_data)
    unavailable['config_status_unavailable'] = True
    dashboard_cards(unavailable)
    assert str(unavailable['configuration_rows'][0]['status']) == 'Error'
    assert unavailable['configuration_rows'][0]['style'] == 'danger'
    for metric in ('orders', 'revenue', 'users', 'events'):
        url = reverse('eventyay_admin:admin.analytics.metric', kwargs={'metric': metric})
        detail = dashboard_admin.get(url + '?range=7d')
        assert detail.status_code == 200
        assert len(detail.context['activity_charts']) == 1
    assert dashboard_admin.get('/admin/analytics/unknown/').status_code == 404
    assert dashboard_admin.get(reverse('eventyay_admin:admin.operations')).status_code == 200
    with patch('eventyay.control.views.admin.cache.delete_many') as clear:
        assert dashboard_admin.post(reverse('eventyay_admin:admin.dashboard'), {'action': 'refresh'}).status_code == 302
        clear.assert_called_once()

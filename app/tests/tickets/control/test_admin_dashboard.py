from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup
from django.http import HttpResponse
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope
from redis.exceptions import RedisError

from eventyay.base.models import Event, Order, OrderPayment, Organizer, Room, StreamSchedule, User
from eventyay.control.platform_dashboard import activity_context, dashboard_cards


@pytest.fixture
def dashboard_admin(client, db):
    """Authenticate a staff user with an active administrator session."""
    user = User.objects.create_user('dashboard-admin@example.test', 'test', is_staff=True)
    client.force_login(user)
    user.staffsession_set.create(date_start=now(), session_key=client.session.session_key)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize('period, expected', [('24h', 25), ('7d', 7), ('30d', 30), ('90d', 90), ('bad', 30)])
def test_activity_ranges_zero_fill_empty_days(period, expected):
    """Keep each activity range complete even when there are no records."""
    data = activity_context(period)
    assert len(data['activity_charts']) == 4
    for chart in data['activity_charts']:
        assert len(chart['series'][0]['rows']) == expected
        assert chart['series'][0]['total'] == 0


@pytest.mark.django_db
def test_activity_separates_currencies_and_uses_payment_date():
    """Aggregate confirmed payments by currency and their payment timestamp."""
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
    """Apply the rolling daily boundary across a daylight-saving transition."""
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
    """Deny ordinary users and require staff to start an administrator session."""
    user = User.objects.create_user('ordinary@example.test', 'test')
    client.force_login(user)
    for path in ('admin.dashboard', 'admin.analytics', 'admin.operations', 'video_admin:settings'):
        assert client.get(reverse(f'eventyay_admin:{path}')).status_code == 403
    user.is_staff = True
    user.save(update_fields=['is_staff'])
    assert client.get(reverse('eventyay_admin:admin.analytics')).status_code == 302


@pytest.mark.django_db
def test_dashboard_sections_and_analytics_render(dashboard_admin, settings):
    """Render the required sections, analytics links, navigation and refresh routes."""
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
        'Revenue & Orders by Currency',
        'Recent transactions',
        'Top events by paid orders',
        'Payment providers',
        'Upcoming events',
        'Recently created events',
    ):
        assert heading in html
    assert html.count('data-expand-chart=') == 4
    assert response.context['activity_range'] == '30d'
    assert all(len(chart['series'][0]['rows']) == 30 for chart in response.context['activity_charts'])
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
        for route in ('admin.dashboard', 'admin.operations'):
            clear.reset_mock()
            url = reverse(f'eventyay_admin:{route}')
            result = dashboard_admin.post(url, {'action': 'refresh'})
            assert result.status_code == 302
            assert result.url == url
            clear.assert_called_once()


@pytest.mark.django_db
def test_system_navigation_active_on_logs(dashboard_admin):
    """Keep the System parent and its Logs child active on the same route."""
    response = dashboard_admin.get(reverse('eventyay_admin:video_admin:systemlog.list'))
    assert response.status_code == 200
    system = next(item for item in response.context['admin_nav_items'] if str(item['label']) == 'System')
    assert system['active']
    assert system['children'][2]['active']


@pytest.mark.django_db
@pytest.mark.parametrize('api_ok, failed_tasks', ((True, 0), (False, 3), (True, None)))
def test_dashboard_reports_measured_health(dashboard_admin, settings, mocker, api_ok, failed_tasks):
    """Show measured task failures and readiness, including unavailable failure history."""
    settings.HAS_CELERY = False
    failure_counter = mocker.patch('eventyay.control.views.admin.task_failure_count')
    if failed_tasks is None:
        failure_counter.side_effect = RedisError('Failure store unavailable')
    else:
        failure_counter.return_value = failed_tasks
    mocker.patch('eventyay.control.views.admin.healthcheck', return_value=HttpResponse(status=200 if api_ok else 503))
    response = dashboard_admin.get(reverse('eventyay_admin:admin.dashboard'))
    assert response.status_code == 200
    rows = {str(row['label']): row for row in response.context['health_rows']}
    assert rows['Failed tasks (last 24 hours)']['value'] == failed_tasks
    assert str(rows['API status']['status']) == ('OK' if api_ok else 'Error')
    assert response.context['action_cards'][1]['value'] == failed_tasks
    if failed_tasks is None:
        assert str(rows['Failed tasks (last 24 hours)']['status']) == 'Not available'


@pytest.mark.django_db
def test_dashboard_reports_include_all_records(dashboard_admin):
    """Keep reports complete and paginated while separating same-named events."""
    organizer = Organizer.objects.create(name='Reports', slug='reports')
    for index in range(27):
        event = Event.objects.create(organizer=organizer, name='Same name', slug=f'event-{index}', date_from=now())
        with scope(event=event, organizer=organizer):
            order = Order.objects.create(event=event, total=10, status=Order.STATUS_PAID)
            for _ in range(2):
                OrderPayment.objects.create(order=order, amount=5, state=OrderPayment.PAYMENT_STATE_CONFIRMED,
                                            provider=f'provider-{index}', payment_date=now())
    for metric in ('top-events', 'providers', 'needs-setup'):
        url = reverse('eventyay_admin:admin.analytics.metric', kwargs={'metric': metric})
        response = dashboard_admin.get(url)
        assert response.status_code == 200
        assert response.context['report_page'].paginator.count == 27
        assert len(response.context['report_rows']) == 25
        assert len(dashboard_admin.get(url + '?page=2').context['report_rows']) == 2
        if metric in ('top-events', 'providers'):
            assert all(row[-1] == 1 for row in response.context['report_rows'])


@pytest.mark.django_db
@pytest.mark.parametrize('workers, expected', ((None, None), ({}, 0), ({'worker': [{}, {}]}, 2)))
def test_dashboard_distinguishes_idle_and_unavailable_workers(dashboard_admin, settings, mocker, workers, expected):
    """An inspection with no worker response must not appear as a healthy zero."""
    settings.HAS_CELERY = True
    mocker.patch('eventyay.control.views.admin.app.control.inspect').return_value.active.return_value = workers
    mocker.patch('eventyay.control.views.admin.cache.get_or_set', side_effect=lambda key, default, timeout: default())
    mocker.patch('eventyay.control.views.admin.task_failure_count', return_value=0)
    mocker.patch('eventyay.control.views.admin.healthcheck', return_value=HttpResponse(status=200))
    response = dashboard_admin.get(reverse('eventyay_admin:admin.dashboard'))
    assert response.status_code == 200
    assert response.context['celery_depth'] == expected
    assert response.context['celery_depth_unavailable'] is (workers is None)
    row = response.context['health_rows'][0]
    assert str(row['status']) == ('Error' if workers is None else 'OK')


@pytest.mark.django_db
def test_video_settings_manage_streams(dashboard_admin, mocker, django_capture_on_commit_callbacks):
    """Configure streams on Video settings and keep event ownership and room validation intact."""
    organizer = Organizer.objects.create(name='Video settings', slug='video-settings')
    event = Event.objects.create(organizer=organizer, name='Streaming demo', slug='streaming', date_from=now())
    other_event = Event.objects.create(organizer=organizer, name='Other event', slug='other', date_from=now())
    with scope(event=event):
        room = Room.objects.create(event=event, name='Stream room')
    with scope(event=other_event):
        other_room = Room.objects.create(event=other_event, name='Other room')
    url = reverse('eventyay_admin:video_admin:settings') + f'?tab=streaming&event={event.pk}'
    assert dashboard_admin.get(url).status_code == 200
    data = {'stream_action': 'save', 'room': room.pk, 'title': 'Demo stream',
            'url': 'https://www.youtube.com/watch?v=example', 'stream_type': 'youtube',
            'start_time': (now() + timedelta(days=1)).isoformat(),
            'end_time': (now() + timedelta(days=1, hours=1)).isoformat(), 'config': '{}'}
    broadcast = mocker.patch('eventyay.control.views.admin_views.notify_admin_stream_change')
    with django_capture_on_commit_callbacks(execute=True):
        response = dashboard_admin.post(url, data)
    assert response.status_code == 302
    assert response.url == url
    broadcast.assert_called_once()
    stream = StreamSchedule.objects.get(room=room)
    edit_url = url + f'&stream={stream.pk}'
    data['title'] = 'Updated stream'
    assert dashboard_admin.post(edit_url, data).status_code == 302
    stream.refresh_from_db()
    assert stream.title == 'Updated stream'
    for change, field in (
        ({'start_time': ''}, 'start_time'),
        ({'room': other_room.pk}, 'room'),
        ({'end_time': data['start_time']}, 'end_time'),
        ({'config': '[]'}, 'config'),
        ({}, '__all__'),
    ):
        response = dashboard_admin.post(url, dict(data, **change))
        assert response.status_code == 200
        assert field in response.context['streaming_form'].errors
    assert StreamSchedule.objects.count() == 1
    assert dashboard_admin.get(url.replace(f'event={event.pk}', f'event={other_event.pk}')
                               + f'&stream={stream.pk}').status_code == 404
    assert dashboard_admin.post(edit_url, {'stream_action': 'delete'}).status_code == 302
    assert not StreamSchedule.objects.filter(pk=stream.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize('deleted_room', (False, True))
def test_video_settings_preserve_stream_times_and_existing_room(dashboard_admin, deleted_room):
    """Round-trip a sub-minute stream, including its existing soft-deleted room."""
    organizer = Organizer.objects.create(name='Stream edits', slug='stream-edits')
    event = Event.objects.create(organizer=organizer, name='Stream edits', slug='stream-edits', date_from=now())
    start = (now() + timedelta(days=1)).replace(second=17, microsecond=0)
    end = start + timedelta(seconds=11)
    with scope(event=event):
        room = Room.objects.create(event=event, name='Current room', deleted=deleted_room)
        other_room = Room.objects.create(event=event, name='Deleted room', deleted=True)
        stream = StreamSchedule.objects.create(
            room=room, title='Original title', url='https://www.youtube.com/watch?v=example',
            stream_type='youtube', start_time=start, end_time=end,
        )
    url = reverse('eventyay_admin:video_admin:settings') + f'?tab=streaming&event={event.pk}'
    edit_url = url + f'&stream={stream.pk}'
    response = dashboard_admin.get(edit_url)
    assert response.status_code == 200
    page = BeautifulSoup(response.content, 'html.parser')
    times = {field: page.find(id=f'id_{field}') for field in ('start_time', 'end_time')}
    assert times['start_time']['value'].endswith(':17')
    assert times['end_time']['value'].endswith(':28')
    assert all(widget['step'] == '1' for widget in times.values())
    room_choices = {option['value'] for option in page.select('#id_room option')}
    assert str(room.pk) in room_choices
    assert str(other_room.pk) not in room_choices
    assert page.find(id='id_room').has_attr('disabled')
    response = dashboard_admin.post(edit_url, {
        'stream_action': 'save', 'title': 'Updated title', 'room': room.pk,
        'url': stream.url, 'stream_type': stream.stream_type, 'config': '{}',
        **{field: widget['value'] for field, widget in times.items()},
    })
    assert response.status_code == 302
    stream.refresh_from_db()
    assert (stream.title, stream.room_id, stream.start_time, stream.end_time) == (
        'Updated title', room.pk, start, end,
    )
    page = BeautifulSoup(dashboard_admin.get(url).content, 'html.parser')
    new_choices = {option['value'] for option in page.select('#id_room option')}
    assert (str(room.pk) in new_choices) is not deleted_room
    assert str(other_room.pk) not in new_choices


@pytest.mark.django_db
@pytest.mark.parametrize('metric', ('orders', 'users', 'events', 'revenue'))
def test_analytics_formats_money_and_counts(dashboard_admin, metric):
    """Display integer activity counts while retaining cents for revenue."""
    organizer = Organizer.objects.create(name='Analytics values', slug='analytics-values')
    event = Event.objects.create(
        organizer=organizer, name='Analytics values', slug='analytics-values', date_from=now(), currency='EUR',
    )
    with scope(event=event, organizer=organizer):
        order = Order.objects.create(event=event, total=Decimal('12.50'), status=Order.STATUS_PAID)
        OrderPayment.objects.create(
            order=order, provider='manual', state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            amount=Decimal('12.50'), payment_date=now(),
        )
    response = dashboard_admin.get(reverse('eventyay_admin:admin.analytics.metric', kwargs={'metric': metric}))
    assert response.status_code == 200
    page = BeautifulSoup(response.content, 'html.parser')
    values = [cell.get_text(strip=True) for cell in page.select('details table tbody tr td:last-child')]
    assert values
    if metric == 'revenue':
        assert '12.50' in values
    else:
        assert '1' in values
        assert all('.' not in value for value in values)

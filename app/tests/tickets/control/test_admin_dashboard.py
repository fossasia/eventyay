from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope
from redis.exceptions import RedisError

from eventyay.base.models import (
    Event,
    JitsiServer,
    Order,
    OrderPayment,
    Organizer,
    Product,
    Room,
    StreamSchedule,
    SystemLog,
    User,
)
from eventyay.control.forms.server_management import VideoStreamingSelectionForm, VideoStreamScheduleForm
from eventyay.control.platform_dashboard import (
    ACTIVITY_RANGES,
    activity_context,
    cached_dashboard_context,
    dashboard_cards,
    setup_events,
)


@pytest.fixture
def dashboard_admin(client, db):
    """Authenticate a staff user with an active administrator session."""
    user = User.objects.create_user('dashboard-admin@example.test', 'test', is_staff=True)
    client.force_login(user)
    user.staffsession_set.create(date_start=now(), session_key=client.session.session_key)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize('period, expected', [('24h', 24), ('7d', 7), ('30d', 30), ('90d', 90), ('bad', 30)])
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
@pytest.mark.parametrize('end', (
    datetime(2026, 10, 25, 12, 30, tzinfo=UTC),
    datetime(2026, 10, 25, 0, 0, tzinfo=UTC),
))
def test_hourly_activity_excludes_records_older_than_24_hours(settings, end):
    """Use 24 aligned UTC buckets, including activity in the current partial hour."""
    settings.TIME_ZONE = 'Europe/Berlin'
    last_bucket = end.replace(minute=0, second=0, microsecond=0)
    start = last_bucket - timedelta(hours=23)
    timestamps = (
        start - timedelta(microseconds=1), start, start + timedelta(minutes=30),
        end - timedelta(minutes=1), end, end + timedelta(microseconds=1),
    )
    for index, timestamp in enumerate(timestamps):
        user = User.objects.create_user(f'boundary-{index}@example.test')
        User.objects.filter(pk=user.pk).update(date_joined=timestamp)
    with patch('eventyay.control.platform_dashboard.now', return_value=end):
        users = next(chart for chart in activity_context('24h')['activity_charts'] if chart['key'] == 'users')
    rows = dict(users['series'][0]['rows'])
    assert len(rows) == 24
    assert list(rows) == [start + timedelta(hours=index) for index in range(24)]
    assert rows[start] == 2
    assert rows[last_bucket] == (2 if end.minute else 1)
    assert users['series'][0]['total'] == 4
    assert users['start'] == start
    assert users['end'] == end


@pytest.mark.django_db
def test_dashboard_and_analytics_require_admin_session(client):
    """Deny ordinary users and require staff to start an administrator session."""
    user = User.objects.create_user('ordinary@example.test', 'test')
    client.force_login(user)
    for path in ('admin.dashboard', 'admin.analytics', 'admin.operations', 'video_admin:settings'):
        assert client.get(reverse(f'eventyay_admin:{path}')).status_code == 403
    for metric in ('orders', 'revenue', 'users', 'events', 'top-events', 'providers', 'needs-setup', 'missing-payment'):
        url = reverse('eventyay_admin:admin.analytics.metric', kwargs={'metric': metric})
        assert client.get(url).status_code == 403
    for action in ('save', 'delete'):
        assert client.post(reverse('eventyay_admin:video_admin:settings'), {
            'stream_action': action,
        }).status_code == 403
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
    sidebar = BeautifulSoup(html, 'html.parser').select_one('.sidebar')
    assert sidebar.find('a')['href'] == reverse('eventyay_admin:admin.dashboard')
    assert [str(item['label']) for item in navigation['Video']['children']] == [
        'Dashboard',
        'Events',
        'Settings',
    ]
    assert [str(item['label']) for item in navigation['System']['children']] == [
        'System operations',
        'Tasks & queues',
        'Logs',
    ]
    assert 'Platform data' in navigation
    voucher_url = reverse('eventyay_admin:admin.vouchers')
    voucher_labels = [
        str(item['label']) for group in navigation.values() for item in group.get('children', [])
        if item['url'] == voucher_url
    ]
    assert voucher_labels == ['Event vouchers']
    unavailable = dict(response.context_data)
    unavailable['config_status_unavailable'] = True
    dashboard_cards(unavailable)
    assert str(unavailable['configuration_rows'][0]['status']) == 'Error'
    assert unavailable['configuration_rows'][0]['style'] == 'danger'
    partial = dict(response.context_data)
    partial.pop('events_missing_payment_count')
    dashboard_cards(partial)
    assert partial['action_cards'][3]['value'] == 0
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
            keys = clear.call_args.args[0]
            assert {'admin_dashboard_common', 'admin_dashboard_operations', 'admin_dashboard_counts',
                    'admin_dashboard_health'} <= set(keys)
            assert all(f'admin_dashboard_activity_{period}' in keys for period in ACTIVITY_RANGES)


@pytest.mark.django_db
@pytest.mark.parametrize('detail', (False, True))
def test_system_navigation_active_on_logs(dashboard_admin, detail):
    """Show one log link and activate only System on log lists and details."""
    log_url = reverse('eventyay_admin:video_admin:systemlog.list')
    if detail:
        entry = SystemLog.objects.create(module='navigation-test', message='Test entry', trace='{}')
        url = reverse('eventyay_admin:video_admin:systemlog.detail', kwargs={'pk': entry.pk})
    else:
        url = log_url
    response = dashboard_admin.get(url)
    assert response.status_code == 200
    navigation = {str(item['label']): item for item in response.context['admin_nav_items']}
    assert navigation['System']['active']
    assert navigation['System']['children'][2]['active']
    assert not navigation['Video']['active']
    assert not any(item['active'] for item in navigation['Video']['children'])
    sidebar = BeautifulSoup(response.content, 'html.parser').select_one('.sidebar')
    assert len(sidebar.find_all('a', href=log_url)) == 1


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
    mocker.patch('eventyay.control.views.admin.check_dependencies', return_value=None if api_ok else 'db_unavailable')
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
    mocker.patch('eventyay.control.views.admin.check_dependencies', return_value=None)
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


@pytest.mark.django_db
def test_setup_events_without_an_active_scope(dashboard_admin):
    """Build and evaluate the platform setup report outside any event scope."""
    organizer = Organizer.objects.create(name='Setup report', slug='setup-report')
    events = {}
    for kind in ('empty', 'free', 'paid', 'configured'):
        event = Event.objects.create(organizer=organizer, name=kind, slug=kind, date_from=now())
        events[kind] = event
        with scope(event=event, organizer=organizer):
            if kind != 'empty':
                Product.objects.create(event=event, name='Ticket', default_price=0 if kind == 'free' else 10)
            if kind == 'configured':
                event.settings.set('payment_manual__enabled', True)
    assert set(setup_events().values_list('pk', flat=True)) == {events['empty'].pk, events['paid'].pk}
    dashboard = dashboard_admin.get(reverse('eventyay_admin:admin.dashboard'))
    card = dashboard.context['action_cards'][3]
    assert card['value'] == 1
    report = dashboard_admin.get(card['url'])
    assert report.status_code == 200
    assert report.context['report_rows'] == [['paid', 'Setup report']]


@pytest.mark.django_db
@pytest.mark.parametrize('config', (None, '', 'null', '{}', '""'))
@pytest.mark.parametrize('existing', (False, True))
def test_stream_form_accepts_empty_config(config, existing):
    """Clear submitted empty configuration while preserving an omitted edit field."""
    organizer = Organizer.objects.create(name='Empty config', slug='empty-config')
    event = Event.objects.create(organizer=organizer, name='Empty config', slug='empty-config', date_from=now())
    start = now() + timedelta(days=1)
    with scope(event=event, organizer=organizer):
        room = Room.objects.create(event=event, name='Stream room')
        data = {
            'room': room.pk, 'url': 'https://example.com/live', 'stream_type': 'hls',
            'start_time': start.isoformat(), 'end_time': (start + timedelta(hours=1)).isoformat(),
        }
        if config is not None:
            data['config'] = config
        instance = StreamSchedule.objects.create(
            room=room, url=data['url'], stream_type='hls', start_time=start,
            end_time=start + timedelta(hours=1), config={'autoplay': True},
        ) if existing else None
        form = VideoStreamScheduleForm(data, event=event, instance=instance)
        assert form.is_valid(), form.errors
        stream = form.save()
        stream.refresh_from_db()
    assert stream.config == ({'autoplay': True} if existing and config is None else {})


@pytest.mark.django_db
@pytest.mark.parametrize('config', ('[]', 'false', '0', '"{}"', '"text"', 'invalid'))
def test_stream_form_rejects_non_object_config(config):
    """Do not normalize invalid JSON or non-object JSON values to an empty object."""
    organizer = Organizer.objects.create(name='Invalid config', slug='invalid-config')
    event = Event.objects.create(organizer=organizer, name='Invalid config', slug='invalid-config', date_from=now())
    start = now() + timedelta(days=1)
    with scope(event=event, organizer=organizer):
        room = Room.objects.create(event=event, name='Stream room')
        form = VideoStreamScheduleForm({
            'room': room.pk, 'url': 'https://example.com/live', 'stream_type': 'hls',
            'start_time': start.isoformat(), 'end_time': (start + timedelta(hours=1)).isoformat(), 'config': config,
        }, event=event)
        assert not form.is_valid()
    assert 'config' in form.errors


@pytest.mark.parametrize('minutes', (-1, 0, 1, None))
def test_stream_clean_validates_times_without_a_room(mocker, minutes):
    """Validate chronology independently of the room and always run base validation."""
    start = now() + timedelta(days=1)
    end = start + timedelta(minutes=minutes) if minutes is not None else None
    stream = StreamSchedule(start_time=start, end_time=end)
    base_clean = mocker.patch('django.db.models.Model.clean', autospec=True)
    if minutes is not None and minutes <= 0:
        with pytest.raises(ValidationError) as error:
            stream.clean()
        assert 'end_time' in error.value.message_dict
    else:
        stream.clean()
    base_clean.assert_called_once_with(stream)


@pytest.mark.django_db
@pytest.mark.parametrize('route, cold_budget', (('admin.dashboard', 65), ('admin.operations', 75)))
def test_admin_page_query_budgets(dashboard_admin, settings, django_assert_max_num_queries, route, cold_budget):
    """Keep cold loads bounded and reuse cached aggregates on subsequent requests."""
    settings.HAS_CELERY = False
    settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    cache.clear()
    url = reverse(f'eventyay_admin:{route}')
    with django_assert_max_num_queries(cold_budget):
        assert dashboard_admin.get(url).status_code == 200
    with patch('eventyay.control.views.admin.AdminContextMixin.get_common_context', side_effect=AssertionError), \
            patch('eventyay.control.views.admin.AdminDashboard.get_dashboard_counts', side_effect=AssertionError), \
            patch('eventyay.control.views.admin.AdminOperations.get_operations_context', side_effect=AssertionError), \
            patch('eventyay.control.platform_dashboard.activity_context', side_effect=AssertionError):
        with django_assert_max_num_queries(17):
            assert dashboard_admin.get(url).status_code == 200
    cache.clear()


@pytest.mark.django_db
@pytest.mark.parametrize('route', ('admin.dashboard', 'admin.analytics'))
def test_admin_all_time_activity_is_cached(dashboard_admin, settings, mocker, route):
    """Exercise all-time charts through both views and invalidate them on Refresh."""
    settings.HAS_CELERY = False
    settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    cache.clear()
    aggregate = mocker.patch('eventyay.control.platform_dashboard.activity_context', wraps=activity_context)
    url = reverse(f'eventyay_admin:{route}') + '?range=all'
    for _ in range(2):
        response = dashboard_admin.get(url)
        assert response.status_code == 200
        assert response.context['activity_range'] == 'all'
        assert len(response.context['activity_charts']) == 4
        assert 'Rendered at' in response.content.decode()
    assert aggregate.call_count == 1
    dashboard_admin.post(reverse('eventyay_admin:admin.dashboard'), {'action': 'refresh'})
    assert dashboard_admin.get(url).status_code == 200
    assert aggregate.call_count == 2
    cache.clear()


@pytest.mark.django_db
def test_admin_pages_only_build_their_own_context(dashboard_admin, settings, mocker):
    """Do not load operations detail on the dashboard or dashboard charts on operations."""
    settings.HAS_CELERY = False
    server = JitsiServer.objects.create(url='https://jitsi.example.test', active=True)
    with patch('eventyay.control.views.admin.AdminOperations.get_operations_context', side_effect=AssertionError):
        assert dashboard_admin.get(reverse('eventyay_admin:admin.dashboard')).status_code == 200
    with patch('eventyay.control.views.admin.AdminDashboard.get_dashboard_counts', side_effect=AssertionError), \
            patch('eventyay.control.views.admin.check_dependencies', side_effect=AssertionError), \
            patch('eventyay.control.platform_dashboard.activity_context', side_effect=AssertionError):
        response = dashboard_admin.get(reverse('eventyay_admin:admin.operations'))
    assert response.status_code == 200
    assert 'activity_charts' not in response.context_data
    assert 'metric_cards' not in response.context_data
    assert 'periodic_tasks' in response.context_data
    assert server.url in response.content.decode()
    assert len(response.context_data['video_server_rows']) == 1


@pytest.mark.django_db
def test_streaming_event_selector_only_renders_selected_event(django_assert_max_num_queries):
    """Use paginated autocomplete instead of rendering every platform event option."""
    organizer = Organizer.objects.create(name='Event search', slug='event-search')
    events = [Event.objects.create(
        organizer=organizer, name='Same name', slug=f'event-{index}', date_from=now(),
    ) for index in range(25)]
    with django_assert_max_num_queries(0):
        html = str(VideoStreamingSelectionForm()['event'])
    assert 'data-model-select2="event"' in html
    assert 'Same name' not in html
    form = VideoStreamingSelectionForm({'event': events[0].pk})
    assert form.is_valid(), form.errors
    html = str(form['event'])
    assert html.count('<option') == 1
    assert 'Same name (event-search)' in html


@pytest.mark.django_db
def test_dashboard_caches_dependency_checks(dashboard_admin, settings, mocker):
    """Cache silent dashboard readiness probes for 60 seconds and refresh explicitly."""
    settings.HAS_CELERY = False
    settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    cache.clear()


    probe = mocker.patch('eventyay.control.views.admin.check_dependencies', return_value='db_unavailable')
    cached = mocker.spy(cache, 'get_or_set')
    url = reverse('eventyay_admin:admin.dashboard')
    for _ in range(2):
        response = dashboard_admin.get(url)
        assert response.status_code == 200
        assert response.context['api_health_ok'] is False
    probe.assert_called_once_with()
    assert any(call.args[0] == 'admin_dashboard_health' and call.args[2] == 60 for call in cached.call_args_list)
    dashboard_admin.post(url, {'action': 'refresh'})
    assert dashboard_admin.get(url).status_code == 200
    assert probe.call_count == 2
    cache.clear()


def test_dashboard_cache_failure_loads_uncached_data(mocker):
    """An unavailable cache must not make the newly cached admin pages fail."""
    mocker.patch('eventyay.control.platform_dashboard.cache.get_or_set', side_effect=RedisError('Unavailable'))
    load = mocker.Mock(return_value={'count': 3})
    assert cached_dashboard_context('admin_dashboard_counts', load) == {'count': 3}
    load.assert_called_once_with()

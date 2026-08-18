import datetime
from decimal import Decimal

import pytest
from django_scopes import scopes_disabled
from rest_framework.test import APIClient

from eventyay.base.models import Device, Event, Order, OrderPosition, Organizer, Product, RevokedTicketSecret
from eventyay.base.models.devices import generate_api_token


@pytest.fixture
def offline_sync_env():
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Offline Org', slug='offline-org')
        event = Event.objects.create(
            organizer=organizer,
            name='Offline Event',
            slug='offline-event',
            plugins='eventyay.plugins.badges',
            date_from=datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc),
            live=True,
            tickets_published=True,
        )
        product = Product.objects.create(
            event=event,
            name='General',
            default_price=0,
            admission=True,
        )
        event.badge_layouts.create(name='Default', default=True)
        order = Order.objects.create(
            event=event,
            email='attendee@example.test',
            status=Order.STATUS_PAID,
            datetime=datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc),
            expires=datetime.datetime(2030, 2, 1, tzinfo=datetime.timezone.utc),
            total=0,
        )
        position = OrderPosition.objects.create(
            order=order,
            product=product,
            price=Decimal('0.00'),
            attendee_name_parts={'full_name': 'Ada Lovelace', '_scheme': 'full'},
            secret='secret-offline-sync',
        )
        RevokedTicketSecret.objects.create(event=event, position=None, secret='revoked-secret-1')
        staff = Device.objects.create(
            organizer=organizer,
            all_events=True,
            name='Check-In Staff',
            initialized=datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc),
            api_token=generate_api_token(),
            security_profile='eventyay_checkin',
        )
        kiosk = Device.objects.create(
            organizer=organizer,
            all_events=True,
            name='Badge Station',
            initialized=datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc),
            api_token=generate_api_token(),
            security_profile='eventyay_checkin_online_kiosk',
        )
        yield {
            'organizer': organizer,
            'event': event,
            'position': position,
            'staff': staff,
            'kiosk': kiosk,
        }


def _device_client(device):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Device ' + device.api_token)
    return client


def _orders_url(env):
    return '/api/v1/organizers/{}/events/{}/orders/'.format(env['organizer'].slug, env['event'].slug)


def _revoked_url(env):
    return '/api/v1/organizers/{}/events/{}/revokedsecrets/'.format(
        env['organizer'].slug,
        env['event'].slug,
    )


def _layouts_url(env):
    return '/api/v1/organizers/{}/events/{}/badgelayouts/'.format(
        env['organizer'].slug,
        env['event'].slug,
    )


@pytest.mark.django_db
def test_checkin_staff_can_list_orders_for_offline_sync(offline_sync_env):
    env = offline_sync_env
    client = _device_client(env['staff'])

    resp = client.get(_orders_url(env) + '?ordering=last_modified')
    assert resp.status_code == 200
    assert 'X-Page-Generated' in resp
    assert resp.data['count'] >= 1
    codes = {row['code'] for row in resp.data['results']}
    assert env['position'].order.code in codes
    position = resp.data['results'][0]['positions'][0]
    assert position['secret'] == 'secret-offline-sync'


@pytest.mark.django_db
def test_checkin_staff_can_list_revoked_secrets(offline_sync_env):
    env = offline_sync_env
    client = _device_client(env['staff'])

    resp = client.get(_revoked_url(env))
    assert resp.status_code == 200
    secrets = {row['secret'] for row in resp.data['results']}
    assert 'revoked-secret-1' in secrets


@pytest.mark.django_db
def test_checkin_staff_can_list_badge_layouts_for_offline_sync(offline_sync_env):
    env = offline_sync_env
    client = _device_client(env['staff'])

    resp = client.get(_layouts_url(env))
    assert resp.status_code == 200
    names = {row['name'] for row in resp.data['results']}
    assert 'Default' in names
    assert 'layout' in resp.data['results'][0]


@pytest.mark.django_db
def test_checkin_staff_can_download_badge_layout_background(offline_sync_env):
    env = offline_sync_env
    client = _device_client(env['staff'])
    layout = env['event'].badge_layouts.get(default=True)

    resp = client.get(f'{_layouts_url(env)}{layout.pk}/background/')
    assert resp.status_code in (200, 404)


@pytest.mark.django_db
def test_badge_station_cannot_list_orders_for_sync(offline_sync_env):
    env = offline_sync_env
    client = _device_client(env['kiosk'])

    resp = client.get(_orders_url(env))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_badge_station_cannot_list_revoked_secrets(offline_sync_env):
    env = offline_sync_env
    client = _device_client(env['kiosk'])

    resp = client.get(_revoked_url(env))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_badge_station_cannot_list_badge_layouts(offline_sync_env):
    env = offline_sync_env
    client = _device_client(env['kiosk'])

    resp = client.get(_layouts_url(env))
    assert resp.status_code == 403

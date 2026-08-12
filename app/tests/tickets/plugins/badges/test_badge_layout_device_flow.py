import datetime
from decimal import Decimal

import pytest
from django_scopes import scopes_disabled
from rest_framework.test import APIClient

from eventyay.base.models import Device, Event, Order, OrderPosition, Organizer, Product
from eventyay.base.models.devices import generate_api_token
from eventyay.plugins.badges.models import BadgeProduct


@pytest.fixture
def checkin_badge_env():
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Checkin Org', slug='checkin-org')
        event = Event.objects.create(
            organizer=organizer,
            name='Checkin Event',
            slug='checkin-event',
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
        default_layout = event.badge_layouts.create(name='Default', default=True)
        alt_layout = event.badge_layouts.create(name='VIP', default=False)
        BadgeProduct.objects.create(product=product, layout=default_layout)
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
            secret='secret-layout-flow',
        )
        device = Device.objects.create(
            organizer=organizer,
            all_events=True,
            name='Check-In Staff',
            initialized=datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc),
            api_token=generate_api_token(),
            security_profile='eventyay_checkin',
        )
        yield {
            'organizer': organizer,
            'event': event,
            'product': product,
            'default_layout': default_layout,
            'alt_layout': alt_layout,
            'position': position,
            'device': device,
        }


def _device_client(device):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Device ' + device.api_token)
    return client


@pytest.mark.django_db
def test_checkin_staff_can_list_badge_layouts(checkin_badge_env):
    env = checkin_badge_env
    client = _device_client(env['device'])

    resp = client.get(
        '/api/v1/organizers/{}/events/{}/badgelayouts/'.format(
            env['organizer'].slug,
            env['event'].slug,
        )
    )
    assert resp.status_code == 200
    names = {row['name'] for row in resp.data['results']}
    assert names == {'Default', 'VIP'}


@pytest.mark.django_db
def test_checkin_staff_download_with_layout_override(checkin_badge_env, monkeypatch):
    env = checkin_badge_env
    client = _device_client(env['device'])
    alt = env['alt_layout']

    monkeypatch.setattr(
        'eventyay.plugins.badges.providers.BadgeOutputProvider.generate',
        lambda self, op, layout=None: (
            'badge.pdf',
            'application/pdf',
            b'%PDF-alt-' + str(layout.pk if layout else 0).encode(),
        ),
    )

    resp = client.get(
        '/api/v1/organizers/{}/events/{}/orderpositions/{}/download/badge/?layout={}'.format(
            env['organizer'].slug,
            env['event'].slug,
            env['position'].pk,
            alt.pk,
        ),
        HTTP_ACCEPT='application/pdf',
    )
    assert resp.status_code == 200
    assert resp['Content-Type'].startswith('application/pdf')
    assert resp.content == b'%PDF-alt-' + str(alt.pk).encode()


@pytest.mark.django_db
def test_checkin_staff_download_accept_pdf_without_layout(checkin_badge_env, monkeypatch):
    env = checkin_badge_env
    client = _device_client(env['device'])

    monkeypatch.setattr(
        'eventyay.plugins.badges.providers.BadgeOutputProvider.generate',
        lambda self, op, layout=None: (
            'badge.pdf',
            'application/pdf',
            b'%PDF-default',
        ),
    )

    resp = client.get(
        '/api/v1/organizers/{}/events/{}/orderpositions/{}/download/badge/'.format(
            env['organizer'].slug,
            env['event'].slug,
            env['position'].pk,
        ),
        HTTP_ACCEPT='application/pdf',
    )
    assert resp.status_code == 200
    assert resp['Content-Type'].startswith('application/pdf')
    assert resp.content == b'%PDF-default'


@pytest.mark.django_db
def test_checkin_staff_download_renders_real_pdf_for_layout(checkin_badge_env):
    env = checkin_badge_env
    client = _device_client(env['device'])
    alt = env['alt_layout']

    resp = client.get(
        '/api/v1/organizers/{}/events/{}/orderpositions/{}/download/badge/?layout={}'.format(
            env['organizer'].slug,
            env['event'].slug,
            env['position'].pk,
            alt.pk,
        )
    )
    assert resp.status_code == 200
    assert resp['Content-Type'].startswith('application/pdf')
    assert resp.content[:4] == b'%PDF'
    assert len(resp.content) > 500


@pytest.mark.django_db
def test_position_downloads_include_assigned_layout(checkin_badge_env):
    env = checkin_badge_env
    client = _device_client(env['device'])

    resp = client.get(
        '/api/v1/organizers/{}/events/{}/orderpositions/{}/'.format(
            env['organizer'].slug,
            env['event'].slug,
            env['position'].pk,
        )
    )
    assert resp.status_code == 200
    badge = next(d for d in resp.data['downloads'] if d['output'] == 'badge')
    assert badge['layout'] == env['default_layout'].pk
    assert 'download/badge' in badge['url']

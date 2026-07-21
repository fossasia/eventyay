from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.files.base import ContentFile
from django.test import override_settings
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import (
    CachedFile,
    CachedTicket,
    Event,
    Order,
    OrderPosition,
    Organizer,
    Product,
    Team,
    User,
)
from eventyay.plugins.badges.models import BadgeProduct
from eventyay.plugins.badges.providers import BadgeOutputProvider


@pytest.fixture
def env():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    with scope(organizer=organizer):
        event = Event.objects.create(
            organizer=organizer,
            name='Dummy',
            slug='dummy',
            date_from=now(),
            plugins='eventyay.plugins.badges',
            live=True,
        )
        user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
        team = Team.objects.create(
            organizer=organizer,
            can_view_orders=True,
            can_change_orders=True,
            can_change_event_settings=True,
            all_events=True,
        )
        team.members.add(user)
        layout = event.badge_layouts.create(name='Default', default=True)
        product = Product.objects.create(event=event, name='Ticket', default_price=23, admission=True)
        BadgeProduct.objects.create(product=product, layout=layout)
        order = Order.objects.create(
            code='FOO',
            event=event,
            email='dummy@dummy.test',
            status=Order.STATUS_PAID,
            datetime=now(),
            expires=now() + timedelta(days=10),
            total=Decimal('23.00'),
            locale='en',
        )
        position = OrderPosition.objects.create(
            order=order,
            product=product,
            variation=None,
            price=Decimal('23.00'),
            attendee_name_parts={'full_name': 'Peter', '_scheme': 'full'},
        )
        yield event, user, order, position, layout


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_order_page_shows_download_and_print_badge(client, env):
    event, user, order, position, _layout = env
    client.login(email='dummy@dummy.dummy', password='dummy')
    response = client.get(
        f'/control/event/{event.organizer.slug}/{event.slug}/orders/{order.code}/',
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Download Badge' in content
    assert 'Print Badge' in content
    assert f'position={position.pk}' in content
    assert 'badges/print' in content
    print_forms = [part for part in content.split('<form') if 'badges/print' in part]
    assert print_forms
    assert all('data-asynctask-download' not in form for form in print_forms)


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_download_preview_page_and_pdf(client, env):
    event, user, order, position, _layout = env
    client.login(email='dummy@dummy.dummy', password='dummy')
    url = (
        f'/control/event/{event.organizer.slug}/{event.slug}/orders/{order.code}/'
        f'position/{position.pk}/badges/preview/'
    )
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Badge preview' in content
    assert 'Download Badge' in content
    assert '?format=pdf' in content

    pdf_response = client.get(url + '?format=pdf')
    assert pdf_response.status_code == 200
    assert pdf_response['Content-Type'].startswith('application/pdf')
    assert 'inline' in pdf_response['Content-Disposition']
    assert pdf_response.get('X-Frame-Options') == 'SAMEORIGIN'

    download_response = client.get(url + '?download=1')
    assert download_response.status_code == 200
    assert download_response['Content-Type'].startswith('application/pdf')
    assert 'attachment' in download_response['Content-Disposition']


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_print_view_opens_print_page(client, env):
    event, user, _order, _position, _layout = env
    client.login(email='dummy@dummy.dummy', password='dummy')
    session_key = client.session.session_key
    with scopes_disabled():
        cf = CachedFile.objects.create(
            filename='badge.pdf',
            type='application/pdf',
            date=now(),
            expires=now() + timedelta(days=1),
            web_download=True,
            session_key=session_key,
        )
        cf.file.save('badge.pdf', ContentFile(b'%PDF-1.4 badge'))

    response = client.get(
        f'/control/event/{event.organizer.slug}/{event.slug}/badges/print/{cf.id}/',
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Print badge' in content
    assert 'data-badge-print-frame' in content
    assert 'format=pdf' in content
    assert 'badge-print.js' in content

    pdf_response = client.get(
        f'/control/event/{event.organizer.slug}/{event.slug}/badges/print/{cf.id}/?format=pdf',
    )
    assert pdf_response.status_code == 200
    assert pdf_response['Content-Type'].startswith('application/pdf')
    assert 'inline' in pdf_response['Content-Disposition']
    assert pdf_response.get('X-Frame-Options') == 'SAMEORIGIN'


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_order_download_badge_redirects_to_preview(client, env):
    event, user, order, position, _layout = env
    client.login(email='dummy@dummy.dummy', password='dummy')
    provider = BadgeOutputProvider(event)
    filename, mimetype, content = provider.generate(position)
    with scopes_disabled():
        ct = CachedTicket.objects.create(
            order_position=position,
            provider='badge',
            type=mimetype,
            extension='.pdf',
        )
        ct.file.save(filename, ContentFile(content))

    response = client.post(
        f'/control/event/{event.organizer.slug}/{event.slug}/orders/{order.code}/'
        f'download/{position.pk}/badge/',
        {'ajax': '1'},
    )
    assert response.status_code == 200
    data = response.json()
    assert data['success'] is True
    assert f'/orders/{order.code}/position/{position.pk}/badges/preview/' in data['redirect']

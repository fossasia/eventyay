from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Order, OrderPosition, Organizer, Team, User
from eventyay.base.models.log import LogEntry
from eventyay.base.models.orders import InvoiceAddress
from eventyay.base.models.product import Product

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def no_site_url_redirect(settings):
    # The organizer middleware redirects control views to SITE_URL when DEBUG is off.
    settings.DEBUG = True


@pytest.fixture
def event():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=organizer,
        name='Dummy',
        slug='dummy',
        date_from=now() - timedelta(days=1),
        live=True,
        tickets_published=True,
    )
    event.settings.invoice_address_asked = True
    event.settings.invoice_address_required = True
    event.settings.attendee_names_asked = True
    event.settings.attendee_emails_asked = True
    return event


@pytest.fixture
def order(event):
    return Order.objects.create(
        code='FOO',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PENDING,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=Decimal('23.00'),
    )


@pytest.fixture
def position(event, order):
    product = Product.objects.create(
        event=event,
        name='Early-bird ticket',
        default_price=Decimal('23.00'),
        admission=True,
    )
    quota = event.quotas.create(name='All', size=100)
    quota.products.add(product)
    return OrderPosition.objects.create(
        order=order,
        product=product,
        price=Decimal('23.00'),
        attendee_name_parts={'full_name': 'Peter', '_scheme': 'full'},
    )


@pytest.fixture
def logged_in_client(client, event):
    user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
    team = Team.objects.create(
        organizer=event.organizer,
        can_view_orders=True,
        can_change_orders=True,
        all_events=True,
    )
    team.members.add(user)
    client.login(email='dummy@dummy.dummy', password='dummy')
    return client


def info_url(event, order):
    return '/control/event/{}/{}/orders/{}/info'.format(event.organizer.slug, event.slug, order.code)


def modified_log_entries(order):
    with scopes_disabled():
        return LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(order),
            object_id=order.pk,
            action_type='eventyay.event.order.modified',
        )


def invoice_address(order):
    with scopes_disabled():
        return InvoiceAddress.objects.filter(order=order).first()


def test_invalid_invoice_address_does_not_persist_attendee_changes(logged_in_client, event, order, position):
    response = logged_in_client.post(
        info_url(event, order),
        {
            '{}-attendee_name_parts_0'.format(position.pk): 'Mallory',
            'street': 'Test street 1',
            'zipcode': '12345',
            'city': 'Testville',
            'country': 'US',
            'state': '',
        },
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert 'We had difficulties processing your input' in content
    assert 'This field is required.' in content
    position.refresh_from_db()
    assert position.attendee_name_parts == {'full_name': 'Peter', '_scheme': 'full'}
    assert not modified_log_entries(order).exists()


def test_invalid_invoice_address_does_not_persist_the_invoice_address(logged_in_client, event, order, position):
    response = logged_in_client.post(
        info_url(event, order),
        {
            '{}-attendee_name_parts_0'.format(position.pk): 'Mallory',
            'street': 'Test street 1',
            'zipcode': '12345',
            'city': 'Testville',
            'country': 'US',
            'state': '',
        },
    )

    assert response.status_code == 200
    assert 'This field is required.' in response.content.decode()
    address = invoice_address(order)
    assert address is None or not address.street


def test_invalid_attendee_form_does_not_persist_the_invoice_address(logged_in_client, event, order, position):
    response = logged_in_client.post(
        info_url(event, order),
        {
            '{}-attendee_email'.format(position.pk): 'not-an-email',
            'street': 'Test street 1',
            'zipcode': '12345',
            'city': 'Berlin',
            'country': 'DE',
            'name_parts_0': 'Peter',
        },
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert 'We had difficulties processing your input' in content
    assert 'valid email address' in content
    position.refresh_from_db()
    assert position.attendee_name_parts == {'full_name': 'Peter', '_scheme': 'full'}
    address = invoice_address(order)
    assert address is None or not address.street
    assert not modified_log_entries(order).exists()


def test_valid_modification_persists_and_is_logged(logged_in_client, event, order, position):
    response = logged_in_client.post(
        info_url(event, order),
        {
            '{}-attendee_name_parts_0'.format(position.pk): 'Mallory',
            'street': 'Test street 1',
            'zipcode': '12345',
            'city': 'Berlin',
            'country': 'DE',
            'name_parts_0': 'Peter',
        },
    )

    assert response.status_code == 302
    position.refresh_from_db()
    assert position.attendee_name_parts == {'full_name': 'Mallory', '_scheme': 'full'}
    assert invoice_address(order).street == 'Test street 1'
    assert modified_log_entries(order).count() == 1


def test_presale_modify_invalid_invoice_does_not_persist_attendee(client, event, order, position):
    event.settings.invoice_address_asked = True
    User.objects.create_user(order.email, 'password')
    client.login(email=order.email, password='password')
    url = '/{}/{}/order/{}/{}/modify'.format(
        event.organizer.slug,
        event.slug,
        order.code,
        order.secret,
    )

    response = client.post(
        url,
        {
            '{}-attendee_name_parts_0'.format(position.pk): 'Mallory',
            'street': 'Test street 1',
            'zipcode': '12345',
            'city': 'Testville',
            'country': 'US',
            'state': '',
        },
    )

    assert response.status_code == 200
    position.refresh_from_db()
    assert position.attendee_name_parts == {'full_name': 'Peter', '_scheme': 'full'}

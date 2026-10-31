from datetime import timedelta

import pytest
from bs4 import BeautifulSoup
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import (
    CartPosition,
    Event,
    Order,
    OrderPosition,
    Organizer,
    Product,
    ProductMetaValue,
)
from tests.testutils.sessions import get_cart_session_key


pytestmark = pytest.mark.django_db


@pytest.fixture
def repeat_purchase(client):
    organizer = Organizer.objects.create(name='Organizer', slug='organizer')
    event = Event.objects.create(
        organizer=organizer, name='Event', slug='event', currency='EUR',
        date_from=now() + timedelta(days=30), live=True, tickets_published=True,
    )
    with scope(event=event, organizer=organizer):
        event.settings.require_registered_account_for_tickets = False
        event.settings.redirect_to_checkout_directly = False
        product = Product.objects.create(event=event, name='Ticket', default_price=10)
        quota = event.quotas.create(name='Tickets', size=20)
        quota.products.add(product)
        order = Order.objects.create(
            event=event, email='customer@example.com', status=Order.STATUS_PAID, total=10,
        )
        OrderPosition.objects.create(order=order, product=product, price=10, positionid=1)
        client.get('/organizer/event/')
        client.post('/organizer/event/cart/add', {f'item_{product.pk}': '1'})
        cart_id = get_cart_session_key(client, event)
        assert CartPosition.objects.filter(event=event, cart_id=cart_id).count() == 1
        session = client.session
        session['carts'][cart_id]['email'] = order.email
        session.save()
        yield event, product, order, cart_id


@pytest.mark.parametrize('status', [Order.STATUS_PENDING, Order.STATUS_PAID])
@pytest.mark.parametrize('restricted', [False, True])
@pytest.mark.parametrize('ajax', [False, True])
@pytest.mark.parametrize('email', ['customer@example.com', 'Customer@Example.COM', 'another@example.com'])
def test_repeat_purchase_respects_product_limit(client, repeat_purchase, status, restricted, ajax, email):
    event, product, order, cart_id = repeat_purchase
    order.status = status
    order.save()
    if restricted:
        property = event.product_meta_properties.create(name='limit_one_per_user')
        ProductMetaValue.objects.create(product=product, property=property, value='1')
        CartPosition.objects.filter(event=event, cart_id=cart_id).delete()
    session = client.session
    session['carts'][cart_id]['email'] = email
    session.save()
    blocked = restricted and email != 'another@example.com'
    data = {f'item_{product.pk}': '1'}
    if ajax:
        data['ajax'] = '1'

    response = client.post('/organizer/event/cart/add', data)

    if ajax:
        assert response.status_code == 200
        payload = response.json()
        assert payload['success'] is not blocked
        redirect_url = payload['redirect']
    else:
        assert response.status_code == 302
        redirect_url = response.url
    page = client.get(redirect_url)
    assert page.status_code == 200
    alerts = [
        alert.get_text(strip=True)
        for alert in BeautifulSoup(page.content, 'lxml').select('.alert-danger')
        if alert.get_text(strip=True)
    ]
    if blocked:
        assert any('Only one ticket per user' in alert for alert in alerts)
    else:
        assert not alerts
    expected_count = 1 if restricted else 2
    if blocked:
        expected_count = 0
    assert CartPosition.objects.filter(event=event, cart_id=cart_id, product=product).count() == expected_count


@pytest.mark.parametrize('status', [Order.STATUS_PENDING, Order.STATUS_PAID])
@pytest.mark.parametrize('owned_restricted', [False, True])
def test_repeat_purchase_mixed_products(client, repeat_purchase, status, owned_restricted):
    event, product, order, cart_id = repeat_purchase
    order.status = status
    order.save()
    other = Product.objects.create(event=event, name='Other ticket', default_price=10)
    event.quotas.get(name='Tickets').products.add(other)
    property = event.product_meta_properties.create(name='limit_one_per_user')
    ProductMetaValue.objects.create(
        product=product if owned_restricted else other, property=property, value='1',
    )

    response = client.post('/organizer/event/cart/add', {
        f'item_{product.pk}': '1', f'item_{other.pk}': '1', 'ajax': '1',
    })

    assert response.status_code == 200
    assert response.json()['success'] is not owned_restricted
    positions = CartPosition.objects.filter(event=event, cart_id=cart_id)
    assert positions.filter(product=product).count() == (1 if owned_restricted else 2)
    assert positions.filter(product=other).count() == (0 if owned_restricted else 1)

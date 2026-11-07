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
from eventyay.base.services.cart import CartError, add_products_to_cart
from eventyay.base.services.orders import OrderError, _perform_order
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
@pytest.mark.parametrize(('limit_value', 'restricted'), [
    (None, False), ('', False), ('0', False), ('false', False), ('False', False),
    ('1', True), ('true', True), ('True', True),
])
@pytest.mark.parametrize('ajax', [False, True])
@pytest.mark.parametrize('email', ['customer@example.com', 'Customer@Example.COM', 'another@example.com'])
def test_repeat_purchase_respects_product_limit(client, repeat_purchase, status, limit_value, restricted, ajax, email):
    event, product, order, cart_id = repeat_purchase
    order.status = status
    order.save()
    if limit_value is not None:
        property = event.product_meta_properties.create(name='limit_one_per_user')
        ProductMetaValue.objects.create(product=product, property=property, value=limit_value)
    if restricted:
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


@pytest.mark.parametrize(('limit_value', 'restricted'), [
    (None, False), ('', False), ('0', False), ('false', False), ('False', False),
    ('1', True), ('true', True), ('True', True),
])
def test_shop_respects_product_limit_value(client, repeat_purchase, limit_value, restricted):
    event, product, order, cart_id = repeat_purchase
    if limit_value is not None:
        property = event.product_meta_properties.create(name='limit_one_per_user')
        ProductMetaValue.objects.create(product=product, property=property, value=limit_value)

    response = client.get('/organizer/event/')

    assert response.status_code == 200
    page = BeautifulSoup(response.content, 'lxml')
    assert ('Limit: 1 per user' in page.get_text()) is restricted


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


@pytest.mark.parametrize('status', [Order.STATUS_PENDING, Order.STATUS_PAID])
@pytest.mark.parametrize(('limit_value', 'restricted'), [
    ('', False), ('0', False), ('false', False), ('False', False),
    ('1', True), ('true', True), ('True', True),
])
@pytest.mark.parametrize('email', [None, 'Customer@Example.COM'])
def test_cart_service_respects_product_limit_value(repeat_purchase, status, limit_value, restricted, email):
    event, product, order, cart_id = repeat_purchase
    order.status = status
    order.save()
    property = event.product_meta_properties.create(name='limit_one_per_user')
    ProductMetaValue.objects.create(product=product, property=property, value=limit_value)
    positions = CartPosition.objects.filter(event=event, cart_id=cart_id, product=product)
    if restricted:
        positions.delete()
    if restricted and email:
        with pytest.raises(CartError, match='Only one ticket per user'):
            add_products_to_cart(
                event.pk, [{'product': product.pk, 'variation': None, 'count': 1}], cart_id,
                widget_data={'email': email},
            )
    else:
        result = add_products_to_cart(
            event.pk, [{'product': product.pk, 'variation': None, 'count': 1}], cart_id,
            widget_data={'email': email} if email else None,
        )
        assert result['success'] is True
        assert positions.count() == (1 if restricted else 2)
        assert 'warning' not in result


@pytest.mark.parametrize('status', [Order.STATUS_PENDING, Order.STATUS_PAID])
@pytest.mark.parametrize(('limit_value', 'restricted'), [
    ('', False), ('0', False), ('false', False), ('False', False),
    ('1', True), ('true', True), ('True', True),
])
def test_order_submission_respects_product_limit_value(repeat_purchase, status, limit_value, restricted):
    event, product, order, cart_id = repeat_purchase
    order.status = status
    order.save()
    property = event.product_meta_properties.create(name='limit_one_per_user')
    ProductMetaValue.objects.create(product=product, property=property, value=limit_value)
    position_ids = list(CartPosition.objects.filter(event=event, cart_id=cart_id).values_list('pk', flat=True))
    if restricted:
        with pytest.raises(OrderError, match='Only one ticket per user'):
            _perform_order(event, None, position_ids, 'Customer@Example.COM', 'en', None)
    else:
        new_order_id = _perform_order(event, None, position_ids, 'Customer@Example.COM', 'en', None)
        new_order = Order.objects.get(pk=new_order_id, event=event)
        assert new_order.email == 'Customer@Example.COM'
        assert new_order.positions.filter(product=product).count() == 1
        assert not CartPosition.objects.filter(pk__in=position_ids).exists()

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import (
    CartPosition,
    Event,
    Order,
    OrderPosition,
    Organizer,
    Product,
)
from eventyay.base.models.product import SubEventProduct
from eventyay.base.services.cart import CartError, CartManager
from eventyay.base.services.orders import OrderChangeManager, OrderError, _perform_order
from eventyay.base.services.pricing import get_price


@pytest.fixture
def event():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=organizer,
        name='Dummy',
        slug='dummy',
        date_from=now() + timedelta(days=30),
        plugins='eventyay.plugins.banktransfer',
    )
    with scope(organizer=organizer):
        yield event


@pytest.fixture
def product(event):
    product = Product.objects.create(event=event, name='Donation', default_price=Decimal('50.00'), free_price=True)
    event.quotas.create(name='Q', size=None).products.add(product)
    return product


@pytest.fixture
def voucher(event, product):
    return event.vouchers.create(code='MINUS30', product=product, price_mode='subtract', value=Decimal('30.00'))


def add_to_cart(event, product, price, voucher=None, cart_id='cart'):
    cm = CartManager(event=event, cart_id=cart_id)
    cm.add_new_products(
        [
            {
                'product': product.pk,
                'variation': None,
                'count': 1,
                'price': price,
                'voucher': voucher.code if voucher else None,
            }
        ]
    )
    cm.commit()
    return CartPosition.objects.get(cart_id=cart_id)


def place_order(event, cart_id='cart'):
    positions = list(CartPosition.objects.filter(cart_id=cart_id).values_list('pk', flat=True))
    return _perform_order(event, 'banktransfer', positions, 'dummy@example.org', 'en', None)


@pytest.mark.django_db
def test_get_price_unvalidated_custom_price_is_clamped_to_minimum(product):
    assert get_price(product, custom_price=Decimal('20.00'), validate_free_price_bounds=False).gross == Decimal('50.00')


@pytest.mark.django_db
def test_get_price_validated_custom_price_below_minimum_raises(product):
    with pytest.raises(ValueError) as excinfo:
        get_price(product, custom_price=Decimal('20.00'))
    assert excinfo.value.args[0] == 'price_too_low'


@pytest.mark.django_db
@pytest.mark.parametrize('custom_price', [Decimal('20.00'), Decimal('25.00')])
def test_cart_accepts_custom_price_down_to_voucher_price(event, product, voucher, custom_price):
    cp = add_to_cart(event, product, custom_price, voucher)
    assert cp.price == custom_price
    assert cp.price_before_voucher == Decimal('50.00')


@pytest.mark.django_db
def test_cart_rejects_custom_price_below_voucher_price(event, product, voucher):
    with pytest.raises(CartError) as excinfo:
        add_to_cart(event, product, Decimal('19.99'), voucher)
    assert '20.00' in str(excinfo.value)
    assert not CartPosition.objects.exists()


@pytest.mark.django_db
def test_cart_without_voucher_keeps_full_minimum(event, product):
    with pytest.raises(CartError) as excinfo:
        add_to_cart(event, product, Decimal('25.00'))
    assert '50.00' in str(excinfo.value)


@pytest.mark.django_db
def test_checkout_places_order_with_discounted_custom_price(event, product, voucher):
    add_to_cart(event, product, Decimal('20.00'), voucher)
    position = OrderPosition.objects.get(order_id=place_order(event))
    assert position.price == Decimal('20.00')
    assert position.price_before_voucher == Decimal('50.00')


@pytest.mark.django_db
def test_voucher_budget_counts_discount_against_custom_price(event, product):
    voucher = event.vouchers.create(
        code='MINUS30', product=product, price_mode='subtract', value=Decimal('30.00'), budget=Decimal('30.00')
    )
    add_to_cart(event, product, Decimal('20.00'), voucher)
    place_order(event)
    assert voucher.budget_used() == Decimal('30.00')


@pytest.mark.django_db
def test_voucher_budget_smaller_than_discount_is_enforced_at_checkout(event, product):
    voucher = event.vouchers.create(
        code='MINUS30', product=product, price_mode='subtract', value=Decimal('30.00'), budget=Decimal('20.00')
    )
    cp = add_to_cart(event, product, Decimal('20.00'), voucher)
    with pytest.raises(OrderError):
        place_order(event)
    cp.refresh_from_db()
    assert cp.price == Decimal('30.00')
    assert not Order.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize('includes_tax', [True, False])
def test_expired_cart_position_is_repriced_with_voucher(event, product, voucher, includes_tax):
    cp = CartPosition.objects.create(
        event=event,
        cart_id='cart',
        product=product,
        voucher=voucher,
        price=Decimal('20.00'),
        price_before_voucher=Decimal('50.00'),
        includes_tax=includes_tax,
        expires=now() - timedelta(minutes=1),
    )
    CartManager(event=event, cart_id='cart').commit()
    cp.refresh_from_db()
    assert cp.expires > now()
    assert cp.price == Decimal('20.00')
    assert cp.price_before_voucher == Decimal('50.00')


@pytest.mark.django_db
def test_checkout_reprices_when_voucher_is_lowered_after_carting(event, product, voucher):
    cp = add_to_cart(event, product, Decimal('20.00'), voucher)
    voucher.value = Decimal('10.00')
    voucher.save()
    with pytest.raises(OrderError):
        place_order(event)
    cp.refresh_from_db()
    assert cp.price == Decimal('40.00')
    position = OrderPosition.objects.get(order_id=place_order(event))
    assert position.price == Decimal('40.00')
    assert position.price_before_voucher == Decimal('50.00')


@pytest.mark.django_db
def test_checkout_reprices_when_base_price_is_raised_after_carting(event, product, voucher):
    cp = add_to_cart(event, product, Decimal('50.00'), voucher)
    product.default_price = Decimal('90.00')
    product.save()
    with pytest.raises(OrderError):
        place_order(event)
    cp.refresh_from_db()
    assert cp.price == Decimal('60.00')


@pytest.mark.django_db
@pytest.mark.parametrize('includes_tax', [True, False])
def test_expired_cart_position_is_repriced_when_voucher_is_lowered(event, product, voucher, includes_tax):
    cp = CartPosition.objects.create(
        event=event,
        cart_id='cart',
        product=product,
        voucher=voucher,
        price=Decimal('20.00'),
        price_before_voucher=Decimal('50.00'),
        includes_tax=includes_tax,
        expires=now() - timedelta(minutes=1),
    )
    voucher.value = Decimal('10.00')
    voucher.save()
    CartManager(event=event, cart_id='cart').commit()
    cp.refresh_from_db()
    assert cp.price == Decimal('40.00')
    assert cp.price_before_voucher == Decimal('50.00')


@pytest.fixture
def order_position(event, product, voucher):
    order = Order.objects.create(
        code='FOO',
        event=event,
        email='dummy@example.org',
        status=Order.STATUS_PENDING,
        locale='en',
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=Decimal('20.00'),
    )
    return OrderPosition.objects.create(
        order=order,
        product=product,
        price=Decimal('20.00'),
        price_before_voucher=Decimal('50.00'),
        voucher=voucher,
        positionid=1,
    )


@pytest.mark.django_db
def test_order_change_product_keeps_price_before_voucher_floor(event, order_position, voucher):
    other = Product.objects.create(event=event, name='Other', default_price=Decimal('40.00'), free_price=True)
    event.quotas.get().products.add(other)
    ocm = OrderChangeManager(order_position.order, None)
    ocm.change_product(order_position, other, None)
    ocm.commit()
    order_position.refresh_from_db()
    assert order_position.price == Decimal('20.00')
    assert order_position.price_before_voucher == Decimal('40.00')


@pytest.mark.django_db
def test_order_change_subevent_keeps_price_before_voucher_floor(event, product, order_position):
    event.has_subevents = True
    event.save()
    old = event.subevents.create(name='Old', date_from=now())
    new = event.subevents.create(name='New', date_from=now())
    order_position.subevent = old
    order_position.save()
    quota = event.quotas.get()
    quota.subevent = old
    quota.save()
    event.quotas.create(name='Q2', size=None, subevent=new).products.add(product)
    SubEventProduct.objects.create(subevent=new, product=product, price=Decimal('40.00'))
    ocm = OrderChangeManager(order_position.order, None)
    ocm.change_subevent(order_position, new)
    ocm.commit()
    order_position.refresh_from_db()
    assert order_position.price == Decimal('20.00')
    assert order_position.price_before_voucher == Decimal('40.00')

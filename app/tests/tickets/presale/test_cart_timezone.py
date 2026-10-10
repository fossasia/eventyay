from contextlib import nullcontext
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.db.models import Value
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import CartPosition, Event, Organizer, Product
from eventyay.base.services.cart import CartError, CartManager
from eventyay.base.services.orders import OrderError, _check_date, _check_positions


@pytest.mark.django_db
def test_existing_subevent_payment_period_over():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=organizer,
        name='Dummy',
        slug='dummy',
        date_from=now() + timedelta(days=30),
        has_subevents=True,
        timezone='Europe/Berlin',
        live=True,
    )
    with scope(event=event, organizer=organizer):
        subevent = event.subevents.create(
            name='Day one', date_from=now() - timedelta(days=2), active=True
        )
        product = Product.objects.create(event=event, name='Ticket', default_price=23)
        position = CartPosition.objects.create(
            event=event,
            cart_id='timezone-regression',
            product=product,
            subevent=subevent,
            price=23,
            expires=now() + timedelta(minutes=10),
        )
        event.settings.payment_term_last = 'RELDATE/1/23:59:59/date_from/'

        CartManager(event=event, cart_id=position.cart_id).commit()

        assert not CartPosition.objects.filter(pk=position.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize('timezone', ['America/Los_Angeles', 'Asia/Tokyo'])
@pytest.mark.parametrize('expired', [False, True])
@pytest.mark.parametrize('path', ['cart-event', 'cart-existing', 'cart-add', 'order-event', 'order-existing'])
def test_payment_deadline_uses_ticketing_timezone(timezone, expired, path):
    """Ticket deadlines use settings even when the talk timezone remains UTC."""
    deadline = datetime(2030, 5, 1, 23, 59, 59, tzinfo=ZoneInfo(timezone))
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=organizer, name='Dummy', slug='dummy',
        date_from=deadline + timedelta(days=30),
        has_subevents=path not in ('cart-event', 'order-event'), live=True,
    )
    with scope(event=event, organizer=organizer):
        assert event.timezone == 'UTC'
        event.settings.timezone = timezone
        event.settings.payment_term_last = '2030-05-01'
        manager = CartManager(event=event, cart_id='ticketing-timezone')
        manager.now_dt = deadline + timedelta(seconds=1 if expired else -1)
        if path in ('cart-event', 'order-event'):
            error = CartError if path == 'cart-event' else OrderError
            with pytest.raises(error) if expired else nullcontext():
                if path == 'cart-event':
                    manager._check_presale_dates()
                else:
                    _check_date(event, manager.now_dt)
            return

        subevent = event.subevents.create(name='Day one', date_from=event.date_from, active=True)
        product = Product.objects.create(event=event, name='Ticket', default_price=23)
        quota = subevent.quotas.create(event=event, name='Tickets', size=10)
        quota.products.add(product)
        if path == 'cart-add':
            with pytest.raises(CartError) if expired else nullcontext():
                manager.add_new_products([{
                    'product': product.pk, 'variation': None, 'count': 1, 'subevent': subevent.pk,
                }])
            return

        position = CartPosition.objects.create(
            event=event, cart_id=manager.cart_id, product=product, subevent=subevent,
            price=23, expires=deadline + timedelta(days=1),
        )
        if path == 'cart-existing':
            assert bool(manager._delete_out_of_timeframe()) == expired
        else:
            position = CartPosition.objects.annotate(requires_seat=Value(False)).get(pk=position.pk)
            with pytest.raises(OrderError) if expired else nullcontext():
                _check_positions(event, manager.now_dt, [position])
        assert CartPosition.objects.filter(pk=position.pk).exists() == (not expired)

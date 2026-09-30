from datetime import timedelta

import pytest
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import CartPosition, Event, Organizer, Product
from eventyay.base.services.cart import CartManager


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

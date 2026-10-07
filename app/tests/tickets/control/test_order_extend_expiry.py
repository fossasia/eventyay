from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.test import override_settings
from django.utils.timezone import now
from django_scopes import scopes_disabled
from eventyay.base.models import Event, Order, OrderPosition, Organizer, Product, Quota, Team, User


@pytest.fixture
@scopes_disabled()
def order():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(organizer=organizer, name='Dummy', slug='dummy', date_from=now() + timedelta(days=30))
    event.settings.timezone = 'Asia/Kolkata'
    user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
    team = Team.objects.create(organizer=organizer, can_view_orders=True, can_change_orders=True)
    team.members.add(user)
    team.limit_events.add(event)
    product = Product.objects.create(event=event, name='Ticket', default_price=Decimal('23.00'))
    quota = Quota.objects.create(event=event, name='Tickets', size=10)
    quota.products.add(product)
    order = Order.objects.create(
        code='FOO',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PENDING,
        datetime=now(),
        expires=now() + timedelta(days=2),
        total=Decimal('23.00'),
    )
    OrderPosition.objects.create(order=order, product=product, price=Decimal('23.00'))
    return order


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_extend_sets_end_of_day_in_event_timezone(client, order):
    new_date = (now() + timedelta(days=20)).date()
    client.force_login(User.objects.get(email='dummy@dummy.dummy'))
    response = client.post(
        '/control/event/dummy/dummy/orders/FOO/extend',
        {'expires': new_date.isoformat()},
    )
    assert response.status_code == 302
    assert response['Location'].endswith('/control/event/dummy/dummy/orders/FOO/')

    with scopes_disabled():
        order.refresh_from_db()
    expires = order.expires.astimezone(ZoneInfo('Asia/Kolkata'))
    assert (expires.date(), expires.hour, expires.minute, expires.second) == (new_date, 23, 59, 59)

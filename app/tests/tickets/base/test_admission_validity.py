from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.utils.timezone import now
from django_scopes import scope
from pytz import UTC

from eventyay.base.models import Event, Order, OrderPosition, Organizer, Product
from eventyay.base.services.checkin import CheckInError, perform_checkin


@pytest.fixture
def event():
    o = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=o,
        name='Dummy',
        slug='dummy',
        date_from=datetime(2026, 6, 1, 10, 0, 0, tzinfo=UTC),
        date_to=datetime(2026, 6, 3, 18, 0, 0, tzinfo=UTC),
        plugins='eventyay.plugins.banktransfer',
    )
    event.settings.timezone = 'UTC'
    with scope(organizer=o):
        yield event


@pytest.fixture
def clist(event):
    return event.checkin_lists.create(name='Default', all_products=True)


def _create_position(event, product, *, clear_admission_snapshot=False):
    order = Order.objects.create(
        code='FOO',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PAID,
        locale='en',
        datetime=now() - timedelta(days=30),
        expires=now() + timedelta(days=10),
        total=Decimal('23.00'),
    )
    position = OrderPosition.objects.create(
        order=order,
        product=product,
        variation=None,
        price=Decimal('23.00'),
        attendee_name_parts={'full_name': 'Peter'},
        positionid=1,
    )
    if clear_admission_snapshot:
        OrderPosition.objects.filter(pk=position.pk).update(
            admission_valid_from=None,
            admission_valid_until=None,
        )
        position.refresh_from_db()
    return position


@pytest.mark.django_db
def test_legacy_ticket_uses_catalog_admission_bounds(event, clist):
    expired_product = event.products.create(
        name='Expired workshop',
        default_price=Decimal('10.00'),
        admission=True,
        active=True,
        admission_validity_mode=Product.ADMISSION_VALIDITY_MODE_FIXED,
        admission_valid_from=now() - timedelta(days=2),
        admission_valid_until=now() - timedelta(days=1),
    )
    position = _create_position(event, expired_product, clear_admission_snapshot=True)

    with pytest.raises(CheckInError) as excinfo:
        perform_checkin(position, clist, {})

    assert excinfo.value.code == 'invalid_time'


@pytest.mark.django_db
def test_legacy_ticket_without_catalog_restriction_allows_checkin(event, clist):
    unrestricted = event.products.create(
        name='Conference pass',
        default_price=Decimal('10.00'),
        admission=True,
        active=True,
    )
    position = _create_position(event, unrestricted, clear_admission_snapshot=True)

    perform_checkin(position, clist, {})
    assert position.checkins.count() == 1


@pytest.mark.django_db
def test_issued_snapshot_takes_precedence_over_catalog(event, clist):
    product = event.products.create(
        name='Workshop',
        default_price=Decimal('10.00'),
        admission=True,
        active=True,
        admission_validity_mode=Product.ADMISSION_VALIDITY_MODE_FIXED,
        admission_valid_from=now() - timedelta(days=2),
        admission_valid_until=now() - timedelta(days=1),
    )
    position = _create_position(event, product, clear_admission_snapshot=False)
    OrderPosition.objects.filter(pk=position.pk).update(
        admission_valid_from=now() - timedelta(hours=1),
        admission_valid_until=now() + timedelta(hours=1),
    )
    position.refresh_from_db()

    perform_checkin(position, clist, {})
    assert position.checkins.count() == 1

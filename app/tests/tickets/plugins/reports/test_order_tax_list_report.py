import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.utils.timezone import now
from django_scopes import scope
from eventyay.base.models import Event, Order, OrderPosition, Organizer, Product
from eventyay.plugins.reports.exporters import OrderTaxListReport


ORDER_DATE = datetime.datetime(2026, 3, 10, 12, 0, tzinfo=ZoneInfo('UTC'))


@pytest.fixture
def event():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(organizer=organizer, name='Dummy', slug='dummy', date_from=now())
    event.settings.timezone = 'Europe/Berlin'
    with scope(organizer=organizer):
        product = Product.objects.create(event=event, name='Ticket', default_price=Decimal('23.00'))
        order = Order.objects.create(
            code='FOO',
            event=event,
            email='dummy@dummy.test',
            status=Order.STATUS_PAID,
            datetime=ORDER_DATE,
            expires=ORDER_DATE + datetime.timedelta(days=10),
            total=Decimal('23.00'),
        )
        OrderPosition.objects.create(order=order, product=product, price=Decimal('23.00'))
    return event


def order_rows(event, **form_data):
    form_data = {
        'date_axis': 'order_date',
        'status': [Order.STATUS_PAID],
        'sort': 'datetime',
        'direction': 'asc',
        **form_data,
    }
    with scope(organizer=event.organizer):
        rows = list(OrderTaxListReport(event).iterate_sheet(form_data, 'orders'))
    # Skip the header row and the final totals row.
    return [row[0] for row in rows[1:-1]]


@pytest.mark.django_db
def test_lists_orders_without_date_filter(event):
    assert order_rows(event) == ['FOO']


@pytest.mark.django_db
def test_date_from_filter(event):
    assert order_rows(event, date_from='2026-03-01') == ['FOO']
    assert order_rows(event, date_from='2026-03-11') == []


@pytest.mark.django_db
def test_date_until_filter(event):
    assert order_rows(event, date_until='2026-03-10') == ['FOO']
    assert order_rows(event, date_until='2026-03-09') == []

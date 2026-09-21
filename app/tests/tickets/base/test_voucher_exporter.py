from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.exporters.vouchers import VoucherAttendeeListExporter
from eventyay.base.models import Event, Order, OrderPosition, Organizer, Product, Voucher


@pytest.fixture
def env():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(organizer=organizer, name='Dummy', slug='dummy', date_from=now())
    with scope(organizer=organizer):
        ticket = Product.objects.create(event=event, name='Ticket', default_price=23, admission=True)
        pool_a = Voucher.objects.create(event=event, code='POOLA1', tag='pool-a', max_usages=2, redeemed=1)
        unclaimed = Voucher.objects.create(event=event, code='POOLA2', tag='pool-a')
        other = Voucher.objects.create(event=event, code='OTHER1', tag='pool-b', redeemed=1)
        order = Order.objects.create(
            code='FOO',
            event=event,
            email='buyer@example.org',
            status=Order.STATUS_PAID,
            datetime=now(),
            expires=now() + timedelta(days=10),
            total=Decimal('46'),
        )
        OrderPosition.objects.create(
            order=order,
            product=ticket,
            price=Decimal('23'),
            voucher=pool_a,
            attendee_name_parts={'full_name': 'Alice', '_scheme': 'full'},
            attendee_email='alice@example.org',
        )
        OrderPosition.objects.create(
            order=order,
            product=ticket,
            price=Decimal('23'),
            voucher=pool_a,
            canceled=True,
            attendee_name_parts={'full_name': 'Canceled Carl', '_scheme': 'full'},
        )
        OrderPosition.objects.create(
            order=order,
            product=ticket,
            price=Decimal('23'),
            voucher=other,
            attendee_name_parts={'full_name': 'Bob', '_scheme': 'full'},
        )
        yield event, pool_a, unclaimed, other


def _rows(event, form_data):
    exporter = VoucherAttendeeListExporter(event)
    rows = [row for row in exporter.iterate_list(form_data) if not isinstance(row, exporter.ProgressSetTotal)]
    header = [str(h) for h in rows[0]]
    return [dict(zip(header, [str(c) for c in row])) for row in rows[1:]]


@pytest.mark.django_db
def test_export_filters_by_tag_and_lists_unclaimed_vouchers(env):
    event, pool_a, unclaimed, other = env

    rows = _rows(event, {'voucher_tag': 'pool-a', 'include_unredeemed': True})

    assert [r['Voucher code'] for r in rows] == ['POOLA1', 'POOLA2']
    claimed, not_claimed = rows
    assert claimed['Attendee name'] == 'Alice'
    assert claimed['Attendee email'] == 'alice@example.org'
    assert claimed['Order code'] == 'FOO'
    assert claimed['Voucher status'] == 'Partially redeemed'
    assert not_claimed['Attendee name'] == ''
    assert not_claimed['Voucher status'] == 'Not redeemed'


@pytest.mark.django_db
def test_export_excludes_unredeemed_vouchers_when_requested(env):
    event, *_ = env

    rows = _rows(event, {'voucher_tag': 'pool-a', 'include_unredeemed': False})

    assert [r['Voucher code'] for r in rows] == ['POOLA1']


@pytest.mark.django_db
def test_export_filters_by_voucher_code(env):
    event, *_ = env

    rows = _rows(event, {'voucher_code': ' other1 '})

    assert len(rows) == 1
    assert rows[0]['Voucher code'] == 'OTHER1'
    assert rows[0]['Attendee name'] == 'Bob'
    assert rows[0]['Attendee email'] == 'buyer@example.org'
    assert rows[0]['Voucher status'] == 'Redeemed'


@pytest.mark.django_db
def test_export_form_offers_existing_tags(env):
    event, *_ = env

    field = VoucherAttendeeListExporter(event).additional_form_fields['voucher_tag']

    assert [value for value, label in field.choices] == ['', 'pool-a', 'pool-b']

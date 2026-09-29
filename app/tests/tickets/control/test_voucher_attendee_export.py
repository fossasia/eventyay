import datetime
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now

from eventyay.base.exporters.vouchers import VoucherAttendeeListExporter
from eventyay.base.models import (
    Event,
    Order,
    OrderPosition,
    Organizer,
    Product,
    Team,
    User,
    WaitingListEntry,
)


HEADERS = [
    'Voucher code',
    'Voucher tag',
    'Status',
    'Attendee name',
    'Attendee email',
    'Order code',
    'Order status',
    'Order date',
    'Product',
]


@pytest.fixture
def event():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(organizer=organizer, name='Dummy', slug='dummy', date_from=now())
    event.settings.set('timezone', 'UTC')
    return event


@pytest.fixture
def ticket(event):
    return Product.objects.create(event=event, name='Ticket', default_price=23, admission=True)


def create_order(event, ticket, voucher, code, name, email, status=Order.STATUS_PAID):
    order = Order.objects.create(
        code=code,
        event=event,
        email='buyer@example.com',
        status=status,
        datetime=datetime.datetime(2026, 1, 2, 10, 0, tzinfo=datetime.UTC),
        expires=now() + datetime.timedelta(days=10),
        total=Decimal('23'),
        locale='en',
    )
    OrderPosition.objects.create(
        order=order,
        product=ticket,
        price=Decimal('23'),
        voucher=voucher,
        attendee_name_parts={'full_name': name, '_scheme': 'full'} if name else {},
        attendee_email=email,
    )
    return order


def mark_sent(voucher, email, name):
    voucher.log_action('eventyay.voucher.sent', data={'recipient': email, 'name': name})


def export_rows(event, **form_data):
    rows = [[str(value) for value in row] for row in VoucherAttendeeListExporter(event).iterate_list(form_data)]
    assert rows[0] == HEADERS
    return rows[1:]


@pytest.mark.django_db
def test_export_lists_attendees_with_voucher_status(event, ticket):
    sent = event.vouchers.create(code='ABC123', tag='speakers')
    mark_sent(sent, 'john@example.com', 'John Doe')
    redeemed = event.vouchers.create(code='ABC124', tag='speakers')
    create_order(event, ticket, redeemed, 'ORDER1', 'Jane Doe', 'jane@example.com')
    event.vouchers.create(code='ABC125', tag='speakers')
    event.vouchers.create(code='ABC126', tag='speakers', valid_until=now() - datetime.timedelta(days=1))

    assert export_rows(event) == [
        ['ABC123', 'speakers', 'Sent', 'John Doe', 'john@example.com', '', '', '', ''],
        [
            'ABC124',
            'speakers',
            'Redeemed',
            'Jane Doe',
            'jane@example.com',
            'ORDER1',
            'paid',
            '2026-01-02 10:00:00 UTC',
            'Ticket',
        ],
        ['ABC125', 'speakers', 'Not redeemed', '', '', '', '', '', ''],
        ['ABC126', 'speakers', 'Expired', '', '', '', '', '', ''],
    ]


@pytest.mark.django_db
def test_export_lists_every_redemption_of_multi_use_voucher(event, ticket):
    voucher = event.vouchers.create(code='GROUP', max_usages=3)
    create_order(event, ticket, voucher, 'ORDER1', 'Jane Doe', 'jane@example.com')
    create_order(event, ticket, voucher, 'ORDER2', '', '', status=Order.STATUS_PENDING)

    rows = export_rows(event)

    assert [row[2:7] for row in rows] == [
        ['Redeemed', 'Jane Doe', 'jane@example.com', 'ORDER1', 'paid'],
        ['Redeemed', '', 'buyer@example.com', 'ORDER2', 'pending'],
    ]


@pytest.mark.django_db
def test_export_ignores_canceled_orders(event, ticket):
    voucher = event.vouchers.create(code='ABC123')
    create_order(event, ticket, voucher, 'ORDER1', 'Jane Doe', 'jane@example.com', status=Order.STATUS_CANCELED)

    assert export_rows(event) == [['ABC123', '', 'Not redeemed', '', '', '', '', '', '']]


@pytest.mark.django_db
def test_export_filters_by_tag(event, ticket):
    event.vouchers.create(code='ABC123', tag='speakers')
    event.vouchers.create(code='XYZ999', tag='press')
    event.vouchers.create(code='NOTAG')

    tag_field = VoucherAttendeeListExporter(event).export_form_fields['tag']
    assert [value for value, label in tag_field.choices] == ['', 'press', 'speakers']
    assert [row[0] for row in export_rows(event, tag='speakers')] == ['ABC123']


@pytest.mark.django_db
def test_export_filters_by_code(event, ticket):
    event.vouchers.create(code='ABC123')
    event.vouchers.create(code='ABC124')

    assert [row[0] for row in export_rows(event, code=' abc123 ')] == ['ABC123']


@pytest.mark.django_db
def test_export_filters_by_status(event, ticket):
    redeemed = event.vouchers.create(code='ABC123')
    create_order(event, ticket, redeemed, 'ORDER1', 'Jane Doe', 'jane@example.com')
    sent = event.vouchers.create(code='ABC124')
    mark_sent(sent, 'john@example.com', 'John Doe')

    assert [row[0] for row in export_rows(event, status='redeemed')] == ['ABC123']
    assert [row[0] for row in export_rows(event, status='unredeemed')] == ['ABC124']


@pytest.mark.django_db
def test_export_skips_malformed_sent_log_entries(event):
    voucher = event.vouchers.create(code='ABC123')
    voucher.log_action('eventyay.voucher.sent', data={'name': 'John Doe'})

    assert export_rows(event) == [['ABC123', '', 'Not redeemed', '', '', '', '', '', '']]


@pytest.mark.django_db
def test_export_excludes_waiting_list_vouchers(event, ticket):
    event.vouchers.create(code='ABC123')
    waiting_list_voucher = event.vouchers.create(code='WAITING')
    WaitingListEntry.objects.create(
        event=event,
        product=ticket,
        email='waiting@example.com',
        voucher=waiting_list_voucher,
    )

    assert [row[0] for row in export_rows(event)] == ['ABC123']


@pytest.fixture
def team_user(event):
    user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
    team = Team.objects.create(organizer=event.organizer, can_view_vouchers=True)
    team.members.add(user)
    team.limit_events.add(event)
    return team, user


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_voucher_list_links_to_export_only_with_order_permission(client, event, team_user):
    team, user = team_user
    event.vouchers.create(code='ABC123')
    client.force_login(user)
    url = reverse('control:event.vouchers', kwargs={'organizer': event.organizer.slug, 'event': event.slug})

    assert 'identifier=voucherattendees' not in client.get(url).content.decode()

    team.can_view_orders = True
    team.save()
    assert 'identifier=voucherattendees' in client.get(url).content.decode()


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_import_export_page_lists_voucher_attendee_exporter(client, event, team_user):
    team, user = team_user
    team.can_view_orders = True
    team.save()
    client.force_login(user)

    response = client.get(
        reverse('control:event.orders.import_export', kwargs={'organizer': event.organizer.slug, 'event': event.slug}),
        {'identifier': 'voucherattendees'},
    )

    doc = BeautifulSoup(response.content.decode(), 'lxml')
    assert doc.select_one('input[name="exporter"][value="voucherattendees"]')

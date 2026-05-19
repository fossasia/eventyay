from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import Event, Order, OrderPosition, Organizer, Product, User
from eventyay.base.services.user import (
    admin_public_fields_with_email_fallback,
    build_admin_ticket_rows_by_token,
    resolve_wikimedia_usernames_by_email,
)
from eventyay.eventyay_common.utils import encode_email


@pytest.fixture
def event_and_item():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy-video-users')
    event = Event.objects.create(
        organizer=organizer,
        name='Dummy Event',
        slug='dummy-event',
        date_from=now(),
    )
    product = Product.objects.create(
        event=event,
        name='Ticket',
        default_price=Decimal('23.00'),
    )
    with scope(organizer=organizer):
        yield event, product


@pytest.mark.django_db
def test_admin_wikimedia_username_falls_back_to_account_email():
    User.objects.create(
        email='wiki-fallback@example.org',
        wikimedia_username='WikiUser42',
    )

    user_row = {
        'token_id': 'ABC1234',
        'moderation_state': '',
        'email': '',
        'profile': {},
        'wikimedia_username': '',
    }
    ticket_by_token = {
        'ABC1234': {
            'contact_email': 'wiki-fallback@example.org',
            'order_code': 'ORD123',
            'ticket_code': 'TCK123',
        }
    }

    email_to_wikimedia = resolve_wikimedia_usernames_by_email(
        ['wiki-fallback@example.org']
    )
    data = admin_public_fields_with_email_fallback(
        user_row, ticket_by_token, email_to_wikimedia
    )

    assert data['email'] == 'wiki-fallback@example.org'
    assert data['wikimedia_username'] == 'WikiUser42'


@pytest.mark.django_db
def test_build_admin_ticket_rows_by_token_prefers_pseudonymization_ids(event_and_item):
    event, product = event_and_item
    order = Order.objects.create(
        code='PSEUD1',
        event=event,
        email='pseudo@example.org',
        status=Order.STATUS_PAID,
        datetime=now(),
        expires=now() + timedelta(days=1),
        total=Decimal('23.00'),
        locale='en',
    )
    pos = OrderPosition.objects.create(
        order=order,
        item=product,
        price=Decimal('23.00'),
        pseudonymization_id='ABC1234',
        secret='SECR1',
    )

    rows = build_admin_ticket_rows_by_token(event.id, ['ABC1234'])

    assert rows['ABC1234']['order_code'] == 'PSEUD1'
    assert rows['ABC1234']['ticket_code'] == pos.secret
    assert rows['ABC1234']['contact_email'] == 'pseudo@example.org'


@pytest.mark.django_db
def test_build_admin_ticket_rows_by_token_hashed_uid_uses_latest_paid_order(event_and_item):
    event, product = event_and_item
    email = 'hash@example.org'

    paid_old = Order.objects.create(
        code='OLDPA',
        event=event,
        email=email,
        status=Order.STATUS_PAID,
        datetime=now() - timedelta(days=2),
        expires=now() + timedelta(days=1),
        total=Decimal('23.00'),
        locale='en',
    )
    OrderPosition.objects.create(
        order=paid_old,
        item=product,
        price=Decimal('23.00'),
        secret='OLD1',
    )

    paid_new = Order.objects.create(
        code='NEWPA',
        event=event,
        email=email,
        status=Order.STATUS_PAID,
        datetime=now() - timedelta(days=1),
        expires=now() + timedelta(days=1),
        total=Decimal('23.00'),
        locale='en',
    )
    OrderPosition.objects.create(
        order=paid_new,
        item=product,
        price=Decimal('23.00'),
        secret='NEW1',
    )

    pending_newer = Order.objects.create(
        code='PEND1',
        event=event,
        email=email,
        status=Order.STATUS_PENDING,
        datetime=now(),
        expires=now() + timedelta(days=1),
        total=Decimal('23.00'),
        locale='en',
    )
    OrderPosition.objects.create(
        order=pending_newer,
        item=product,
        price=Decimal('23.00'),
        secret='PEND1',
    )

    token = encode_email(email)
    rows = build_admin_ticket_rows_by_token(event.id, [token])

    assert rows[token]['order_code'] == 'NEWPA'
    assert rows[token]['ticket_code'] == 'NEW1'
    assert rows[token]['contact_email'] == email


@pytest.mark.django_db
def test_build_admin_ticket_rows_by_token_ignores_non_paid_orders(event_and_item):
    event, product = event_and_item
    email = 'pending@example.org'
    Order.objects.create(
        code='PEND1',
        event=event,
        email=email,
        status=Order.STATUS_PENDING,
        datetime=now(),
        expires=now() + timedelta(days=1),
        total=Decimal('23.00'),
        locale='en',
    )
    token = encode_email(email)
    rows = build_admin_ticket_rows_by_token(event.id, [token])
    assert token not in rows


@pytest.mark.django_db
def test_build_admin_ticket_rows_by_token_multiple_positions_same_order(event_and_item):
    event, product = event_and_item
    email = 'multi@example.org'
    order = Order.objects.create(
        code='MULTI1',
        event=event,
        email=email,
        status=Order.STATUS_PAID,
        datetime=now(),
        expires=now() + timedelta(days=1),
        total=Decimal('46.00'),
        locale='en',
    )
    OrderPosition.objects.create(
        order=order,
        item=product,
        price=Decimal('23.00'),
        secret='SEC1',
        positionid=1,
    )
    OrderPosition.objects.create(
        order=order,
        item=product,
        price=Decimal('23.00'),
        secret='SEC2',
        positionid=2,
    )
    token = encode_email(email)
    rows = build_admin_ticket_rows_by_token(event.id, [token])
    assert rows[token]['order_code'] == 'MULTI1'
    # Should pick first position by positionid
    assert rows[token]['ticket_code'] == 'SEC1'


@pytest.mark.django_db
def test_build_admin_ticket_rows_by_token_ignores_invalid_tokens(event_and_item):
    event, item = event_and_item
    # Not 7 hex chars
    rows = build_admin_ticket_rows_by_token(event.id, ['not-hex', '123456', '12345678'])
    assert rows == {}

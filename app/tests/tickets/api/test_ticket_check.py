"""Tests for the CustomerOrderCheckView (ticket-check) endpoint.

Issue: #3903 – the endpoint was permanently disabled and always returned HTTP 501.
These tests verify that the re-implemented endpoint works correctly.
"""
import datetime
from decimal import Decimal

import pytest

from eventyay.base.models import Order, OrderPosition


# ---------------------------------------------------------------------------
# Shared helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def item(event):
    return event.products.create(name='General Admission', default_price=Decimal('50.00'))


@pytest.fixture
def order(event, item):
    """A paid order with one position."""
    o = Order.objects.create(
        code='TCKTST',
        event=event,
        email='buyer@example.com',
        status=Order.STATUS_PAID,
        secret='abcdefgh12345678',
        datetime=datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc),
        expires=datetime.datetime(2024, 2, 15, 12, 0, 0, tzinfo=datetime.timezone.utc),
        total=Decimal('50.00'),
        locale='en',
    )
    OrderPosition.objects.create(
        order=o,
        product=item,
        variation=None,
        price=Decimal('50.00'),
        attendee_name_cached='Jane Doe',
        attendee_email='jane@example.com',
        secret='positionsecretxyz',
    )
    return o


def url(organizer, event):
    return f'/api/v1/{organizer.slug}/{event.slug}/ticket-check'


# ---------------------------------------------------------------------------
# Test: endpoint is no longer disabled (regression guard)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ticket_check_not_disabled(client, organizer, event, order):
    """The endpoint must not return 501 for any valid request."""
    resp = client.post(
        url(organizer, event),
        data={'email': order.email, 'code': order.code},
        content_type='application/json',
    )
    assert resp.status_code != 501, (
        'ticket-check endpoint is still disabled (returns 501)'
    )


# ---------------------------------------------------------------------------
# 400 – missing criteria
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ticket_check_missing_criteria_returns_400(client, organizer, event, order):
    # Missing both
    resp = client.post(url(organizer, event), data={}, content_type='application/json')
    assert resp.status_code == 400
    assert 'detail' in resp.json()

    # Missing code
    resp = client.post(url(organizer, event), data={'email': order.email}, content_type='application/json')
    assert resp.status_code == 400

    # Missing email
    resp = client.post(url(organizer, event), data={'code': order.code}, content_type='application/json')
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 404 – event does not exist
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ticket_check_unknown_event_returns_404(client, organizer, event, order):
    resp = client.post(
        f'/api/v1/{organizer.slug}/nonexistent-event/ticket-check',
        data={'email': order.email, 'code': order.code},
        content_type='application/json',
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 404 – no matching orders
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ticket_check_no_match_returns_404(client, organizer, event, order):
    resp = client.post(
        url(organizer, event),
        data={'email': 'nobody@example.com', 'code': order.code},
        content_type='application/json',
    )
    assert resp.status_code == 404

    resp = client.post(
        url(organizer, event),
        data={'email': order.email, 'code': 'WRONG'},
        content_type='application/json',
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 200 – combined email + code filter
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ticket_check_by_email_and_code(client, organizer, event, order):
    resp = client.post(
        url(organizer, event),
        data={'email': order.email, 'code': order.code},
        content_type='application/json',
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert data['code'] == order.code
    assert data['status'] == order.status
    assert data['email'] == order.email


@pytest.mark.django_db
def test_ticket_check_email_is_case_insensitive(client, organizer, event, order):
    resp = client.post(
        url(organizer, event),
        data={'email': order.email.upper(), 'code': order.code},
        content_type='application/json',
    )
    assert resp.status_code == 200


@pytest.mark.django_db
def test_ticket_check_code_lowercase_accepted(client, organizer, event, order):
    resp = client.post(
        url(organizer, event),
        data={'email': order.email, 'code': order.code.lower()},
        content_type='application/json',
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 200 – response contains positions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ticket_check_response_includes_positions(client, organizer, event, order):
    resp = client.post(
        url(organizer, event),
        data={'email': order.email, 'code': order.code},
        content_type='application/json',
    )
    assert resp.status_code == 200
    data = resp.json()
    positions = data['positions']
    assert len(positions) == 1
    pos = positions[0]
    assert 'product' in pos
    assert 'price' in pos
    assert 'attendee_name' in pos
    assert 'attendee_email' in pos
    assert pos['attendee_name'] == 'Jane Doe'
    assert pos['attendee_email'] == 'jane@example.com'


# ---------------------------------------------------------------------------
# 200 – pending and expired orders
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ticket_check_pending_order(client, organizer, event, order):
    order.status = Order.STATUS_PENDING
    order.save()
    resp = client.post(
        url(organizer, event),
        data={'email': order.email, 'code': order.code},
        content_type='application/json',
    )
    assert resp.status_code == 200
    assert resp.json()['status'] == Order.STATUS_PENDING


@pytest.mark.django_db
def test_ticket_check_expired_order(client, organizer, event, order):
    order.status = Order.STATUS_EXPIRED
    order.save()
    resp = client.post(
        url(organizer, event),
        data={'email': order.email, 'code': order.code},
        content_type='application/json',
    )
    assert resp.status_code == 200
    assert resp.json()['status'] == Order.STATUS_EXPIRED

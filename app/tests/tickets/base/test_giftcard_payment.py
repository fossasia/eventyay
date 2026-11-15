from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.utils.timezone import now

from eventyay.base.models import Event, GiftCard, GiftCardTransaction, Organizer
from eventyay.base.payment import GiftCardPayment
from eventyay.base.services.cart import VOUCHER_RATE_LIMIT_WINDOW, VoucherRateLimitUnavailable


@pytest.fixture
def event():
    o = Organizer.objects.create(name='Dummy', slug='dummy')
    return Event.objects.create(organizer=o, name='Dummy', slug='dummy', date_from=now(), currency='USD')


@pytest.mark.django_db
def test_giftcard_checkout_prepare_applies_gift_card(event):
    valid_gc = GiftCard.objects.create(issuer=event.organizer, currency='USD')
    GiftCardTransaction.objects.create(card=valid_gc, value=Decimal('10.00'))

    prov = GiftCardPayment(event)

    request = MagicMock()
    request.event = event
    request.META = {'REMOTE_ADDR': '192.0.2.1'}
    request.POST = {'giftcard': valid_gc.secret}

    cs = {'gift_cards': [], 'payment': 'giftcard'}
    cart = {
        'positions': [MagicMock(total=Decimal('50.00'))],
        'invoice_address': None,
        'raw': [],
    }

    with (
        patch('eventyay.base.payment.get_cart', return_value=[]),
        patch('eventyay.base.payment.cart_session', return_value=cs),
    ):
        prov.checkout_prepare(request, cart)

        assert cs['gift_cards'] == [valid_gc.pk]
        assert cs.get('payment') is None  # because remainder > 0, it asks for a new payment method


@pytest.mark.django_db
def test_giftcard_checkout_rate_limit_returns_429(event):
    provider = GiftCardPayment(event)
    request = MagicMock()
    request.event = event
    request.META = {'REMOTE_ADDR': '192.0.2.1'}
    request.POST = {'giftcard': 'wrong-code'}

    with (
        patch('eventyay.base.payment.get_cart', return_value=[]),
        patch('eventyay.base.payment.cart_session', return_value={}),
        patch('eventyay.base.payment.reserve_voucher_attempt', return_value=(None, False)),
        patch('eventyay.base.payment.messages.error') as add_error,
    ):
        response = provider.checkout_prepare(request, {})

    assert response.status_code == 429
    assert response['Retry-After'] == str(VOUCHER_RATE_LIMIT_WINDOW)
    add_error.assert_not_called()


@pytest.mark.django_db
def test_giftcard_payment_rate_limit_returns_429(event):
    provider = GiftCardPayment(event)
    request = MagicMock()
    request.event = event
    request.META = {'REMOTE_ADDR': '192.0.2.1'}
    request.POST = {'giftcard': 'wrong-code'}
    payment = MagicMock()
    payment.order.positions.all.return_value = []

    with (
        patch('eventyay.base.payment.reserve_voucher_attempt', return_value=(None, False)),
        patch('eventyay.base.payment.messages.error') as add_error,
    ):
        response = provider.payment_prepare(request, payment)

    assert response.status_code == 429
    assert response['Retry-After'] == str(VOUCHER_RATE_LIMIT_WINDOW)
    add_error.assert_not_called()


@pytest.mark.django_db
def test_giftcard_checkout_rate_limit_unavailable_returns_503(event):
    provider = GiftCardPayment(event)
    request = MagicMock()
    request.event = event
    request.POST = {'giftcard': 'wrong-code'}

    with (
        patch('eventyay.base.payment.get_cart', return_value=[]),
        patch('eventyay.base.payment.cart_session', return_value={}),
        patch(
            'eventyay.base.payment.reserve_voucher_attempt',
            side_effect=VoucherRateLimitUnavailable,
        ),
    ):
        response = provider.checkout_prepare(request, {})

    assert response.status_code == 503
    assert response['Retry-After'] == str(VOUCHER_RATE_LIMIT_WINDOW)

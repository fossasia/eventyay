from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.utils.timezone import now

from eventyay.base.models import Event, GiftCard, Organizer
from eventyay.base.payment import GiftCardPayment

@pytest.fixture
def event():
    o = Organizer.objects.create(name='Dummy', slug='dummy')
    return Event.objects.create(organizer=o, name='Dummy', slug='dummy', date_from=now(), currency='USD')

@pytest.mark.django_db
def test_giftcard_checkout_prepare_removes_stale_mismatched_card(event):
    valid_gc = GiftCard.objects.create(issuer=event.organizer, currency='USD', value=Decimal('10.00'))
    stale_gc = GiftCard.objects.create(issuer=event.organizer, currency='EUR', value=Decimal('100.00'))
    
    prov = GiftCardPayment(event)
    
    request = MagicMock()
    request.event = event
    request.META = {'REMOTE_ADDR': '192.0.2.1'}
    request.POST = {'giftcard': valid_gc.secret}
    
    cs = {'gift_cards': [stale_gc.pk], 'payment': 'giftcard'}
    cart = {
        'positions': [MagicMock(total=Decimal('50.00'))],
        'invoice_address': None,
        'raw': [],
    }
    
    with patch('eventyay.base.payment.get_cart', return_value=[]), \
         patch('eventyay.base.payment.cart_session', return_value=cs):
         
         prov.checkout_prepare(request, cart)
         
         # The stale EUR card should have been removed, leaving only the valid USD card.
         assert cs['gift_cards'] == [valid_gc.pk]
         assert cs.get('payment') is None # because remainder > 0, it asks for a new payment method


@pytest.mark.django_db
def test_giftcard_checkout_rate_limit_returns_retry_after(event):
    provider = GiftCardPayment(event)
    request = MagicMock()
    request.event = event
    request.META = {'REMOTE_ADDR': '192.0.2.1'}
    request.POST = {'giftcard': 'wrong-code'}

    with (
        patch('eventyay.base.payment.get_cart', return_value=[]),
        patch('eventyay.base.payment.cart_session', return_value={}),
        patch('eventyay.base.payment.reserve_voucher_attempt', return_value=(None, False)),
    ):
        response = provider.checkout_prepare(request, {})

    assert response.status_code == 429
    assert response['Retry-After'] == '300'

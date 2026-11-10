import pytest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from django.core.cache import cache
from django.test import RequestFactory, override_settings
from eventyay.base.models import Event, Organizer, GiftCard, Product as Item, CartPosition
from eventyay.base.payment import GiftCardPayment
from eventyay.base.services.cart import VOUCHER_RATE_LIMIT_MAX, _voucher_rate_limit_key, reserve_voucher_attempt
from django.utils.timezone import now

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
@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    'LOCATION': 'voucher-rate-limit-giftcard-failure',
}})
def test_giftcard_failed_lookup_counts_toward_voucher_limit(event):
    cache.clear()
    request = RequestFactory().post('/', {'giftcard': 'unknown-card'})
    request.event = event
    request.META['REMOTE_ADDR'] = '192.0.2.2'
    provider = GiftCardPayment(event)
    cart = {'positions': [], 'invoice_address': None, 'raw': []}

    with patch('eventyay.base.payment.get_cart', return_value=[]), \
         patch('eventyay.base.payment.cart_session', return_value={'gift_cards': []}), \
         patch('eventyay.base.payment.messages.error'):
        provider.checkout_prepare(request, cart)

    key = _voucher_rate_limit_key(request)
    assert cache.get(key) == 1
    for _ in range(VOUCHER_RATE_LIMIT_MAX - 1):
        assert reserve_voucher_attempt(request)[1]
    assert not reserve_voucher_attempt(request)[1]
    cache.clear()


@pytest.mark.django_db
@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    'LOCATION': 'voucher-rate-limit-giftcard-block',
}})
def test_giftcard_rate_limit_blocks_lookup(event):
    cache.clear()
    request = RequestFactory().post('/', {'giftcard': 'unknown-card'})
    request.event = event
    request.META['REMOTE_ADDR'] = '192.0.2.3'
    provider = GiftCardPayment.__new__(GiftCardPayment)
    accepted_gift_cards = MagicMock()
    provider.event = SimpleNamespace(
        pk=event.pk,
        organizer=SimpleNamespace(accepted_gift_cards=accepted_gift_cards),
        testmode=False,
        private_testmode_tickets_enabled=False,
        currency=event.currency,
    )
    for _ in range(VOUCHER_RATE_LIMIT_MAX):
        assert reserve_voucher_attempt(request)[1]
    assert cache.get(_voucher_rate_limit_key(request)) == VOUCHER_RATE_LIMIT_MAX

    with patch('eventyay.base.payment.get_cart', return_value=[]), \
         patch('eventyay.base.payment.cart_session', return_value={'gift_cards': []}):
        response = provider.checkout_prepare(request, {'positions': []})

    accepted_gift_cards.get.assert_not_called()
    assert response.status_code == 429
    assert response['Retry-After'] == '300'
    cache.clear()


@pytest.mark.django_db
@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    'LOCATION': 'voucher-rate-limit-giftcard-payment-prepare',
}})
def test_giftcard_payment_prepare_returns_rate_limit_response(event):
    cache.clear()
    request = RequestFactory().post('/', {'giftcard': 'unknown-card'})
    request.event = event
    request.META['REMOTE_ADDR'] = '192.0.2.4'
    provider = GiftCardPayment.__new__(GiftCardPayment)
    provider.event = event
    payment = MagicMock()
    payment.order.positions.all.return_value = []
    for _ in range(VOUCHER_RATE_LIMIT_MAX):
        assert reserve_voucher_attempt(request)[1]

    response = provider.payment_prepare(request, payment)

    assert response.status_code == 429
    assert response['Retry-After'] == '300'
    cache.clear()

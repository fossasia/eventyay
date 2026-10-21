from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

import pytest
from django.db import DatabaseError, close_old_connections
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import Event, Order, OrderPosition, Organizer, Product
from eventyay.base.services.orders import (
    OrderChangeManager,
    OrderError,
    _cancel_order,
    reactivate_order,
    signal_listener_issue_giftcards,
)


@pytest.fixture
def gift_order():
    organizer = Organizer.objects.create(name='Gift cards', slug='gift-cards')
    with scope(organizer=organizer):
        event = Event.objects.create(organizer=organizer, name='Cards', slug='cards', date_from=now())
    with scope(event=event, organizer=organizer):
        product = Product.objects.create(event=event, name='50 EUR card', default_price=50, issue_giftcard=True)
        order = Order.objects.create(event=event, status=Order.STATUS_PAID, total=25, email='buyer@example.com')
        order.payments.create(state='confirmed', provider='manual', amount=25)
        position = OrderPosition.objects.create(order=order, product=product, price=25, price_before_voucher=50)
        event.settings.cancel_allow_user_paid = True
        with patch('eventyay.base.services.orders.tickets.invalidate_cache.apply_async'):
            yield event, order, position


@pytest.mark.django_db
@pytest.mark.parametrize('face,paid', [(50, 25), (50, 0), (None, 25), (0, 0)])
def test_issuance_uses_original_price_once(gift_order, face, paid):
    event, order, position = gift_order
    position.price_before_voucher = face
    position.price = paid
    position.save()
    for _ in range(2):
        signal_listener_issue_giftcards(event, order)
    cards = list(position.issued_gift_cards.all())
    expected = Decimal(face if face is not None else paid)
    assert sum(card.value for card in cards) == expected
    assert len(cards) == (1 if expected else 0)


@pytest.mark.django_db
@pytest.mark.parametrize('legacy', [False, True])
def test_cancel_and_reactivate_preserve_actual_issued_credit(gift_order, legacy):
    event, order, position = gift_order
    if legacy:
        card = event.organizer.issued_gift_cards.create(currency=event.currency, issued_in=position)
        card.transactions.create(value=25, order=order)
    else:
        signal_listener_issue_giftcards(event, order)
        card = position.issued_gift_cards.get()
    original = card.value
    _cancel_order(order, send_mail=False)
    assert card.value == 0
    reactivate_order(order, force=True)
    assert card.value == original
    assert position.issued_gift_cards.count() == 1
    assert order.status == Order.STATUS_PAID


@pytest.mark.django_db
def test_redeemed_face_value_cannot_be_cancelled(gift_order):
    event, order, position = gift_order
    signal_listener_issue_giftcards(event, order)
    card = position.issued_gift_cards.get()
    assert position in order.user_cancelable_positions
    card.transactions.create(value=-10)
    assert position not in Order.objects.get(pk=order.pk).user_cancelable_positions
    with pytest.raises(OrderError):
        _cancel_order(order, send_mail=False)
    assert card.value == 40


@pytest.mark.django_db
def test_position_cancellation_reverses_full_credit(gift_order):
    event, order, position = gift_order
    signal_listener_issue_giftcards(event, order)
    card = position.issued_gift_cards.get()
    other = Product.objects.create(event=event, name='Other', default_price=0)
    OrderPosition.objects.create(order=order, product=other, price=0)
    manager = OrderChangeManager(order)
    manager.cancel(position)
    manager.commit(check_quotas=False)
    assert card.value == 0


@pytest.mark.django_db
def test_reactivation_restores_each_card_once(gift_order):
    event, order, position = gift_order
    cards = []
    for value in (10, 15):
        card = event.organizer.issued_gift_cards.create(currency=event.currency, issued_in=position)
        card.transactions.create(value=value, order=order)
        cards.append(card)
    for _ in range(2):
        _cancel_order(order, send_mail=False)
        assert [card.value for card in cards] == [0, 0]
        reactivate_order(order, force=True)
        assert [card.value for card in cards] == [10, 15]
        assert position.issued_gift_cards.count() == 2


@pytest.mark.django_db
def test_stale_reactivation_does_not_duplicate_credit(gift_order):
    event, order, position = gift_order
    signal_listener_issue_giftcards(event, order)
    _cancel_order(order, send_mail=False)
    stale_order = Order.objects.get(pk=order.pk)
    reactivate_order(order, force=True)
    with pytest.raises(OrderError, match='not canceled'):
        reactivate_order(stale_order, force=True)
    assert position.issued_gift_cards.get().value == 50


@pytest.mark.django_db
def test_stale_paid_signal_does_not_issue_pending_order(gift_order):
    event, order, position = gift_order
    Order.objects.filter(pk=order.pk).update(status=Order.STATUS_PENDING)
    signal_listener_issue_giftcards(event, order)
    assert not position.issued_gift_cards.exists()


@pytest.mark.django_db
def test_issuance_failure_rolls_back_order_change(gift_order):
    event, order, position = gift_order
    other = Product.objects.create(event=event, name='Other', default_price=0)
    manager = OrderChangeManager(order)
    manager.add_position(other, variation=None, price=Decimal('0'))
    with patch('eventyay.base.models.giftcards.GiftCardTransaction.save', side_effect=DatabaseError('ledger failed')):
        with pytest.raises(DatabaseError, match='ledger failed'):
            manager.commit(check_quotas=False)
    assert order.positions.count() == 1
    assert not position.issued_gift_cards.exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_signals_issue_one_card(gift_order):
    event, order, position = gift_order
    barrier = Barrier(2)

    def issue():
        close_old_connections()
        try:
            with scope(event=event, organizer=event.organizer):
                barrier.wait(timeout=10)
                signal_listener_issue_giftcards(event, order)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(issue) for _ in range(2)]
        for future in futures:
            future.result(timeout=20)
    assert position.issued_gift_cards.count() == 1
    assert position.issued_gift_cards.get().value == 50

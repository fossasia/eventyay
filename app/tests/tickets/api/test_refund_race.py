import threading
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.db import connection
from django.utils.timezone import now
from django_scopes import scopes_disabled
from rest_framework.test import APIClient

from eventyay.base.models import Order, OrderPayment


@pytest.fixture
def paid_order(event):
    with scopes_disabled():
        o = Order.objects.create(
            code='RACE1',
            event=event,
            email='dummy@dummy.test',
            status=Order.STATUS_PAID,
            secret='k24fiuwvu8kxz3y1',
            datetime=now(),
            expires=now(),
            total=Decimal('100.00'),
            locale='en',
        )
        o.payments.create(
            provider='banktransfer',
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            amount=Decimal('100.00'),
            payment_date=now(),
        )
    return o


@pytest.mark.django_db(transaction=True)
def test_concurrent_refunds_exceed_payment_amount(organizer, event, team, paid_order, monkeypatch):
    """
    Two refund requests for the full payment amount are sent at the same time.
    The barrier makes both read ``refunded_amount`` (== 0) before either creates its refund,
    which is exactly what happens in a real race. Expected: one request is rejected.
    """
    team.can_view_orders = True
    team.can_change_orders = True
    team.all_events = True
    team.save()
    token = team.tokens.create(name='Race').token

    provider = SimpleNamespace(
        payment_refund_supported=lambda payment: True,
        payment_partial_refund_supported=lambda payment: True,
        execute_refund=lambda refund: None,
    )
    monkeypatch.setattr(OrderPayment, 'payment_provider', property(lambda self: provider))
    from eventyay.base.models import OrderRefund

    monkeypatch.setattr(OrderRefund, 'payment_provider', property(lambda self: provider))

    barrier = threading.Barrier(2, timeout=2)
    original = OrderPayment.refunded_amount.fget

    def refunded_amount_then_wait(self):
        value = original(self)
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            # With the payment row locked, the second request cannot reach this point
            # until the first one is done, so the barrier is never completed.
            pass
        return value

    monkeypatch.setattr(OrderPayment, 'refunded_amount', property(refunded_amount_then_wait))

    url = '/api/v1/organizers/{}/events/{}/orders/{}/payments/1/refund/'.format(
        organizer.slug, event.slug, paid_order.pk
    )
    results = []

    def fire():
        try:
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION='Token ' + token)
            results.append(client.post(url, format='json', data={'amount': '100.00', 'mark_canceled': False}))
        finally:
            connection.close()

    threads = [threading.Thread(target=fire) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print('STATUS CODES:', [r.status_code for r in results])
    with scopes_disabled():
        refunds = list(paid_order.refunds.values_list('amount', flat=True))
    print('REFUNDS CREATED:', refunds, 'TOTAL:', sum(refunds), 'PAYMENT AMOUNT: 100.00')

    assert sum(refunds) <= Decimal('100.00'), 'Over-refund: refunded {} of a 100.00 payment'.format(sum(refunds))
    assert sorted(r.status_code for r in results) == [200, 400]

import threading
import time
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.db import connection
from django.db.models.query import QuerySet
from django.utils.timezone import now
from django_scopes import scopes_disabled
from rest_framework.test import APIClient

from eventyay.base.models import Order, OrderPayment, OrderRefund


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
    A short sleep after ``refunded_amount`` is read keeps both requests in the check-then-create
    window, which is what happens in a real race. Expected: one request is rejected.
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
    monkeypatch.setattr(OrderRefund, 'payment_provider', property(lambda self: provider))

    # Both requests are released at the same moment. If one of the threads does not show up in
    # time the barrier breaks, the thread records the error and the test fails below.
    start = threading.Barrier(2, timeout=10)
    original = OrderPayment.refunded_amount.fget

    def refunded_amount_slowly(self):
        value = original(self)
        # Widen the window between "read the refunded amount" and "create the refund". Without a
        # lock on the payment both requests read 0 here and both create a refund. With the lock the
        # second request is blocked before this point and sees the first refund instead.
        time.sleep(1)
        return value

    monkeypatch.setattr(OrderPayment, 'refunded_amount', property(refunded_amount_slowly))

    # Record every attempt to lock a payment row, to show that both requests reached the lock.
    lock_attempts = []
    original_select_for_update = QuerySet.select_for_update

    def recording_select_for_update(self, *args, **kwargs):
        if self.model is OrderPayment:
            lock_attempts.append(threading.current_thread().name)
        return original_select_for_update(self, *args, **kwargs)

    monkeypatch.setattr(QuerySet, 'select_for_update', recording_select_for_update)

    url = '/api/v1/organizers/{}/events/{}/orders/{}/payments/1/refund/'.format(
        organizer.slug, event.slug, paid_order.pk
    )
    results = []
    errors = []

    def fire():
        try:
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION='Token ' + token)
            start.wait()
            results.append(client.post(url, format='json', data={'amount': '100.00', 'mark_canceled': False}))
        except Exception as exc:  # noqa: BLE001 - reported by the assertion below
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=fire) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, 'A request thread failed to run: {!r}'.format(errors)
    print('STATUS CODES:', [r.status_code for r in results])
    with scopes_disabled():
        refunds = list(paid_order.refunds.values_list('amount', flat=True))
    print('REFUNDS CREATED:', refunds, 'TOTAL:', sum(refunds), 'PAYMENT AMOUNT: 100.00')

    assert sum(refunds) <= Decimal('100.00'), 'Over-refund: refunded {} of a 100.00 payment'.format(sum(refunds))
    assert sorted(r.status_code for r in results) == [200, 400]
    assert len(lock_attempts) == 2, 'Expected both requests to lock the payment, got {}'.format(lock_attempts)

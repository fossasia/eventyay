from decimal import Decimal

import pytest

# We import from eventyay to match the API View's locking logic
from eventyay.base.models import OrderPayment, OrderRefund


@pytest.mark.django_db
def test_refund_available_amount_includes_created_refunds(token_client, organizer, event, order, scopes_disabled):
    """
    Verifies that the available_amount calculation correctly includes refunds that are
    currently in the 'created' state. This ensures that even if a refund process is
    ongoing (and the lock has been released), a subsequent request will see the
    reserved amount and refuse to over-refund.
    """
    with scopes_disabled():
        # Using the order fixture's payments manager ensures compatibility
        payment = order.payments.create(
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            amount=Decimal('100.00'),
            provider='banktransfer',
        )

        # Simulate an ongoing refund that reached 'created' state but hasn't finished
        order.refunds.create(
            payment=payment,
            source=OrderRefund.REFUND_SOURCE_ADMIN,
            state=OrderRefund.REFUND_STATE_CREATED,
            amount=Decimal('60.00'),
            provider='banktransfer',
        )

    # Now try to refund another 60.00 via API.
    # It should fail because only 100 - 60 = 40.00 are available.
    resp = token_client.post(
        '/api/v1/organizers/{}/events/{}/orders/{}/payments/{}/refund/'.format(
            organizer.slug,
            event.slug,
            order.code,
            payment.pk,
        ),
        format='json',
        data={'amount': '60.00'},
    )

    assert resp.status_code == 400
    assert 'only 40.00 are available to refund' in resp.data['amount'][0]


@pytest.mark.django_db
def test_refund_serialization_locking(token_client, organizer, event, order, monkeypatch, scopes_disabled):
    """
    Verifies that PaymentViewSet.refund uses select_for_update() to lock the payment row.
    Specifically patches the eventyay namespace used by the API view logic.
    """
    select_for_update_called = False
    original_select_for_update = OrderPayment.objects.select_for_update

    def mock_select_for_update(*args, **kwargs):
        nonlocal select_for_update_called
        select_for_update_called = True
        return original_select_for_update(*args, **kwargs)

    # We patch the eventyay-namespaced model because that's what the View uses
    monkeypatch.setattr(OrderPayment.objects, 'select_for_update', mock_select_for_update)

    with scopes_disabled():
        payment = order.payments.create(
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            amount=Decimal('100.00'),
            provider='banktransfer',
        )

    token_client.post(
        '/api/v1/organizers/{}/events/{}/orders/{}/payments/{}/refund/'.format(
            organizer.slug,
            event.slug,
            order.code,
            payment.pk,
        ),
        format='json',
        data={'amount': '100.00'},
    )

    assert select_for_update_called

"""
Test for concurrent refund race condition prevention.

Validates that the select_for_update() fix in OrderPaymentViewSet.refund()
prevents multiple concurrent refunds from exceeding the payment amount.

Related: app/eventyay/api/views/order.py lines 1251-1276
"""
import json
import threading
from decimal import Decimal

import pytest
from django.db import connection
from django.test import Client
from django_scopes import scopes_disabled

from eventyay.base.models.orders import OrderPayment


@pytest.mark.django_db(transaction=True)
class TestConcurrentRefunds:
    """Test suite for concurrent refund race condition prevention."""

    def test_concurrent_refunds_race_condition_prevented(
        self, token_client, organizer, event, order
    ):
        """
        Test that concurrent refund requests are properly serialized.
        
        Two threads attempt to refund $80 each from a $100 payment.
        With select_for_update(): only one succeeds, preventing double refund.
        """
        # Set up a payment with confirmed state
        with scopes_disabled():
            payment = order.payments.first()
            payment.amount = Decimal('100.00')
            payment.state = OrderPayment.PAYMENT_STATE_CONFIRMED
            payment.save()

        results = []
        errors = []
        auth_header = token_client.defaults.get('HTTP_AUTHORIZATION')
        start_barrier = threading.Barrier(2)

        def make_refund_request(amount, barrier):
            """Make a refund request in a separate thread."""
            try:
                barrier.wait()
                
                client = Client()
                client.defaults['HTTP_AUTHORIZATION'] = auth_header
                response = client.post(
                    f'/api/v1/organizers/{organizer.slug}/events/{event.slug}/'
                    f'orders/{order.code}/payments/{payment.local_id}/refund/',
                    data=json.dumps({'amount': str(amount)}),
                    content_type='application/json',
                )
                results.append({
                    'status': response.status_code,
                    'amount': amount,
                    'body': response.content.decode('utf-8')[:500]
                })
            except Exception as e:
                errors.append(str(e))
            finally:
                connection.close()

        thread1 = threading.Thread(target=make_refund_request, args=(Decimal('80.00'), start_barrier))
        thread2 = threading.Thread(target=make_refund_request, args=(Decimal('80.00'), start_barrier))

        thread1.start()
        thread2.start()

        thread1.join(timeout=10)
        thread2.join(timeout=10)

        if thread1.is_alive() or thread2.is_alive():
            pytest.fail(
                f"Test threads did not finish within timeout. "
                f"{{thread1 alive: {{thread1.is_alive()}}}}, thread2 alive: {{thread2.is_alive()}}}}"
            )

        assert len(errors) == 0, f"Thread errors occurred: {errors}"
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"

        status_codes = sorted([r['status'] for r in results])
        assert status_codes == [200, 400], (
            f"Expected [200, 400], got {status_codes}. Results: {results}"
        )

        with scopes_disabled():
            payment.refresh_from_db()
            refunds = list(payment.refunds.all())
            total_refunded = sum(r.amount for r in refunds)

        assert len(refunds) == 1, (
            f"Expected 1 refund, got {len(refunds)}. "
            "Race condition not prevented - select_for_update() may not be working."
        )

        assert total_refunded == Decimal('80.00'), (
            f"Expected $80.00 refunded, got ${total_refunded}. Double refund occurred!"
        )

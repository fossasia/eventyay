"""
Test for concurrent refund race condition prevention.

This test validates that the double refund race condition fix is working correctly.
The fix uses select_for_update() with @transaction.atomic to prevent multiple 
concurrent refunds from succeeding when they would exceed the available refund amount.

Related: Fix for double refund race condition in OrderPaymentViewSet.refund()
Location: app/eventyay/api/views/order.py lines 1251-1276

The fix prevents a TOCTOU (Time-of-check to time-of-use) race condition where:
1. Two threads check available refund amount simultaneously
2. Both see enough funds available
3. Both create refunds, exceeding the payment amount
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
        Test that concurrent refund requests are properly serialized with select_for_update().
        
        Scenario:
        - A payment of $100.00 exists in confirmed state
        - Two concurrent refund requests of $80.00 each are made
        - Without select_for_update(): both would succeed ($160 refunded - BUG!)
        - With select_for_update(): only one succeeds, the other fails with 400
        
        The fix in OrderPaymentViewSet.refund() works as follows:
        1. @transaction.atomic ensures atomicity
        2. queryset.select_for_update() acquires row-level lock on payment
        3. available_amount calculation happens under the lock (prevents TOCTOU)
        4. Second thread waits for the lock, then sees insufficient funds
        
        Expected behavior:
        - One request returns 200 (success)
        - One request returns 400 (insufficient funds)
        - Only $80 is refunded total (not $160)
        - Only 1 refund object exists in database
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

        def make_refund_request(amount):
            """Make a refund request in a separate thread."""
            try:
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
                # Important: close the connection in each thread
                connection.close()

        # Create two concurrent refund requests
        # Each requests $80 of the $100 payment - total would be $160
        # Only one should succeed
        thread1 = threading.Thread(target=make_refund_request, args=(Decimal('80.00'),))
        thread2 = threading.Thread(target=make_refund_request, args=(Decimal('80.00'),))

        # Start both threads to create race condition
        thread1.start()
        thread2.start()

        # Wait for both threads to complete
        thread1.join(timeout=10)
        thread2.join(timeout=10)

        # Verify no exceptions occurred
        assert len(errors) == 0, f"Thread errors occurred: {errors}"

        # Both requests should complete
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"

        # Verify one succeeded (200) and one failed (400)
        status_codes = sorted([r['status'] for r in results])
        assert status_codes == [200, 400], (
            f"Expected [200, 400], got {status_codes}. "
            f"Results: {results}"
        )

        # Verify only one refund was created
        with scopes_disabled():
            payment.refresh_from_db()
            refunds = list(payment.refunds.all())
            total_refunded = sum(r.amount for r in refunds)

        # Should have exactly 1 refund (not 2!)
        assert len(refunds) == 1, (
            f"Expected 1 refund, got {len(refunds)}. "
            "Race condition may not be properly prevented! "
            "The select_for_update() lock may not be working."
        )

        # Total refunded should be $80, not $160 (which would be the double refund bug)
        assert total_refunded == Decimal('80.00'), (
            f"Expected $80.00 refunded, got ${total_refunded}. "
            "Double refund occurred! This is a critical bug."
        )

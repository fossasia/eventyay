"""
Unit tests for Stripe webhook view and update_billing_invoice_information task.
"""
import json
import uuid
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from eventyay.base.models.billing import BillingInvoice
from eventyay.eventyay_common.tasks import update_billing_invoice_information


@pytest.fixture
def organizer(db):
    from eventyay.base.models import Organizer
    return Organizer.objects.create(name="Test Org", slug="test-org-stripe")


@pytest.fixture
def event(db, organizer):
    from datetime import timedelta
    from django.utils import timezone
    from eventyay.base.models import Event
    now = timezone.now()
    return Event.objects.create(
        organizer=organizer, name="Stripe Test Event", slug="stripe-test-event",
        date_from=now + timedelta(days=10), date_to=now + timedelta(days=11),
        currency="USD", locale="en", is_public=True, live=True, email="o@example.com",
    )


@pytest.fixture
def pending_invoice(db, organizer, event):
    """A BillingInvoice in STATUS_PENDING."""
    return BillingInvoice.objects.create(
        organizer=organizer, event=event, status=BillingInvoice.STATUS_PENDING,
        amount="100.00", currency="USD", ticket_fee="100.00", final_ticket_fee="100.00",
        monthly_bill=date.today(), created_by="test", updated_by="test",
    )


@pytest.fixture
def paid_invoice(db, organizer, event):
    """A BillingInvoice already in STATUS_PAID (Stripe retry scenario)."""
    return BillingInvoice.objects.create(
        organizer=organizer, event=event, status=BillingInvoice.STATUS_PAID,
        amount="100.00", currency="USD", ticket_fee="100.00", final_ticket_fee="100.00",
        monthly_bill=date.today(), created_by="test", updated_by="test",
    )


@pytest.fixture
def expired_invoice(db, organizer, event):
    """A BillingInvoice in STATUS_EXPIRED (unexpected for payment success)."""
    return BillingInvoice.objects.create(
        organizer=organizer, event=event, status=BillingInvoice.STATUS_EXPIRED,
        amount="100.00", currency="USD", ticket_fee="100.00", final_ticket_fee="100.00",
        monthly_bill=date.today(), created_by="test", updated_by="test",
    )


def _make_stripe_event(invoice_id=None, event_id="evt_test_123"):
    """Build a minimal fake Stripe webhook event object."""
    metadata = {"invoice_id": invoice_id} if invoice_id else {}
    ev = MagicMock()
    ev.id = event_id
    ev.type = "payment_intent.succeeded"
    ev.data.object.get = lambda key, default=None: metadata if key == "metadata" else default
    return ev


class TestStripeWebhookView:
    """Tests for stripe_webhook_view."""

    def _build_payload(self, invoice_id=None):
        metadata = {"invoice_id": invoice_id} if invoice_id else {}
        return json.dumps(
            {"type": "payment_intent.succeeded", "data": {"object": {"metadata": metadata}}}
        ).encode()

    @patch("eventyay.api.views.stripe.stripe.Webhook.construct_event")
    @patch("eventyay.api.views.stripe.update_billing_invoice_information")
    @patch("eventyay.api.views.stripe.get_stripe_secret_key", return_value="sk_test")
    @patch("eventyay.api.views.stripe.get_stripe_webhook_secret_key", return_value="whsec_test")
    def test_task_not_dispatched_when_invoice_id_missing(
        self, _whsec, _sk, mock_task, mock_construct
    ):
        """Task must NOT be dispatched when invoice_id is absent; still returns 200."""
        from django.test import RequestFactory
        from eventyay.api.views.stripe import stripe_webhook_view

        mock_construct.return_value = _make_stripe_event(invoice_id=None)
        factory = RequestFactory()
        request = factory.post(
            "/api/stripe/webhook/",
            data=self._build_payload(),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=abc",
        )
        response = stripe_webhook_view(request)
        mock_task.delay.assert_not_called()
        assert response.status_code == 200

    @patch("eventyay.api.views.stripe.stripe.Webhook.construct_event")
    @patch("eventyay.api.views.stripe.update_billing_invoice_information")
    @patch("eventyay.api.views.stripe.get_stripe_secret_key", return_value="sk_test")
    @patch("eventyay.api.views.stripe.get_stripe_webhook_secret_key", return_value="whsec_test")
    def test_task_dispatched_when_invoice_id_present(
        self, _whsec, _sk, mock_task, mock_construct
    ):
        """Task must be dispatched exactly once with the correct invoice_id."""
        from django.test import RequestFactory
        from eventyay.api.views.stripe import stripe_webhook_view

        fake_id = str(uuid.uuid4())
        mock_construct.return_value = _make_stripe_event(invoice_id=fake_id)
        factory = RequestFactory()
        request = factory.post(
            "/api/stripe/webhook/",
            data=self._build_payload(invoice_id=fake_id),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=abc",
        )
        response = stripe_webhook_view(request)
        mock_task.delay.assert_called_once_with(invoice_id=fake_id)
        assert response.status_code == 200

    @patch("eventyay.api.views.stripe.stripe.Webhook.construct_event")
    @patch("eventyay.api.views.stripe.update_billing_invoice_information")
    @patch("eventyay.api.views.stripe.get_stripe_secret_key", return_value="sk_test")
    @patch("eventyay.api.views.stripe.get_stripe_webhook_secret_key", return_value="whsec_test")
    def test_warning_logged_when_invoice_id_missing(
        self, _whsec, _sk, mock_task, mock_construct
    ):
        """A WARNING must be logged when invoice_id is absent."""
        from django.test import RequestFactory
        from eventyay.api.views.stripe import stripe_webhook_view

        mock_construct.return_value = _make_stripe_event(invoice_id=None)
        factory = RequestFactory()
        request = factory.post(
            "/api/stripe/webhook/",
            data=self._build_payload(),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=abc",
        )
        with patch("eventyay.api.views.stripe.logger.warning") as mock_warning:
            stripe_webhook_view(request)

        mock_warning.assert_called_once()
        assert "invoice_id missing" in mock_warning.call_args[0][0].lower()


class TestUpdateBillingInvoiceInformationTask:
    """Tests for update_billing_invoice_information Celery task."""

    def test_raises_value_error_on_none_invoice_id(self):
        """invoice_id=None must raise ValueError so Celery marks job as FAILED."""
        with pytest.raises(ValueError, match="invoice_id must not be None or empty"):
            update_billing_invoice_information(invoice_id=None)

    def test_raises_value_error_on_empty_string_invoice_id(self):
        """Same guard must fire for an empty string."""
        with pytest.raises(ValueError, match="invoice_id must not be None or empty"):
            update_billing_invoice_information(invoice_id="")

    @pytest.mark.django_db
    def test_pending_invoice_marked_as_paid(self, pending_invoice):
        """Happy path: PENDING invoice updated to PAID."""
        update_billing_invoice_information(invoice_id=str(pending_invoice.pk))
        pending_invoice.refresh_from_db()
        assert pending_invoice.status == BillingInvoice.STATUS_PAID
        assert pending_invoice.payment_method == "stripe"
        assert pending_invoice.paid_datetime is not None
        assert pending_invoice.reminder_enabled is False

    @pytest.mark.django_db
    def test_idempotency_already_paid_not_double_updated(self, paid_invoice):
        """Already-PAID invoice must NOT be updated again (idempotency guard)."""
        original_paid_datetime = paid_invoice.paid_datetime
        with patch("eventyay.eventyay_common.tasks.logger.warning") as mock_warning:
            update_billing_invoice_information(invoice_id=str(paid_invoice.pk))

        paid_invoice.refresh_from_db()
        assert paid_invoice.status == BillingInvoice.STATUS_PAID
        assert paid_invoice.paid_datetime == original_paid_datetime
        mock_warning.assert_called_once()
        assert "already marked as paid" in mock_warning.call_args[0][0].lower()

    @pytest.mark.django_db
    def test_nonpending_nonpaid_invoice_logs_error(self, expired_invoice):
        """Unexpected non-pending statuses should log an error and return None."""
        with patch("eventyay.eventyay_common.tasks.logger.error") as mock_error:
            result = update_billing_invoice_information(invoice_id=str(expired_invoice.pk))

        expired_invoice.refresh_from_db()
        assert result is None
        assert expired_invoice.status == BillingInvoice.STATUS_EXPIRED
        mock_error.assert_called_once()
        assert "current status is" in mock_error.call_args[0][0].lower()

    @pytest.mark.django_db
    def test_nonexistent_invoice_logs_error_and_returns_none(self):
        """Non-existent invoice_id should log an error and return None."""
        with patch("eventyay.eventyay_common.tasks.logger.error") as mock_error:
            result = update_billing_invoice_information(invoice_id="999999")

        assert result is None
        mock_error.assert_called_once()
        assert "does not exist in the database" in mock_error.call_args[0][0].lower()

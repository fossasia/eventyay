from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django_scopes import scopes_disabled

from eventyay.base.models import BillingInvoice
from eventyay.eventyay_common.tasks import update_billing_invoice_information


def _payment_intent_event(*, invoice_id=None, event_id='evt_test'):
    metadata = {}
    if invoice_id is not None:
        metadata['invoice_id'] = invoice_id
    return SimpleNamespace(
        id=event_id,
        type='payment_intent.succeeded',
        data=SimpleNamespace(object={'metadata': metadata, 'id': 'pi_test'}),
    )


@pytest.fixture
@scopes_disabled()
def billing_invoice(organizer, event):
    return BillingInvoice.objects.create(
        organizer=organizer,
        event=event,
        status=BillingInvoice.STATUS_PENDING,
        amount=Decimal('10.00'),
        currency='EUR',
        ticket_fee=Decimal('10.00'),
        final_ticket_fee=Decimal('10.00'),
        created_by='test',
        updated_by='test',
        monthly_bill=timezone.now().date(),
    )


@pytest.mark.django_db
def test_billing_webhook_skips_task_when_invoice_id_missing():
    client = Client()
    event = _payment_intent_event(invoice_id=None)

    with (
        mock.patch(
            'eventyay.api.views.stripe.get_stripe_webhook_secret_key',
            return_value='whsec_test',
        ),
        mock.patch(
            'eventyay.api.views.stripe.stripe.Webhook.construct_event',
            return_value=event,
        ),
        mock.patch(
            'eventyay.api.views.stripe.update_billing_invoice_information.delay'
        ) as delay,
    ):
        response = client.post(
            reverse('api-v1:stripe-webhook'),
            data=b'{}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='t=1,v1=deadbeef',
        )

    assert response.status_code == 200
    delay.assert_not_called()


@pytest.mark.django_db
def test_billing_webhook_dispatches_task_when_invoice_id_present(billing_invoice):
    client = Client()
    event = _payment_intent_event(invoice_id=str(billing_invoice.id))

    with (
        mock.patch(
            'eventyay.api.views.stripe.get_stripe_webhook_secret_key',
            return_value='whsec_test',
        ),
        mock.patch(
            'eventyay.api.views.stripe.stripe.Webhook.construct_event',
            return_value=event,
        ),
        mock.patch(
            'eventyay.api.views.stripe.update_billing_invoice_information.delay'
        ) as delay,
    ):
        response = client.post(
            reverse('api-v1:stripe-webhook'),
            data=b'{}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='t=1,v1=deadbeef',
        )

    assert response.status_code == 200
    delay.assert_called_once_with(invoice_id=str(billing_invoice.id))


@pytest.mark.django_db
def test_update_billing_invoice_marks_pending_invoice_paid(billing_invoice):
    with scopes_disabled():
        update_billing_invoice_information(str(billing_invoice.id))
        billing_invoice.refresh_from_db()

    assert billing_invoice.status == BillingInvoice.STATUS_PAID
    assert billing_invoice.payment_method == 'stripe'
    assert billing_invoice.paid_datetime is not None
    assert billing_invoice.reminder_enabled is False


@pytest.mark.django_db
def test_update_billing_invoice_does_not_overwrite_already_paid(billing_invoice):
    original_paid_at = datetime(2024, 1, 15, 12, 0, tzinfo=dt_timezone.utc)
    with scopes_disabled():
        billing_invoice.status = BillingInvoice.STATUS_PAID
        billing_invoice.paid_datetime = original_paid_at
        billing_invoice.payment_method = 'stripe'
        billing_invoice.reminder_enabled = False
        billing_invoice.save(
            update_fields=['status', 'paid_datetime', 'payment_method', 'reminder_enabled']
        )

        update_billing_invoice_information(str(billing_invoice.id))
        billing_invoice.refresh_from_db()

    assert billing_invoice.status == BillingInvoice.STATUS_PAID
    assert billing_invoice.paid_datetime == original_paid_at


@pytest.mark.django_db
def test_update_billing_invoice_noop_when_invoice_id_missing():
    assert update_billing_invoice_information(None) is None
    assert update_billing_invoice_information('') is None

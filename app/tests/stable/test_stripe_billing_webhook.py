import copy
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django_scopes import scope, scopes_disabled

from eventyay.base.models import BillingInvoice, Order, OrderPayment, OrderRefund
from eventyay.eventyay_common.tasks import update_billing_invoice_information


class ObjectWithoutDictMethods:
    """Stand-in for a stripe-python 15 ``StripeObject``.

    Supports attribute access, ``in``, ``[]`` and ``to_dict()``, but not dict methods such as
    ``.get()``, so it fails like a stripe-python 15 object on any installed stripe version.
    """

    def __init__(self, data):
        self._data = data

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name) from None

    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    def to_dict(self):
        return copy.deepcopy(self._data)


def _post_webhook(client, event):
    with (
        mock.patch(
            'eventyay.api.views.stripe.get_stripe_webhook_secret_key',
            return_value='whsec_test',
        ),
        mock.patch(
            'eventyay.api.views.stripe.stripe.Webhook.construct_event',
            return_value=event,
        ),
    ):
        return client.post(
            reverse('api-v1:stripe-webhook'),
            data=b'{}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='t=1,v1=deadbeef',
        )


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
def billing_invoice(organizer, event):
    with scope(organizer=organizer):
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
        mock.patch('eventyay.api.views.stripe.update_billing_invoice_information.delay') as delay,
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
        mock.patch('eventyay.api.views.stripe.update_billing_invoice_information.delay') as delay,
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
    original_paid_at = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
    with scopes_disabled():
        billing_invoice.status = BillingInvoice.STATUS_PAID
        billing_invoice.paid_datetime = original_paid_at
        billing_invoice.payment_method = 'stripe'
        billing_invoice.reminder_enabled = False
        billing_invoice.save(update_fields=['status', 'paid_datetime', 'payment_method', 'reminder_enabled'])

        update_billing_invoice_information(str(billing_invoice.id))
        billing_invoice.refresh_from_db()

    assert billing_invoice.status == BillingInvoice.STATUS_PAID
    assert billing_invoice.paid_datetime == original_paid_at


@pytest.mark.django_db
def test_update_billing_invoice_noop_when_invoice_id_missing():
    assert update_billing_invoice_information(None) is None
    assert update_billing_invoice_information('') is None


@pytest.mark.django_db
def test_billing_webhook_reads_payment_intents_without_dict_methods(billing_invoice):
    event = SimpleNamespace(
        id='evt_test',
        type='payment_intent.succeeded',
        data=SimpleNamespace(
            object=ObjectWithoutDictMethods({'id': 'pi_test', 'metadata': {'invoice_id': str(billing_invoice.id)}})
        ),
    )

    with mock.patch('eventyay.api.views.stripe.update_billing_invoice_information.delay') as delay:
        response = _post_webhook(Client(), event)

    assert response.status_code == 200
    delay.assert_called_once_with(invoice_id=str(billing_invoice.id))


@pytest.fixture
def stripe_payment(event):
    with scope(organizer=event.organizer, event=event):
        order = Order.objects.create(
            code='FOO',
            event=event,
            email='dummy@dummy.test',
            status=Order.STATUS_PAID,
            datetime=timezone.now(),
            expires=timezone.now() + timedelta(days=10),
            total=Decimal('23.00'),
            locale='en',
        )
        return order.payments.create(
            provider='stripe',
            amount=Decimal('23.00'),
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            info=json.dumps({'id': 'ch_test'}),
        )


def _charge_refunded(payment):
    return {
        'id': 'ch_test',
        'object': 'charge',
        'refunded': False,
        'metadata': {'order': payment.order.code, 'payment': str(payment.local_id)},
        'refunds': {
            'object': 'list',
            'data': [{'id': 're_test', 'object': 'refund', 'amount': 500, 'currency': 'eur'}],
        },
    }


@pytest.mark.django_db
def test_charge_refunded_webhook_reads_charges_without_dict_methods(organizer, event, stripe_payment):
    stripe_event = SimpleNamespace(
        id='evt_test',
        type='charge.refunded',
        data=SimpleNamespace(object=ObjectWithoutDictMethods(_charge_refunded(stripe_payment))),
    )

    response = _post_webhook(Client(), stripe_event)

    assert response.status_code == 200
    with scope(organizer=organizer, event=event):
        refund = stripe_payment.order.refunds.get()
    assert refund.amount == Decimal('5.00')
    assert refund.state == OrderRefund.REFUND_STATE_DONE
    assert json.loads(refund.info)['full_data']['id'] == 're_test'


@pytest.mark.django_db
def test_charge_refunded_webhook_records_refund_from_a_signed_stripe_event(organizer, event, stripe_payment):
    secret = 'whsec_test'
    payload = json.dumps(
        {
            'id': 'evt_test',
            'object': 'event',
            'type': 'charge.refunded',
            'data': {'object': _charge_refunded(stripe_payment)},
        }
    )
    timestamp = int(time.time())
    signature = hmac.new(secret.encode(), f'{timestamp}.{payload}'.encode(), hashlib.sha256).hexdigest()

    with mock.patch('eventyay.api.views.stripe.get_stripe_webhook_secret_key', return_value=secret):
        response = Client().post(
            reverse('api-v1:stripe-webhook'),
            data=payload,
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE=f't={timestamp},v1={signature}',
        )

    assert response.status_code == 200
    with scope(organizer=organizer, event=event):
        refund = stripe_payment.order.refunds.get()
    assert refund.amount == Decimal('5.00')
    assert json.loads(refund.info)['full_data']['id'] == 're_test'


@pytest.mark.django_db
def test_charge_refunded_webhook_records_each_refund_once(organizer, event, stripe_payment):
    stripe_event = SimpleNamespace(
        id='evt_test',
        type='charge.refunded',
        data=SimpleNamespace(object=ObjectWithoutDictMethods(_charge_refunded(stripe_payment))),
    )

    first = _post_webhook(Client(), stripe_event)
    second = _post_webhook(Client(), stripe_event)

    assert first.status_code == second.status_code == 200
    with scope(organizer=organizer, event=event):
        assert stripe_payment.order.refunds.count() == 1

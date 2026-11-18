from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

import pytest
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone
from django_scopes import scopes_disabled

from eventyay.api.views.stripe import _stripe_object_to_dict, stripe_webhook_view
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
    original_paid_at = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
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


class MockStripe15Object:
    """Simulates a Stripe Python 15.x StripeObject which does not support dict methods (.get, .items, etc.)."""

    def __init__(self, data):
        self._data = data

    def to_dict(self):
        result = {}
        for k, v in self._data.items():
            if isinstance(v, MockStripe15Object):
                result[k] = v.to_dict()
            elif isinstance(v, list):
                result[k] = [item.to_dict() if isinstance(item, MockStripe15Object) else item for item in v]
            else:
                result[k] = v
        return result

    def __getattr__(self, name):
        if name in ('get', 'items', 'keys', 'values'):
            raise AttributeError(
                f"'{name}' is a dict method, but a StripeObject is not a dict. Use .to_dict() to convert it."
            )
        if name in self._data:
            return self._data[name]
        raise AttributeError(name)


def test_stripe_object_to_dict_conversion():
    # Case 1: Plain dictionary
    assert _stripe_object_to_dict({'a': 1, 'b': 2}) == {'a': 1, 'b': 2}

    # Case 2: MockStripe15Object raising AttributeError on .get()
    raw_dict = {'id': 'pi_123', 'metadata': {'invoice_id': '456'}}
    mock_obj = MockStripe15Object({
        'id': 'pi_123',
        'metadata': MockStripe15Object({'invoice_id': '456'}),
    })
    with pytest.raises(AttributeError, match="is a dict method, but a StripeObject is not a dict"):
        mock_obj.get('id')

    converted = _stripe_object_to_dict(mock_obj)
    assert converted == raw_dict
    assert converted.get('metadata', {}).get('invoice_id') == '456'

    # Case 3: None or non-dict
    assert _stripe_object_to_dict(None) == {}
    assert _stripe_object_to_dict('invalid') == {}


def test_billing_webhook_with_stripe_15_object_dispatches_task():
    rf = RequestFactory()
    mock_stripe_event = SimpleNamespace(
        id='evt_test_15',
        type='payment_intent.succeeded',
        data=SimpleNamespace(
            object=MockStripe15Object({
                'id': 'pi_123',
                'metadata': MockStripe15Object({'invoice_id': 'inv_789'}),
            })
        ),
    )

    request = rf.post(
        '/api/v1/webhook/stripe',
        data=b'{}',
        content_type='application/json',
        HTTP_STRIPE_SIGNATURE='t=1,v1=deadbeef',
    )

    with (
        mock.patch('eventyay.api.views.stripe.get_stripe_webhook_secret_key', return_value='whsec_test'),
        mock.patch('eventyay.api.views.stripe.stripe.Webhook.construct_event', return_value=mock_stripe_event),
        mock.patch('eventyay.api.views.stripe.update_billing_invoice_information.delay') as delay,
    ):
        response = stripe_webhook_view(request)

    assert response.status_code == 200
    delay.assert_called_once_with(invoice_id='inv_789')


def test_billing_webhook_with_stripe_15_object_skips_when_invoice_id_missing():
    rf = RequestFactory()
    mock_stripe_event = SimpleNamespace(
        id='evt_test_15_missing',
        type='payment_intent.succeeded',
        data=SimpleNamespace(
            object=MockStripe15Object({
                'id': 'pi_123',
                'metadata': MockStripe15Object({}),
            })
        ),
    )

    request = rf.post(
        '/api/v1/webhook/stripe',
        data=b'{}',
        content_type='application/json',
        HTTP_STRIPE_SIGNATURE='t=1,v1=deadbeef',
    )

    with (
        mock.patch('eventyay.api.views.stripe.get_stripe_webhook_secret_key', return_value='whsec_test'),
        mock.patch('eventyay.api.views.stripe.stripe.Webhook.construct_event', return_value=mock_stripe_event),
        mock.patch('eventyay.api.views.stripe.update_billing_invoice_information.delay') as delay,
    ):
        response = stripe_webhook_view(request)

    assert response.status_code == 200
    delay.assert_not_called()


def test_billing_webhook_charge_refunded_with_stripe_15_object():
    rf = RequestFactory()
    mock_refund_item = MockStripe15Object({
        'id': 're_123',
        'amount': 1500,
    })
    mock_charge = MockStripe15Object({
        'id': 'ch_123',
        'metadata': MockStripe15Object({'order': 'ORD1', 'payment': '1'}),
        'refunds': MockStripe15Object({'data': [mock_refund_item]}),
        'refunded': True,
    })
    mock_stripe_event = SimpleNamespace(
        id='evt_test_refund',
        type='charge.refunded',
        data=SimpleNamespace(object=mock_charge),
    )

    request = rf.post(
        '/api/v1/webhook/stripe',
        data=b'{}',
        content_type='application/json',
        HTTP_STRIPE_SIGNATURE='t=1,v1=deadbeef',
    )

    fake_order = mock.MagicMock(code='ORD1', status='p')
    fake_order.refunds.filter.return_value.exists.return_value = False
    fake_payment = mock.MagicMock(order=fake_order)

    with (
        mock.patch('eventyay.api.views.stripe.get_stripe_webhook_secret_key', return_value='whsec_test'),
        mock.patch('eventyay.api.views.stripe.stripe.Webhook.construct_event', return_value=mock_stripe_event),
        mock.patch(
            'eventyay.api.views.stripe.OrderPayment.objects.filter',
            return_value=mock.MagicMock(first=lambda: fake_payment),
        ),
        mock.patch('eventyay.api.views.stripe.mark_order_refunded') as mock_mark_refunded,
    ):
        response = stripe_webhook_view(request)

    assert response.status_code == 200
    fake_order.refunds.create.assert_called_once()
    create_kwargs = fake_order.refunds.create.call_args.kwargs
    assert create_kwargs['amount'] == Decimal('15.00')
    assert create_kwargs['provider'] == 'stripe'
    mock_mark_refunded.assert_called_once_with(fake_order, user=None)

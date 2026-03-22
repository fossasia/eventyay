import hashlib
import hmac
import json
import time
from datetime import timedelta
from decimal import Decimal
from unittest import mock

import pytest
import stripe
from django.test import RequestFactory
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay_stripe.models import ReferencedStripeObject
from eventyay_stripe.views import GlobalSettingsObject, webhook
from pretix.base.models import (
    Event, Order, OrderPayment, OrderRefund, Organizer, Team, User,
)


@pytest.fixture
def env():
    user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
    o = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=o, name='Dummy', slug='dummy', plugins='eventyay_stripe',
        date_from=now(), live=True
    )
    t = Team.objects.create(organizer=event.organizer, can_view_orders=True, can_change_orders=True)
    t.members.add(user)
    t.limit_events.add(event)
    o1 = Order.objects.create(
        code='FOOBAR', event=event, email='dummy@dummy.test',
        status=Order.STATUS_PAID,
        datetime=now(), expires=now() + timedelta(days=10),
        total=Decimal('13.37'),
    )
    return event, o1


def generate_signature(payload, secret, timestamp=None):
    """Generate a valid Stripe webhook signature for testing."""
    timestamp = timestamp or int(time.time())
    signed_payload = f"{timestamp}.{payload}"
    signature = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


def get_test_charge(order: Order):
    return {
        "id": "ch_18TY6GGGWE2Is8TZHanef25",
        "object": "charge",
        "amount": 1337,
        "amount_refunded": 1000,
        "application_fee": None,
        "balance_transaction": "txn_18TY6GGGWE2Ias8TkwY6o51W",
        "captured": True,
        "created": 1467642664,
        "currency": "eur",
        "customer": None,
        "description": None,
        "destination": None,
        "dispute": None,
        "failure_code": None,
        "failure_message": None,
        "fraud_details": {},
        "invoice": None,
        "livemode": False,
        "metadata": {
            "code": order.code,
            "order": str(order.pk),
            "event": str(order.event.pk),
        },
        "order": None,
        "paid": True,
        "receipt_email": None,
        "receipt_number": None,
        "refunded": False,
        "refunds": {
            "object": "list",
            "data": [],
            "total_count": 0
        },
        "shipping": None,
        "source": {
            "id": "card_18TY5wGGWE2Ias8Td38PjyPy",
            "object": "card",
            "address_city": None,
            "address_country": None,
            "address_line1": None,
            "address_line1_check": None,
            "address_line2": None,
            "address_state": None,
            "address_zip": None,
            "address_zip_check": None,
            "brand": "Visa",
            "country": "US",
            "customer": None,
            "cvc_check": "pass",
            "dynamic_last4": None,
            "exp_month": 12,
            "exp_year": 2016,
            "fingerprint": "FNbGTMaFvhRU2Y0E",
            "funding": "credit",
            "last4": "4242",
            "metadata": {},
            "name": "Carl Cardholder",
            "tokenization_method": None,
        },
        "source_transfer": None,
        "statement_descriptor": None,
        "status": "succeeded"
    }


@pytest.mark.django_db
def test_webhook_all_good(env, client, monkeypatch):
    charge = get_test_charge(env[1])
    monkeypatch.setattr("stripe.Charge.retrieve", lambda *args, **kwargs: charge)

    client.post('/dummy/dummy/stripe/webhook/', json.dumps(
        {
            "id": "evt_18otImGGWE2Ias8TUyVRDB1G",
            "object": "event",
            "api_version": "2016-03-07",
            "created": 1472729052,
            "data": {
                "object": {
                    "id": "ch_18TY6GGGWE2Ias8TZHanef25",
                    "object": "charge",
                    # Rest of object is ignored anway
                }
            },
            "livemode": True,
            "pending_webhooks": 1,
            "request": "req_977XOWC8zk51Z9",
            "type": "charge.refunded"
        }
    ), content_type='application_json')

    order = env[1]
    order.refresh_from_db()
    assert order.status == Order.STATUS_PAID


@pytest.mark.django_db
def test_webhook_mark_paid(env, client, monkeypatch):
    order = env[1]
    order.status = Order.STATUS_PENDING
    order.save()
    charge = get_test_charge(env[1])
    charge["amount_refunded"] = 0
    with scopes_disabled():
        payment = env[1].payments.create(
            provider='stripe', amount=env[1].total, info='{}', state=OrderPayment.PAYMENT_STATE_CREATED,
        )
        ReferencedStripeObject.objects.create(
            order=order,
            payment=payment,
            reference="pi_1",
        )

    monkeypatch.setattr("stripe.Charge.retrieve", lambda *args, **kwargs: charge)

    client.post('/dummy/dummy/stripe/webhook/', json.dumps(
        {
            "id": "evt_18otImGGWE2Ias8TUyVRDB1G",
            "object": "event",
            "api_version": "2016-03-07",
            "created": 1472729052,
            "data": {
                "object": {
                    "object": "charge",
                    "id": "pi_1",
                    "amount": 2000,
                    "currency": "usd",
                    "status": "succeeded",
                    "livemode": True,
                    "pending_webhooks": 1,
                    "request": "req_977XOWC8zk51Z9",
                    "type": "charge.succeeded"
                }
            },
            "livemode": True,
            "pending_webhooks": 1,
            "request": "req_977XOWC8zk51Z9",
            "type": "payment_intent.succeeded"
        }
    ), content_type='application_json')

    order.refresh_from_db()
    assert order.status == Order.STATUS_PENDING


@pytest.mark.django_db
def test_webhook_partial_refund(env, client, monkeypatch):
    charge = get_test_charge(env[1])

    with scopes_disabled():
        payment = env[1].payments.create(
            provider='stripe', amount=env[1].total, info=json.dumps(charge)
        )
    ReferencedStripeObject.objects.create(order=env[1], reference="ch_18TY6GGGWE2Ias8TZHanef25",
                                          payment=payment)

    charge['refunds'] = {
        "object": "list",
        "data": [
            {
                "id": "re_18otImGGWE2Ias8TY0QvwKYQ",
                "object": "refund",
                "amount": "12300",
                "balance_transaction": "txn_18otImGGWE2Ias8T4fLOxesC",
                "charge": "ch_18TY6GGGWE2Ias8TZHanef25",
                "created": 1472729052,
                "currency": "eur",
                "metadata": {},
                "reason": None,
                "receipt_number": None,
                "status": "succeeded"
            }
        ],
        "total_count": 1
    }
    monkeypatch.setattr("stripe.Charge.retrieve", lambda *args, **kwargs: charge)

    payload = json.dumps(
        {
            "id": "evt_18otImGGWE2Ias8TUyVRDB1G",
            "object": "event",
            "api_version": "2016-03-07",
            "created": 1472729052,
            "data": {
                "object": {
                    "id": "ch_18TY6GGGWE2Ias8TZHanef25",
                    "object": "charge",
                    # Rest of object is ignored anway
                }
            },
            "livemode": True,
            "pending_webhooks": 1,
            "request": "req_977XOWC8zk51Z9",
            "type": "charge.refunded"
        }
    )

    gs = GlobalSettingsObject()
    gs.settings.set('payment_stripe_webhook_secret', 'whsec_123')
    gs.settings.set('payment_stripe_connect_test_secret_key', 'sk_test_123')

    sig_header = generate_signature(payload, "whsec_123")
    client.post(
        '/dummy/dummy/stripe/webhook/',
        payload,
        content_type='application_json',
        HTTP_STRIPE_SIGNATURE=sig_header
    )

    order = env[1]
    order.refresh_from_db()
    assert order.status == Order.STATUS_PAID

    with scopes_disabled():
        ra = order.refunds.first()
    assert ra.state == OrderRefund.REFUND_STATE_EXTERNAL
    assert ra.source == 'external'
    assert ra.amount == Decimal('123.00')


@pytest.mark.django_db
def test_webhook_global(env, client, monkeypatch):
    order = env[1]
    order.status = Order.STATUS_PENDING
    order.save()

    charge = get_test_charge(env[1])
    charge["amount_refunded"] = 0
    monkeypatch.setattr("stripe.Charge.retrieve", lambda *args, **kwargs: charge)

    with scopes_disabled():
        payment = order.payments.create(
            provider='stripe', amount=order.total, info=json.dumps(charge), state=OrderPayment.PAYMENT_STATE_CREATED
        )
    ReferencedStripeObject.objects.create(order=order, reference="ch_18TY6GGGWE2Ias8TZHanef25",
                                          payment=payment)
    ReferencedStripeObject.objects.create(order=order, reference="pi_123456",
                                          payment=payment)

    payload = json.dumps(
        {
            "id": "evt_18otImGGWE2Ias8TUyVRDB1G",
            "object": "event",
            "api_version": "2016-03-07",
            "created": 1472729052,
            "data": {
                "object": {
                    "id": "ch_18TY6GGGWE2Ias8TZHanef25",
                    "object": "charge",
                    "payment_intent": "pi_123456",
                    "metadata": {
                        "event": order.event_id,
                    }
                }
            },
            "livemode": True,
            "pending_webhooks": 1,
            "request": "req_977XOWC8zk51Z9",
            "type": "payment_intent.succeeded"
        }
    )
    gs = GlobalSettingsObject()
    gs.settings.set('payment_stripe_webhook_secret', 'whsec_123')
    gs.settings.set('payment_stripe_connect_test_secret_key', 'sk_test_123')

    sig_header = generate_signature(payload, "whsec_123")
    response = client.post(
        '/_stripe/webhook/',
        payload,
        content_type='application_json',
        HTTP_STRIPE_SIGNATURE=sig_header
    )
    assert response.status_code == 200

    order.refresh_from_db()
    assert order.status == Order.STATUS_PAID


@pytest.mark.django_db
def test_webhook_global_legacy_reference(env, client, monkeypatch):
    order = env[1]
    order.status = Order.STATUS_PENDING
    order.save()

    charge = get_test_charge(env[1])
    charge["amount_refunded"] = 0
    monkeypatch.setattr("stripe.Charge.retrieve", lambda *args, **kwargs: charge)

    with scopes_disabled():
        payment = order.payments.create(
            provider='stripe', amount=order.total, info=json.dumps(charge), state=OrderPayment.PAYMENT_STATE_CREATED
        )
    ReferencedStripeObject.objects.create(order=order, reference="ch_18TY6GGGWE2Ias8TZHanef25")
    ReferencedStripeObject.objects.create(order=order, reference="pi_123456")

    payload = json.dumps(
        {
            "id": "evt_18otImGGWE2Ias8TUyVRDB1G",
            "object": "event",
            "api_version": "2016-03-07",
            "created": 1472729052,
            "data": {
                "object": {
                    "id": "ch_18TY6GGGWE2Ias8TZHanef25",
                    "object": "charge",
                    "payment_intent": "pi_123456",
                    "metadata": {
                        "event": order.event_id,
                    }
                }
            },
            "livemode": True,
            "pending_webhooks": 1,
            "request": "req_977XOWC8zk51Z9",
            "type": "payment_intent.succeeded"
        }
    )
    gs = GlobalSettingsObject()
    gs.settings.set('payment_stripe_webhook_secret', 'whsec_123')
    gs.settings.set('payment_stripe_connect_test_secret_key', 'sk_test_123')
    sig_header = generate_signature(payload, "whsec_123")

    response = client.post('/_stripe/webhook/', payload, content_type='application_json', HTTP_STRIPE_SIGNATURE=sig_header)
    assert response.status_code == 200

    order.refresh_from_db()
    assert order.status == Order.STATUS_PAID
    with scopes_disabled():
        assert list(order.payments.all()) == [payment]


@pytest.fixture
def factory():
    return RequestFactory()


@pytest.fixture
def mock_global_settings():
    with mock.patch('eventyay_stripe.views.GlobalSettingsObject') as MockGlobalSettings:
        instance = MockGlobalSettings.return_value
        instance.settings.payment_stripe_connect_secret_key = 'sk_test_123'
        instance.settings.payment_stripe_connect_test_secret_key = 'sk_test_123'
        instance.settings.payment_stripe_webhook_secret = 'whsec_123'
        yield instance


@pytest.fixture
def valid_payload():
    return json.dumps({
        "id": "evt_1",
        "object": "event",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "object": "charge",
                "id": "pi_1",
                "amount": 2000,
                "currency": "usd",
                "status": "succeeded",
                "livemode": True,
                "pending_webhooks": 1,
                "request": "req_977XOWC8zk51Z9",
                "type": "charge.succeeded"
            }
        }
    })


@pytest.mark.django_db
def test_webhook_invalid_payload(factory, mock_global_settings):
    invalid_payload = "invalid_payload"
    request = factory.post('/dummy/dummy/stripe/webhook', data=invalid_payload, content_type='application/json')
    with mock.patch('stripe.Webhook.construct_event', side_effect=ValueError("Invalid JSON")):
        response = webhook(request)
        assert response.status_code == 400
        assert response.content == b"Invalid payload"


@pytest.mark.django_db
def test_webhook_invalid_signature(factory, valid_payload, mock_global_settings):
    request = factory.post('/_stripe/webhook', data=valid_payload, content_type='application/json')
    request.META['HTTP_STRIPE_SIGNATURE'] = 'invalid_signature'

    with mock.patch('stripe.Webhook.construct_event', side_effect=stripe.error.SignatureVerificationError("Invalid signature", 'sig_123')):
        response = webhook(request)
        assert response.status_code == 400
        assert response.content == b"Invalid Stripe signature"


@pytest.mark.django_db
def test_webhook_success(factory, valid_payload, mock_global_settings):
    request = factory.post('/_stripe/webhook', data=valid_payload, content_type='application/json')
    request.META['HTTP_STRIPE_SIGNATURE'] = 'valid_signature'

    with mock.patch('stripe.Webhook.construct_event', return_value={"type": "payment_intent.succeeded"}):
        response = webhook(request)
        assert response.status_code == 200


@pytest.mark.django_db
def test_webhook_refund(factory, valid_payload, mock_global_settings):
    request = factory.post('/_stripe/webhook', data=valid_payload, content_type='application/json')
    request.META['HTTP_STRIPE_SIGNATURE'] = 'valid_signature'

    with mock.patch('stripe.Webhook.construct_event', return_value={"type": "payment_intent.succeeded"}):
        response = webhook(request)
        assert response.status_code == 200

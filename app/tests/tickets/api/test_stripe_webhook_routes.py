from unittest import mock

import pytest
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
@pytest.mark.parametrize(
    'path',
    [
        '/_stripe/webhook',
        '/_stripe/webhook/',
        '/tickets/_stripe/webhook',
        '/tickets/_stripe/webhook/',
    ],
)
def test_stripe_payment_webhook_compat_paths_do_not_404(path):
    """Stripe Dashboard used /tickets/_stripe/webhook and paths without a trailing slash.

    Those must reach the payment plugin webhook without APPEND_SLASH 301 redirects
    (Stripe does not follow POST redirects for webhooks).
    """
    client = Client()
    with (
        mock.patch('eventyay_stripe.views.get_stripe_secret_key', return_value='sk_test'),
        mock.patch('eventyay_stripe.views.get_stripe_webhook_secret_key', return_value='whsec_test'),
    ):
        response = client.post(
            path,
            data=b'{}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='t=1,v1=deadbeef',
        )
    assert response.status_code != 404, response.content
    assert response.status_code not in (301, 302), response.get('Location')
    # Invalid signature / payload is expected for a forged request with a real secret configured.
    assert response.status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize(
    'path',
    [
        '/api/v1/webhook/stripe',
        '/api/v1/webhook/stripe/',
        '/tickets/api/v1/webhook/stripe',
        '/tickets/api/v1/webhook/stripe/',
    ],
)
def test_stripe_billing_webhook_paths_reachable(path):
    client = Client()
    with mock.patch(
        'eventyay.api.views.stripe.get_stripe_webhook_secret_key',
        side_effect=ValidationError('Stripe webhook secret key not found.'),
    ):
        response = client.post(
            path,
            data=b'{}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='t=1,v1=deadbeef',
        )
    assert response.status_code == 503
    assert b'not configured' in response.content.lower()


@pytest.mark.django_db
def test_stripe_billing_webhook_missing_signature_returns_400():
    client = Client()
    response = client.post(
        reverse('api-v1:stripe-webhook'),
        data=b'{}',
        content_type='application/json',
    )
    assert response.status_code == 400
    assert b'Missing signature' in response.content


@pytest.mark.django_db
def test_stripe_billing_webhook_invalid_signature_returns_400():
    client = Client()
    with mock.patch(
        'eventyay.api.views.stripe.get_stripe_webhook_secret_key',
        return_value='whsec_test',
    ):
        response = client.post(
            '/api/v1/webhook/stripe',
            data=b'{"id":"evt_1"}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='t=1,v1=notavalidsignature',
        )
    assert response.status_code == 400
    assert b'Invalid signature' in response.content

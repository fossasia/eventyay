.. _stripe:

Stripe
======

.. note:: If you use the Hosted version of eventyay at eventyay.com, you do not need to copy API keys and create webhooks
          any more. Instead, you can just click "Connect with Stripe" in eventyay and everything will connect
          automatically.

To integrate Stripe with eventyay, you first need to have an active Stripe merchant account. If you do not already have a
Stripe account, you can create one on `stripe.com`_. Then, click on "API" in the left navigation of the Stripe
Dashboard. As you can see in the following screenshot, you will be presented with two sets of API keys, one for test
and one for live payments. In each set, there is a secret and a publishable keys.

.. image:: img/stripe1.png
   :class: screenshot

Choose one of the two sets and copy the two keys to the appropriate fields in eventyay' settings. To perform actual
payments, you will need to use the live keys, but you can use the test keys to test the payment flow before you go live.
In test mode, you cannot use your real credit card, but only `test cards`_ like ``4242424242424242`` that you can
find in Stripe's documentation.

If you want Stripe to notify eventyay automatically once a payment gets cancelled, so eventyay can cancel the ticket as
well, you need to create a so-called webhook. To do so, click "Webhooks" on top of the page in the Stripe dashboard
that you are currently on. Then, click "Add endpoint" and enter the URL that you find directly below the key
configuration in eventyay' settings.

.. image:: img/stripe2.png
   :class: screenshot

Again, you can choose between live mode and test mode here.

.. _stripe.com: https://dashboard.stripe.com/register
.. _test cards: https://stripe.com/docs/testing#cards

Stripe Webhook Configuration (Detailed)

To ensure proper communication between Stripe and Eventyay, webhooks need to be configured correctly.

1. Go to the Stripe Dashboard
2. Navigate to Developers → Webhooks
3. Click on "Add endpoint"

In the "URL to be called" field, enter the webhook URL provided in Eventyay (usually found in the payment settings section).

Select the following events:
- payment_intent.succeeded
- payment_intent.payment_failed
- charge.refunded
- checkout.session.completed

After creating the webhook, click on it and copy the "Signing secret". This secret should be added to Eventyay in the Stripe settings to verify incoming webhook requests.

---

Stripe OAuth Configuration

Stripe OAuth allows users to connect their Stripe accounts directly with Eventyay.

1. Go to Stripe Dashboard
2. Navigate to Settings → Connect Settings
3. Enable Stripe Connect if not already enabled

You will need the following credentials:
- Client ID
- Publishable Key
- Secret Key

These credentials can be entered in the Eventyay payment settings.

---

Redirect URIs

Make sure the following redirect URI is configured in your Stripe application:

/_stripe/oauth_return/

For local development, you may need to use:
http://localhost:8000/_stripe/oauth_return/

For production:
https://your-domain.com/_stripe/oauth_return/

---

Notes

- Ensure you are using the correct mode (test or live) while configuring keys and webhooks.
- Test mode should be used during development.
- Live mode should only be used in production environments.

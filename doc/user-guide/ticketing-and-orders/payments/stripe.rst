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

.. image:: ../../../img/stripe1.png
   :class: screenshot

Choose one of the two sets and copy the two keys to the appropriate fields in eventyay' settings. To perform actual
payments, you will need to use the live keys, but you can use the test keys to test the payment flow before you go live.
In test mode, you cannot use your real credit card, but only `test cards`_ like ``4242424242424242`` that you can
find in Stripe's documentation.

Webhooks Configuration (Admin Level)
------------------------------------

.. note:: There is a distinction between Event-level and Admin-level settings:
          - **Event Level:** Organizers only need their Stripe *Publishable* and *Secret* keys to process payments.
          - **Admin Level:** Server administrators must configure a *Webhook Secret* (and OAuth Client ID) to receive global notifications from Stripe.

.. image:: ../../../img/stripe2.png
   :class: screenshot

If you want Stripe to notify Eventyay automatically once a payment gets cancelled, refunded, or succeeds (especially for asynchronous payment methods like SEPA), the server administrator needs to create a webhook. 

1. In your Stripe dashboard, navigate to **Developers > Webhooks**.
2. Click **Add endpoint**.
3. Set the **Endpoint URL** to ``https://<yourdomain>/_stripe/webhook/``.
4. Select the following **events to send**:

   * ``charge.succeeded``, ``charge.refunded``, ``charge.failed``, ``charge.updated``
   * ``charge.dispute.created``, ``charge.dispute.updated``, ``charge.dispute.closed``
   * ``payment_intent.succeeded``, ``payment_intent.created``, ``payment_intent.payment_failed``, ``payment_intent.canceled``
   * ``source.chargeable``, ``source.canceled``, ``source.failed``

5. After creating the endpoint, reveal the **Signing secret** (which starts with ``whsec_``).
6. Provide this secret to your Eventyay instance via your environment configuration (e.g., using the variable ``EVY_PAYMENT_STRIPE_WEBHOOK_SECRET_KEY`` or the corresponding secrets file).

*Local Testing:* If you are testing locally, you can use the `Stripe CLI <https://stripe.com/docs/stripe-cli>`_:
``stripe listen --forward-to localhost:8000/_stripe/webhook/``

Stripe OAuth Setup (Connect)
----------------------------

To allow event organizers to seamlessly connect their existing Stripe accounts to Eventyay without manually copying API keys, you can configure Stripe OAuth (Stripe Connect).

1. In your Stripe dashboard, navigate to **Settings > Connect > Settings > Integration**.
2. Note your **Client ID** (it starts with ``ca_``) and configure it in your Eventyay settings.
3. You must add the following **Redirect URIs** in the Stripe Dashboard to allow Eventyay to handle the OAuth return:

   * **Production:** ``https://<yourdomain>/_stripe/oauth_return/``
   * **Local Development:** ``http://localhost:8000/_stripe/oauth_return/``

When configured, organizers will see a "Connect with Stripe" button in their payment settings, allowing a one-click connection to Eventyay.

Troubleshooting and Known Errors
--------------------------------

**1. "As per Indian regulations, only registered Indian businesses... can accept international payments"**

This error occurs if you are using an Indian Stripe sandbox/test account and attempt to process a payment in a foreign currency (like USD). To test successfully without full export compliance, ensure your Eventyay event's currency is set to **INR** (Indian Rupees).

**2. Payment gets stuck in "Pending" or "requires_action"**

When testing domestic transactions in India (INR), the Reserve Bank of India mandates 3D Secure authentication. When you click "Pay" using a test card, Stripe redirects to a mock 3D Secure page. If you close this page without clicking "Complete Authentication," the order will remain in the ``requires_action`` state. Ensure you complete the mock authentication flow during checkout.

.. _stripe.com: https://dashboard.stripe.com/register
.. _test cards: https://stripe.com/docs/testing#cards

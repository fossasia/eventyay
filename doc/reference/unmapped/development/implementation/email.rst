Sending Email
=============

Eventyay allows event organizers to configure how they want to send emails to their users in multiple ways.
Therefore, all emails should be sent through the following function.

If the email you send is related to an order, you should also take a look at the
:py:meth:`~eventyay.base.models.Order.send_mail` of the order model.

.. autofunction:: eventyay.base.services.mail.mail
   :no-index:

Gmail / Google Workspace API
----------------------------

Eventyay can send platform and event email through the Gmail API in addition to SMTP and SendGrid.

Configuration
~~~~~~~~~~~~~~~

1. Create a Google Cloud project and enable the Gmail API.
2. Configure an OAuth client (Web application) with the redirect URI shown in the admin **Global settings → Email** tab.
3. In Eventyay, open **Global settings → Email**, choose **Gmail / Google Workspace API**, and save the OAuth client ID and secret.
4. Click **Connect Gmail account** and authorize Gmail send and user email access (``gmail.send`` and ``userinfo.email`` scopes).
5. Optionally configure SMTP or SendGrid as a fallback provider.

Event-level custom gateways can also use Gmail when **Use custom email gateway** is enabled in the unified event email settings.

Security
~~~~~~~~

OAuth refresh tokens are encrypted at rest using a key derived from ``SECRET_KEY``.
Tokens are never shown in the admin UI after connection.

Limits and delivery behavior
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Gmail and Google Workspace accounts have daily sending limits and API rate limits.
Eventyay tracks approximate daily usage per connected account, applies per-minute rate limiting, and queues email through Celery workers.

Temporary Gmail API errors are retried with exponential backoff.
Daily-limit and permanent rejection errors are not retried endlessly.
When a fallback provider is configured, Eventyay can send through SMTP or SendGrid if Gmail delivery is unavailable.

Incoming reply handling via Gmail API is planned as a follow-up feature (see issue #4608).

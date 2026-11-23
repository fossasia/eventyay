.. _`rest-tokenauth`:

Token-based authentication
==========================

Obtaining an API token
----------------------

To authenticate your API requests with Tokens, you need to obtain a team-level API token.
You can create a token in the eventyay web interface on the level of organizer teams. Create
a new team or choose an existing team that has the level of permissions the token should
have and create a new token using the form below the list of team members:

.. image:: ../img/token_form.png
   :class: screenshot

You can enter a description for the token to distinguish from other tokens later on.
Once you click "Add", you will be provided with an API token in the success message.
Copy this token, as you won't be able to retrieve it again.

.. image:: ../img/token_success.png
   :class: screenshot

Read-only tokens for integrations
---------------------------------

Website plugins, newsletters and dashboards usually only need to display event information. For them,
create a team with only the permission "Read-only access to event information", limit it to the events
the integration should show, and create the token in that team. If the token leaks, it cannot be used
to change your event.

A token of such a team can read:

* the event itself and its public settings (texts, colors, images, languages)
* ticket types and prices: products, categories, quotas, questions, tax rules and dates
* tracks, rooms, session types and the published schedule
* confirmed sessions in the published schedule and the public profiles of their speakers
* sponsors and exhibitors, if the exhibition plugin is enabled

It cannot change anything; every write request is answered with ``403 Forbidden``. It also has no access
to private data: orders, attendee details, invoices, vouchers, gift cards, check-ins, proposals that are not
public yet, reviews, answers to non-public questions, email templates or access codes.

API access still depends on your plan. If your plan does not include API read access, requests with this
token are refused as well.

Using an API token
------------------

You need to include the API token with every request to eventyay' API in the ``Authorization`` header
like the following:

.. sourcecode:: http
   :emphasize-lines: 3

   GET /api/v1/organizers/ HTTP/1.1
   Host: eventyay.com
   Authorization: Token e1l6gq2ye72thbwkacj7jbri7a7tvxe614ojv8ybureain92ocub46t5gab5966k


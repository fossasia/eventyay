.. _user-anonymizing-ticketing-data:

Anonymizing ticketing data
==========================

Once an event is over you usually no longer need to know *who* bought a ticket, only *that* tickets were sold.
Anonymizing ticketing data removes the identity of buyers and attendees from an event while keeping everything you
need for your statistics and bookkeeping.

Nothing is deleted. Orders, ticket counts, totals, payments, check-ins and the answers to your questions stay in
place. They are simply no longer connected to a person.

What is anonymized and what stays
---------------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Data
     - What happens
     - What stays
   * - Order contact
     - Email becomes a unique placeholder ending in ``@eventyay.invalid``, phone number is removed.
     - Order code, status, totals, dates, sales channel.
   * - Attendees
     - Name, email, company, address and job title are removed.
     - Product, price, taxes, seat, check-ins.
   * - Invoice address
     - Name, company, address, VAT ID and internal reference are removed.
     - Nothing; the address is cleared.
   * - Invoices
     - Buyer details are replaced and the PDF is regenerated without them. The old PDF file is deleted.
     - Invoice number, date, line items, amounts and taxes.
   * - Payments
     - Identifying data stored for the payment provider, such as account holder names, is removed. Bank transfer
       transactions lose the payer's details.
     - Amounts, payment state and the provider reference IDs needed to reconcile with your provider.
   * - Questions and answers
     - Nothing. Free-text answers are kept as they are.
     - Everything.
   * - Order links
     - The order secret and the ticket page secret are replaced, so old confirmation emails no longer open the order.
     - Nothing to keep.
   * - Waiting list, carts, email queue
     - Names, emails and phone numbers are removed or replaced.
     - The entries themselves.
   * - Video platform accounts
     - Profile and name are cleared for attendees of the event. Team members and organizers are not touched.
     - Everything else on the platform is not changed.
   * - Logs
     - Contact details in the order and waiting list history are masked.
     - The history itself.

Anonymizing does not change who is linked to an order by email address. Because an anonymized order has a placeholder
email, it no longer appears under a user's account.

.. warning::

   **Anonymizing is irreversible.** Tax law in your country may require you to keep complete invoices for several
   years. Download them before you anonymize. You are responsible for meeting these requirements.

Download your invoices first
----------------------------

Open the event's invoice downloads page (``…/orders/invoice-downloads/``) to download:

* **Invoice PDFs** – a ZIP archive with one PDF per invoice.
* **Invoice spreadsheet** – an Excel workbook with invoice details and line items.

The anonymize page links to this page and asks you to confirm that you downloaded what you need.

Anonymizing a single order
--------------------------

On an order's page, a team member with the *Can change orders* permission can choose **Anonymize**. This is useful
for a single deletion request. It anonymizes only that order and works at any time after the event has ended.
An anonymized order can no longer be edited.

Anonymizing a whole event
-------------------------

In **Settings → Danger zone → Data management**, **Anonymize ticketing data** anonymizes every order of the event.

* Only members of your organizer's **Core Organizing Team** see this action. See :ref:`user-teams`.
* It is available only after the event has ended **plus** a waiting period. The platform administrators set the
  waiting period; the default is 14 days. For events with several dates, the last date counts.
* You must have logged in recently. If not, you are asked for your password again.
* The page shows how many orders, attendees and invoices are affected and repeats the tax warning.
* You confirm that you downloaded your invoices and type the event name.

Anonymization runs in the background and the page shows its progress. If it is interrupted, for example because a
server restarts, open the page again and choose **Resume anonymization**. Orders that were already anonymized are
skipped.

.. highlight:: python
   :linenothreshold: 5

Data model
==========

Eventyay provides the following data(base) models. Every model and every model method or field that is not
documented here is considered private and should not be used by third-party plugins, as it may change
without advance notice.

User model
----------

.. autoclass:: eventyay.base.models.User
   :members:

Organizers and events
---------------------

.. autoclass:: eventyay.base.models.Organizer
   :members:

.. autoclass:: eventyay.base.models.Event
   :members: get_date_from_display, get_time_from_display, get_date_to_display, get_date_range_display, presale_has_ended, presale_is_running, cache, lock, get_plugins, get_mail_backend, payment_term_last, get_payment_providers, get_invoice_renderers, invoice_renderer, settings

.. autoclass:: eventyay.base.models.SubEvent
   :members: get_date_from_display, get_time_from_display, get_date_to_display, get_date_range_display, presale_has_ended, presale_is_running

.. autoclass:: eventyay.base.models.Team
   :members:

.. autoclass:: eventyay.base.models.TeamAPIToken
   :members:

.. autoclass:: eventyay.base.models.RequiredAction
   :members:

.. autoclass:: eventyay.base.models.EventMetaProperty
   :members:

.. autoclass:: eventyay.base.models.EventMetaValue
   :members:

.. autoclass:: eventyay.base.models.SubEventMetaValue
   :members:


Products
--------

.. autoclass:: eventyay.base.models.Product
   :members:

.. autoclass:: eventyay.base.models.ProductCategory
   :members:

.. autoclass:: eventyay.base.models.ProductVariation
   :members:

.. autoclass:: eventyay.base.models.ProductAddOn
   :members:

.. autoclass:: eventyay.base.models.Question
   :members:

.. autoclass:: eventyay.base.models.Quota
   :members:

Carts and Orders
----------------

.. autoclass:: eventyay.base.models.Order
   :members:

.. autoclass:: eventyay.base.models.AbstractPosition
   :members:

.. autoclass:: eventyay.base.models.OrderPosition
   :members:

.. autoclass:: eventyay.base.models.OrderFee
   :members:

.. autoclass:: eventyay.base.models.OrderPayment
   :members:

.. autoclass:: eventyay.base.models.OrderRefund
   :members:

.. autoclass:: eventyay.base.models.CartPosition
   :members:

.. autoclass:: eventyay.base.models.QuestionAnswer
   :members:

.. autoclass:: eventyay.base.models.Checkin
   :members:

Logging
-------

.. autoclass:: eventyay.base.models.LogEntry
   :members:

Invoicing
---------

.. autoclass:: eventyay.base.models.Invoice
   :members:

.. autoclass:: eventyay.base.models.InvoiceLine
   :members:

Vouchers
--------

.. autoclass:: eventyay.base.models.Voucher
   :members:

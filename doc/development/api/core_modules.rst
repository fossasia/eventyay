.. highlight:: python
   :linenothreshold: 5

Core Modules Reference
======================

This section documents the core modules of the unified eventyay system.

Configuration & Settings
------------------------

Settings Management
~~~~~~~~~~~~~~~~~~~

.. automodule:: eventyay.config.settings
   :members:

Channels & Sales
----------------

Sales Channels
~~~~~~~~~~~~~~

.. autoclass:: eventyay.base.channels.SalesChannel
   :members:

.. autofunction:: eventyay.base.channels.get_all_sales_channels

The default sales channel is:

.. autoclass:: eventyay.base.channels.WebshopSalesChannel
   :members:

Authentication & Authorization
------------------------------

Auth Backends
~~~~~~~~~~~~~

.. automodule:: eventyay.base.auth
   :members:
   :no-index:

User Management
~~~~~~~~~~~~~~~

.. autoclass:: eventyay.base.models.User
   :members:
   :no-index:

Permissions
~~~~~~~~~~~

.. automodule:: eventyay.core.permissions
   :members:

.. automodule:: eventyay.control.permissions
   :members:

Payment Processing
------------------

Base Payment Provider
~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: eventyay.base.payment.BasePaymentProvider
   :members:
   :no-index:

Payment Exceptions
~~~~~~~~~~~~~~~~~~

.. autoexception:: eventyay.base.payment.PaymentException

Invoice Generation
~~~~~~~~~~~~~~~~~~

See ``eventyay.base.services.invoices`` for invoice generation functions.

Ticket Output
-------------

Ticket Output Providers
~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: eventyay.base.ticketoutput.BaseTicketOutput
   :members:
   :no-index:

Data Export
-----------

Exporters
~~~~~~~~~

.. autoclass:: eventyay.base.exporter.BaseExporter
   :members:
   :no-index:

.. autoclass:: eventyay.base.exporter.ListExporter
   :members:
   :no-index:

.. autoclass:: eventyay.base.exporter.MultiSheetListExporter
   :members:
   :no-index:

Data Shredding
~~~~~~~~~~~~~~

.. autoclass:: eventyay.base.shredder.BaseDataShredder
   :members:
   :no-index:

.. autoexception:: eventyay.base.shredder.ShredError
   :no-index:

.. autofunction:: eventyay.base.shredder.shred_constraints
   :no-index:

Email & Notifications
---------------------

Email Context
~~~~~~~~~~~~~

.. autofunction:: eventyay.base.email.get_email_context

.. autofunction:: eventyay.base.email.get_available_placeholders

Mail Services
~~~~~~~~~~~~~

.. autoexception:: eventyay.base.services.mail.SendMailException
   :no-index:

Notification Services
~~~~~~~~~~~~~~~~~~~~~

.. automodule:: eventyay.base.notifications
   :members:
   :no-index:

Middleware
----------

.. automodule:: eventyay.base.middleware
   :members:

.. automodule:: eventyay.control.middleware
   :members:

Multi-domain middleware is located in ``eventyay.multidomain.middleware``.

Internationalization
--------------------

.. automodule:: eventyay.base.i18n
   :members:

.. automodule:: eventyay.helpers.i18n
   :members:

Utilities
---------

Money & Decimal
~~~~~~~~~~~~~~~

.. automodule:: eventyay.base.decimal
   :members:

.. automodule:: eventyay.helpers.money
   :members:

Date & Time
~~~~~~~~~~~

.. automodule:: eventyay.base.reldate
   :members:

.. automodule:: eventyay.helpers.daterange
   :members:

Validation
~~~~~~~~~~

.. automodule:: eventyay.base.validators
   :members:

Cache
~~~~~

.. automodule:: eventyay.base.cache
   :members:

.. automodule:: eventyay.helpers.cache
   :members:

Storage
~~~~~~~

.. automodule:: eventyay.base.storage
   :members:

.. automodule:: eventyay.storage
   :members:

Context Processors
------------------

.. automodule:: eventyay.base.context
   :members:

.. automodule:: eventyay.control.context
   :members:

.. automodule:: eventyay.common.context_processors
   :members:

Metrics & Monitoring
--------------------

.. automodule:: eventyay.base.metrics
   :members:

Timeline & Activity
-------------------

.. automodule:: eventyay.base.timeline
   :members:


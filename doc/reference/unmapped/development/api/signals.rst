.. highlight:: python
   :linenothreshold: 5

Signals Reference
=================

Eventyay uses Django's signal dispatcher to allow plugins and components to react to various events happening within the system.

Base Signals
------------

These signals are available from ``eventyay.base.signals``:

Event Signals
~~~~~~~~~~~~~

**eventyay.base.signals.event_copy_data**

Sent when an event is being cloned to allow plugins to copy their own data.

* **Sender:** Event instance (source)
* **Arguments:**
  
  * ``new_event`` - The newly created Event object

Order Signals
~~~~~~~~~~~~~

**eventyay.base.signals.order_placed**

Sent when an order has been successfully placed.

* **Sender:** Order instance
* **Arguments:** ``order`` - The Order object

**eventyay.base.signals.order_paid**

Sent when an order has been fully paid.

* **Sender:** Order instance
* **Arguments:** ``order`` - The Order object

**eventyay.base.signals.order_canceled**

Sent when an order has been canceled.

* **Sender:** Order instance
* **Arguments:** ``order`` - The Order object

**eventyay.base.signals.order_changed**

Sent when an order has been modified (positions added/removed, etc).

* **Sender:** Order instance
* **Arguments:** ``order`` - The Order object

Check-in Signals
~~~~~~~~~~~~~~~~

**eventyay.base.signals.checkin_created**

Sent when a check-in has been performed.

* **Sender:** Checkin instance
* **Arguments:** ``checkin`` - The Checkin object

Plugin Signals
~~~~~~~~~~~~~~

**eventyay.base.signals.register_payment_providers**

Sent to discover available payment providers.

* **Sender:** None
* **Expected return value:** List of payment provider classes

**eventyay.base.signals.register_ticket_outputs**

Sent to discover available ticket output formats.

* **Sender:** None
* **Expected return value:** List of ticket output classes

**eventyay.base.signals.register_sales_channels**

Sent to discover available sales channels.

* **Sender:** None
* **Expected return value:** List of SalesChannel instances

**eventyay.base.signals.register_data_exporters**

Sent to discover available data exporters.

* **Sender:** Event instance
* **Expected return value:** List of exporter classes

Talk Component Signals
----------------------

Signals for talk submissions, reviews, and scheduling are integrated into the unified base signals system. Common talk-related signals include:

**Submission-related signals**

Available through the ``eventyay.common.signals`` module for submission management, state changes, and notifications.

**Schedule-related signals**

Available through the ``eventyay.common.signals`` module for schedule releases and updates.

**Review-related signals**

Available through the ``eventyay.common.signals`` module for review submissions and scoring.

Video Component Signals
-----------------------

Signals for video rooms and streaming are integrated into the unified features system and can be accessed through the base signals as needed for virtual event features.

Usage Examples
--------------

Listening to Signals
~~~~~~~~~~~~~~~~~~~~

To listen to a signal in your plugin:

.. code-block:: python

    from django.dispatch import receiver
    from eventyay.base.signals import order_placed
    
    @receiver(order_placed, dispatch_uid="my_plugin_order_placed")
    def handle_order_placed(sender, **kwargs):
        order = kwargs['order']
        # Do something with the order
        print(f"Order {order.code} was placed!")

Registering Providers
~~~~~~~~~~~~~~~~~~~~~

To register a payment provider:

.. code-block:: python

    from django.dispatch import receiver
    from eventyay.base.signals import register_payment_providers
    from eventyay.base.payment import BasePaymentProvider
    
    class MyPaymentProvider(BasePaymentProvider):
        identifier = 'myprovider'
        verbose_name = 'My Payment Provider'
        # ... implement required methods
    
    @receiver(register_payment_providers, dispatch_uid="myplugin_payment")
    def register_payment_provider(sender, **kwargs):
        return [MyPaymentProvider]

Returning Multiple Items
~~~~~~~~~~~~~~~~~~~~~~~~

Some signals expect you to return multiple items:

.. code-block:: python

    from django.dispatch import receiver
    from eventyay.base.signals import register_data_exporters
    
    @receiver(register_data_exporters, dispatch_uid="myplugin_exporters")
    def register_exporters(sender, **kwargs):
        return [
            MyCSVExporter,
            MyJSONExporter,
            MyXMLExporter,
        ]

Signal Best Practices
---------------------

1. **Use unique dispatch_uid**: Always provide a unique ``dispatch_uid`` to prevent signals from being registered multiple times.

2. **Handle exceptions**: Wrap your signal handlers in try-except blocks to prevent errors in one handler from affecting others.

3. **Keep it fast**: Signal handlers should execute quickly. For long-running tasks, use Celery.

4. **Document your signals**: If your plugin defines new signals, document them clearly for other developers.

5. **Don't modify sender**: Never modify the sender object unless explicitly documented.

See Also
--------

* :ref:`pluginsetup` - Creating plugins
* `Django Signals Documentation <https://docs.djangoproject.com/en/stable/topics/signals/>`_


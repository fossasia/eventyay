.. highlight:: python
   :linenothreshold: 5

Services API
============

Eventyay provides a comprehensive services layer in ``app/eventyay/base/services/`` that handles common operations across all components.

Order Services
--------------

Located in ``eventyay.base.services.orders``:

Creating Orders
~~~~~~~~~~~~~~~

.. code-block:: python

    from eventyay.base.services.orders import OrderCreator
    
    creator = OrderCreator(event=event)
    order = creator.create(
        positions=[
            {'product': product, 'variation': variation, 'count': 2}
        ],
        email='customer@example.com',
        locale='en',
        sales_channel='web'
    )

Modifying Orders
~~~~~~~~~~~~~~~~

.. code-block:: python

    from eventyay.base.services.orders import OrderModifier
    
    modifier = OrderModifier(order=order)
    modifier.add_position(product=product, variation=variation)
    modifier.remove_position(position_id=123)
    modifier.save()

Canceling Orders
~~~~~~~~~~~~~~~~

.. code-block:: python

    from eventyay.base.services.orders import OrderCanceler
    
    canceler = OrderCanceler(order=order)
    canceler.cancel()

Email Services
--------------

Located in ``eventyay.base.services.mail``:

Sending Event Emails
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from eventyay.base.services.mail import SendMailService
    
    service = SendMailService(event=event)
    service.send_mail(
        subject='Welcome!',
        message='Thank you for your order',
        recipient_list=['customer@example.com'],
        order=order  # Optional, for tracking
    )

Using Email Templates
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from eventyay.base.models import MailTemplate
    from eventyay.base.services.mail import TemplateMailService
    
    template = MailTemplate.objects.get(event=event, identifier='order_placed')
    service = TemplateMailService(template=template)
    service.send(
        order=order,
        context={'custom_var': 'value'}
    )

Invoice Services
----------------

Located in ``eventyay.base.services.invoices``:

Generating Invoices
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from eventyay.base.services.invoices import InvoiceGenerator
    
    generator = InvoiceGenerator(order=order)
    invoice = generator.generate()

Regenerating Invoices
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from eventyay.base.services.invoices import InvoiceRegenerator
    
    regenerator = InvoiceRegenerator(invoice=invoice)
    regenerator.regenerate()

Ticket Services
---------------

Located in ``eventyay.base.services.tickets``:

Generating Tickets
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from eventyay.base.services.tickets import TicketGenerator
    
    generator = TicketGenerator(event=event)
    pdf_data = generator.generate(order_position=position)

Check-in Services
-----------------

Located in ``eventyay.base.services.checkin``:

Performing Check-ins
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from eventyay.base.services.checkin import CheckinService
    
    service = CheckinService(checkin_list=checkin_list)
    result = service.checkin(
        secret='TICKET_SECRET',
        force=False,
        ignore_unpaid=False
    )
    
    if result['status'] == 'ok':
        print(f"Checked in: {result['position']}")

Payment Services
----------------

Located in ``eventyay.base.services.payments``:

Processing Payments
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from eventyay.base.services.payments import PaymentProcessor
    
    processor = PaymentProcessor(order=order, payment_provider='stripe')
    payment = processor.create_payment(amount=order.total)
    
    # After payment confirmation
    processor.confirm_payment(payment=payment)

Refunding Payments
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from eventyay.base.services.payments import RefundService
    
    service = RefundService(order=order)
    refund = service.create_refund(
        payment=payment,
        amount=50.00,
        provider='stripe'
    )

Cart Services
-------------

Located in ``eventyay.base.services.cart``:

Managing Carts
~~~~~~~~~~~~~~

.. code-block:: python

    from eventyay.base.services.cart import CartManager
    
    manager = CartManager(event=event, session=request.session)
    
    # Add to cart
    manager.add_product(
        product=product,
        variation=variation,
        count=2
    )
    
    # Get cart contents
    cart_positions = manager.get_cart()
    
    # Clear cart
    manager.clear()

Quota Services
--------------

Located in ``eventyay.base.services.quotas``:

Checking Availability
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from eventyay.base.services.quotas import QuotaAvailability
    
    checker = QuotaAvailability(event=event)
    
    # Check if product is available
    available, left = checker.check_product(product=product, count=2)
    
    if available:
        print(f"{left} tickets remaining")

Talk Component Services
------------------------

Submission Services
~~~~~~~~~~~~~~~~~~~

Located in ``eventyay.submission.services``:

.. code-block:: python

    from eventyay.submission.services import SubmissionService
    
    service = SubmissionService(event=event)
    
    # Create submission
    submission = service.create_submission(
        title='My Talk',
        description='Description',
        speaker=speaker_profile,
        submission_type=submission_type
    )
    
    # Accept submission
    service.accept_submission(submission=submission)

Schedule Services
~~~~~~~~~~~~~~~~~

Located in ``eventyay.schedule.services``:

.. code-block:: python

    from eventyay.schedule.services import ScheduleService
    
    service = ScheduleService(event=event)
    
    # Create schedule
    schedule = service.create_schedule(version='1.0')
    
    # Add talk to schedule
    service.add_talk_slot(
        schedule=schedule,
        submission=submission,
        start=datetime(2025, 3, 15, 10, 0),
        room=room
    )
    
    # Publish schedule
    service.publish_schedule(schedule=schedule)

Video Component Services
-------------------------

Room Services
~~~~~~~~~~~~~

Located in ``eventyay.features.live.services``:

.. code-block:: python

    from eventyay.features.live.services import RoomService
    
    service = RoomService(event=event)
    
    # Create virtual room
    room = service.create_room(
        name='Main Hall',
        description='Main conference room',
        capacity=500
    )
    
    # Add user to room
    service.add_user_to_room(room=room, user=user)

Streaming Services
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from eventyay.features.live.services import StreamingService
    
    service = StreamingService(room=room)
    
    # Start stream
    stream = service.start_stream(
        provider='bbb',  # BigBlueButton
        moderator=user
    )
    
    # Get join URL
    join_url = service.get_join_url(stream=stream, user=user)

Service Best Practices
-----------------------

1. **Use services, not direct model manipulation**: Services handle business logic, validation, and side effects.

2. **Pass explicit parameters**: Don't rely on global state or request objects within services.

3. **Handle errors gracefully**: Services may raise specific exceptions - catch and handle them appropriately.

4. **Use transactions**: When modifying multiple objects, wrap service calls in database transactions.

5. **Keep services stateless**: Services should not maintain state between calls.

Example: Complete Order Flow
-----------------------------

.. code-block:: python

    from django.db import transaction
    from eventyay.base.services.orders import OrderCreator
    from eventyay.base.services.mail import SendMailService
    from eventyay.base.services.invoices import InvoiceGenerator
    
    with transaction.atomic():
        # Create order
        creator = OrderCreator(event=event)
        order = creator.create(
            positions=[{'product': product, 'count': 1}],
            email='customer@example.com',
            locale='en'
        )
        
        # Generate invoice
        invoice_gen = InvoiceGenerator(order=order)
        invoice = invoice_gen.generate()
        
        # Send confirmation email
        mail_service = SendMailService(event=event)
        mail_service.send_mail(
            subject=f'Order {order.code}',
            message='Your order has been confirmed',
            recipient_list=[order.email],
            order=order
        )

See Also
--------

* :doc:`talk_models` - Talk component models documentation
* :doc:`video_models` - Video component models documentation
* :doc:`unified_models` - Base models documentation
* :doc:`signals` - Signals reference
* :ref:`pluginsetup` - Creating plugins


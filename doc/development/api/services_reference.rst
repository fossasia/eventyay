.. highlight:: python
   :linenothreshold: 5

Services Module Reference
=========================

Complete reference for all service modules in ``eventyay.base.services``.

Order Management
----------------

.. automodule:: eventyay.base.services.orders
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: eventyay.base.services.cart
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: eventyay.base.services.pricing
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: eventyay.base.services.quotas
   :members:
   :undoc-members:
   :show-inheritance:

Payment & Invoicing
-------------------

.. automodule:: eventyay.base.services.invoices
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: eventyay.base.services.mail
   :members:
   :undoc-members:
   :show-inheritance:

Check-in & Tickets
------------------

.. automodule:: eventyay.base.services.checkin
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: eventyay.base.services.tickets
   :members:
   :undoc-members:
   :show-inheritance:

Video & Streaming
-----------------

.. automodule:: eventyay.base.services.bbb
   :members:
   :undoc-members:
   :show-inheritance:

Janus WebRTC Service
^^^^^^^^^^^^^^^^^^^^

The Janus service provides WebRTC video conferencing integration. See ``eventyay.base.services.janus`` for implementation details.

.. automodule:: eventyay.base.services.turn
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: eventyay.base.services.room
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: eventyay.base.services.chat
   :members:
   :undoc-members:
   :show-inheritance:

Interactive Features
--------------------

.. automodule:: eventyay.base.services.poll
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: eventyay.base.services.poster
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: eventyay.base.services.question
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: eventyay.base.services.roulette
   :members:
   :undoc-members:
   :show-inheritance:

Exhibition
----------

.. automodule:: eventyay.base.services.exhibition
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: eventyay.base.services.reactions
   :members:
   :undoc-members:
   :show-inheritance:

User & Auth
-----------

.. automodule:: eventyay.base.services.auth
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: eventyay.base.services.user
   :members:
   :undoc-members:
   :show-inheritance:

Event Management
----------------

.. automodule:: eventyay.base.services.event
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: eventyay.base.services.cancelevent
   :members:
   :undoc-members:
   :show-inheritance:

Data Management
---------------

.. automodule:: eventyay.base.services.export
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: eventyay.base.services.orderimport
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: eventyay.base.services.shredder
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: eventyay.base.services.cleanup
   :members:
   :undoc-members:
   :show-inheritance:

System
------

Tasks Module
^^^^^^^^^^^^

The tasks module provides Celery task base classes for background job processing.

**Key Classes:**

- ``ProfiledTask`` - Task with performance profiling
- ``EventTask`` - Event-scoped task
- ``OrganizerUserTask`` - User-scoped task
- ``ProfiledEventTask`` - Event task with profiling

.. automodule:: eventyay.base.services.locking
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: eventyay.base.services.notifications
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: eventyay.base.services.stats
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: eventyay.base.services.update_check
   :members:
   :undoc-members:
   :show-inheritance:

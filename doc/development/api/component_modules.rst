.. highlight:: python
   :linenothreshold: 5

Component Modules
=================

Documentation for the main component modules in the unified Eventyay system.

Tickets Component (Presale)
----------------------------

Presale Views
~~~~~~~~~~~~~

.. automodule:: eventyay.presale.views.event
   :members:
   :no-index:

.. automodule:: eventyay.presale.views.cart
   :members:
   :exclude-members: get_or_create_cart_id
   :no-index:

.. automodule:: eventyay.presale.views.checkout
   :members:

.. automodule:: eventyay.presale.views.order
   :members:

Presale Signals
~~~~~~~~~~~~~~~

.. automodule:: eventyay.presale.signals
   :members:

Talk Component (CfP & Organizer)
---------------------------------

Call for Papers
~~~~~~~~~~~~~~~

.. automodule:: eventyay.cfp.permissions
   :members:

.. automodule:: eventyay.cfp.signals
   :members:
   :no-index:

Organizer Interface
~~~~~~~~~~~~~~~~~~~

.. automodule:: eventyay.orga.signals
   :members:
   :no-index:

.. automodule:: eventyay.orga.permissions
   :members:
   :no-index:

Submission Management
~~~~~~~~~~~~~~~~~~~~~

.. automodule:: eventyay.submission.signals
   :members:
   :no-index:

Schedule Management
~~~~~~~~~~~~~~~~~~~

.. automodule:: eventyay.schedule.signals
   :members:
   :no-index:

Public Agenda
~~~~~~~~~~~~~

.. automodule:: eventyay.agenda.signals
   :members:
   :no-index:

.. automodule:: eventyay.agenda.permissions
   :members:

.. automodule:: eventyay.agenda.recording
   :members:
   :no-index:

Person & Speaker Management
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: eventyay.person.signals
   :members:
   :no-index:

.. automodule:: eventyay.person.permissions
   :members:

Talk Rules & Permissions
~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: eventyay.talk_rules.person
   :members:

.. automodule:: eventyay.talk_rules.submission
   :members:

Control Panel (Admin Interface)
--------------------------------

Control Views
~~~~~~~~~~~~~

Documentation for control panel views is available in the implementation section.

Control Signals
~~~~~~~~~~~~~~~

.. automodule:: eventyay.control.signals
   :members:

Control Permissions
~~~~~~~~~~~~~~~~~~~

.. automodule:: eventyay.control.permissions
   :members:
   :no-index:

Navigation
~~~~~~~~~~

.. automodule:: eventyay.control.navigation
   :members:

Log Display
~~~~~~~~~~~

.. automodule:: eventyay.control.logdisplay
   :members:

.. automodule:: eventyay.common.log_display
   :members:

Common Utilities
----------------

Common Signals
~~~~~~~~~~~~~~

.. automodule:: eventyay.common.signals
   :members:
   :no-index:

Common Tasks
~~~~~~~~~~~~

.. automodule:: eventyay.common.tasks
   :members:

Common Exceptions
~~~~~~~~~~~~~~~~~

.. automodule:: eventyay.common.exceptions
   :members:

Text Processing
~~~~~~~~~~~~~~~

Text processing utilities are located in ``eventyay.common.text`` package.

Mail Handling
~~~~~~~~~~~~~

.. automodule:: eventyay.common.mail
   :members:

.. automodule:: eventyay.mail.signals
   :members:
   :no-index:

Multi-domain Support
--------------------

.. automodule:: eventyay.multidomain.models
   :members:

.. automodule:: eventyay.multidomain.urlreverse
   :members:
   :no-index:

API Module
----------

API Authentication
~~~~~~~~~~~~~~~~~~

API authentication modules are located in ``eventyay.api.auth`` package.

API Middleware
~~~~~~~~~~~~~~

.. automodule:: eventyay.api.middleware
   :members:

OAuth
~~~~~

.. automodule:: eventyay.api.oauth
   :members:

Webhooks
~~~~~~~~

.. automodule:: eventyay.api.webhooks
   :members:

API Serializers
~~~~~~~~~~~~~~~

.. automodule:: eventyay.api.serializers.event
   :members:
   :exclude-members: create
   :no-index:

.. automodule:: eventyay.api.serializers.order
   :members:
   :exclude-members: create
   :no-index:

.. automodule:: eventyay.api.serializers.product
   :members:
   :exclude-members: create
   :no-index:

Event Management
----------------

Event Services
~~~~~~~~~~~~~~

.. automodule:: eventyay.event.services
   :members:

.. automodule:: eventyay.event.stages
   :members:

.. automodule:: eventyay.event.utils
   :members:

Helpers & Utilities
-------------------

Helper Modules
~~~~~~~~~~~~~~

.. automodule:: eventyay.helpers.countries
   :members:

.. automodule:: eventyay.helpers.http
   :members:

.. automodule:: eventyay.helpers.json
   :members:

.. automodule:: eventyay.helpers.security
   :members:

.. automodule:: eventyay.helpers.thumb
   :members:

Formats
~~~~~~~

.. automodule:: eventyay.helpers.formats.de
   :members:

.. automodule:: eventyay.helpers.formats.en
   :members:

Template Tags
~~~~~~~~~~~~~

.. automodule:: eventyay.base.templatetags.money
   :members:

.. automodule:: eventyay.base.templatetags.rich_text
   :members:

.. automodule:: eventyay.helpers.templatetags.thumb
   :members:

.. automodule:: eventyay.common.templatetags.times
   :members:


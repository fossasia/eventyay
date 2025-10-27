.. highlight:: python
   :linenothreshold: 5

Unified Component Models
=========================

These models represent the unified architecture of Eventyay, integrating tickets, talk, and video components.

Base Models & Mixins
--------------------

.. autoclass:: eventyay.base.models.PretalxModel
   :members:

.. autoclass:: eventyay.base.models.LoggedModel
   :members:
   :no-index:

.. autoclass:: eventyay.base.models.TimestampedModel
   :members:
   :no-index:

.. autoclass:: eventyay.base.models.FileCleanupMixin
   :members:

.. autoclass:: eventyay.base.models.GenerateCode
   :members:

Announcements & Notifications
------------------------------

.. autoclass:: eventyay.base.models.Announcement
   :members:

.. autoclass:: eventyay.base.models.NotificationSetting
   :members:

.. autoclass:: eventyay.base.models.QueuedMail
   :members:

.. autoclass:: eventyay.base.models.MailTemplate
   :members:

.. autoclass:: eventyay.base.models.MailTemplateRoles
   :members:

Access Control
--------------

.. autoclass:: eventyay.base.models.SubmitterAccessCode
   :members:
   :exclude-members: urls, DoesNotExist, MultipleObjectsReturned

Feedback
--------

.. autoclass:: eventyay.base.models.Feedback
   :members:

Availability
------------

.. autoclass:: eventyay.base.models.Availability
   :members:

Files
-----

.. autoclass:: eventyay.base.models.CachedFile
   :members:

Logging & Audit
---------------

.. autoclass:: eventyay.base.models.LogEntry
   :members:
   :no-index:

.. autoclass:: eventyay.base.models.ActivityLog
   :members:
   :no-index:

.. autoclass:: eventyay.base.models.AuditLog
   :members:

.. autoclass:: eventyay.base.models.SystemLog
   :members:

Settings
--------

.. autoclass:: eventyay.base.models.GlobalSettings
   :members:

.. autoclass:: eventyay.base.models.Event_SettingsStore
   :members:

.. autoclass:: eventyay.base.models.Organizer_SettingsStore
   :members:

Billing
-------

.. autoclass:: eventyay.base.models.BillingInvoice
   :members:

.. autoclass:: eventyay.base.models.OrganizerBillingModel
   :members:


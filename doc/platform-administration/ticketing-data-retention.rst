.. _admin-ticketing-data-retention:

Ticketing data retention
========================

Platform administrators control how organizers may anonymize the ticketing data of their events. The settings are in
the admin area under **Global settings → Ticketing → Data retention**. Changing them requires an active staff session.

.. list-table::
   :header-rows: 1
   :widths: 40 15 45

   * - Setting
     - Default
     - Meaning
   * - Minimum days after the event before manual anonymization
     - 14
     - Organizers can anonymize an event only this many days after its end (the last date for events with several
       dates). Set ``0`` to allow it as soon as the event is over.
   * - Retention periods offered to organizers
     - 30, 60, 90, 180, 365
     - Choices for automatic anonymization, as days after the event.
   * - First reminder (days before anonymization)
     - 14
     - How long before an automatic anonymization organizers are warned.
   * - Offer the option to keep original data in trash
     - on
     - Whether organizers may keep the original data for a limited time so an administrator can restore it.
   * - Days to keep original data in trash
     - 30
     - How long that data is kept.
   * - Maximum postponement in days
     - no cap
     - How far organizers may postpone an automatic anonymization. ``0`` disables postponement.

.. note::

   The minimum days setting applies to manual anonymization today. The other settings are stored and used by the
   automatic retention policy and the trash option as they become available.

Who may anonymize
-----------------

Anonymizing a whole event is limited to members of the organizer's Core Organizing Team. Platform administrators are
not part of that team by default. The Core Organizing Team cannot be deleted, always has every permission, and always
keeps at least one active member.

Orders that were anonymized cannot be restored from the application; make sure organizers understand this, and point
them to :ref:`user-anonymizing-ticketing-data`.

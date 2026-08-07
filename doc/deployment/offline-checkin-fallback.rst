Offline Check-in Fallback Procedure
====================================

When the eventyay server is unavailable during an event (network outage,
server overload, or maintenance window), venue staff must be able to
continue checking in attendees. This document describes the offline
fallback workflow and the steps to resynchronise once connectivity is
restored.

.. note::

   This procedure applies to check-in devices that use the eventyay
   check-in API (``/api/v1/organizers/<org>/checkin/redeem/``). The
   specifics depend on the check-in client application in use.

Pre-event Preparation
---------------------

1. **Sync the attendee list** to each check-in device before the event
   starts. Most check-in apps support downloading the full attendee list
   for offline use.

2. **Verify the local cache** on each device by performing a test scan
   while the device is in airplane mode. The scan should succeed against
   the locally cached list.

3. **Distribute backup printed lists** of attendee names and order codes
   to each entrance as a last-resort fallback.

4. **Brief venue staff** on the offline procedure so they know what to
   do if the device shows a connection error.

During an Outage
----------------

When the check-in device cannot reach the server:

1. The device should automatically fall back to **local cache validation**.
   Scanned barcodes are matched against the previously downloaded attendee
   list.

2. Check-in records are **stored locally** on the device with timestamps.

3. Staff should **continue scanning normally**. The device UI should
   indicate that it is operating in offline mode.

4. If the device does not support automatic offline mode, staff should
   use the **printed backup list** and mark attendees manually with a pen.

.. warning::

   Duplicate check-in detection may not work across devices during an
   outage because devices cannot communicate with each other. Accept this
   risk and resolve duplicates after connectivity is restored.

After Connectivity is Restored
------------------------------

1. The check-in device should **automatically sync** locally stored
   check-in records back to the server when connectivity returns.

2. **Review the sync report** for conflicts:

   - *Duplicate scans*: the same ticket scanned on multiple devices.
     The server keeps the earliest timestamp.
   - *Rejected scans*: tickets that were valid in the local cache but
     have since been cancelled or refunded on the server.

3. **Verify totals**: compare the number of check-ins reported by each
   device with the server total to ensure no records were lost.

Known Limitations
-----------------

- **No real-time duplicate detection** across devices during an outage.
- **Stale attendee data**: if tickets are sold or cancelled after the
  last sync, the local cache will not reflect those changes.
- **Manual check-ins** (printed list) require manual data entry into the
  system after the event.

Recommended Device Configuration
---------------------------------

For events expecting more than 500 attendees, configure the check-in
devices as follows:

- Set the **sync interval** to the shortest supported period (e.g. every
  30 seconds) so the local cache is as fresh as possible before an outage.
- Enable **automatic offline mode** so the device switches seamlessly
  without staff intervention.
- Ensure the device has sufficient **local storage** for the full
  attendee list plus check-in records.

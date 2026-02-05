Telemetry System Documentation
==============================

Eventyay includes a telemetry system that sends aggregated usage data once per day
to help track version adoption, deployment patterns, and usage statistics.

What Data is Collected
----------------------

**Instance Identification:**

* Instance ID (randomly generated UUID, persistent)
* Canonical base URL (SHA256 hashed for privacy)

**Version Information:**

* Eventyay version
* Python version  
* Build metadata (git branch/commit if available)

**Environment:**

* OS family (Linux, Darwin, Windows)
* OS version
* Deployment type (docker, kubernetes, native)
* Database type (postgresql, mysql, sqlite)
* Database major version
* Storage backend (file, s3, etc.)
* Feature flags (Celery enabled, Redis enabled)

**Usage Metrics (bucketed ranges, not exact counts):**

* Events: 0, 1-10, 11-50, 51-100, 101-500, 501-1000, 1001-5000, 5000+
* Live events
* Organizers
* Orders (total and paid separately)
* Tickets issued (total, paid, free separately)
* Submissions
* Attendees
* Uptime (bucketed: 0-1h, 1-24h, 1-7d, 7-30d, 30d+)

**Enabled Plugins:**

* List of plugin module names currently active

**Optional Contact:**

* Maintainer email (if provided by admin)

What is NOT Collected
---------------------

* No exact counts (all metrics are bucketed into ranges)
* No personal information (user names, attendee emails, addresses)
* No event content (titles, descriptions, submission details)
* No financial data (ticket prices, payment amounts)
* No IP addresses or geolocation data
* No user-identifiable information

How to Enable
-------------

Telemetry is **disabled by default** and requires explicit opt-in configuration.

Via Admin Settings
^^^^^^^^^^^^^^^^^^

1. Log in as superuser
2. Go to **Admin** → **Global Settings** → **Update check**
3. Scroll down to telemetry settings
4. Check **"Enable telemetry"**
5. Enter endpoint URL (provided by Eventyay maintainers)
6. Enter API key (provided by Eventyay maintainers)
7. (Optional) Enter your contact email
8. Click **Save**

Via Django Shell
^^^^^^^^^^^^^^^^

.. code-block:: python

    docker exec -it eventyay-web python manage.py shell
    
    from eventyay.base.settings import GlobalSettingsObject
    gs = GlobalSettingsObject()
    
    gs.settings.set('telemetry_enabled', True)
    gs.settings.set('telemetry_endpoint', 'https://script.google.com/...')
    gs.settings.set('telemetry_api_key', 'your-api-key')
    gs.settings.set('telemetry_contact_email', 'admin@example.com')

How It Works
------------

**Automatic Daily Heartbeat:**

1. Every ~15 minutes, Celery periodic task fires
2. Checks if telemetry is enabled
3. Checks if 23+ hours have passed since last send
4. If both true, collects metrics and sends payload
5. Updates ``telemetry_last_sent`` timestamp on success

**Data Flow:**

* Eventyay → HTTPS POST with JSON payload
* Google Apps Script receiver validates API key
* Checks rate limit (max 1 per 23 hours per instance)
* Appends row to Google Sheet
* Returns 200 OK response

Privacy & Compliance
--------------------

**Data Minimization:**

* All numeric metrics are bucketed (e.g., "11-50" not "37")
* Base URLs are SHA256 hashed and truncated
* No timestamps except server-side ``received_at_utc``
* No database queries, payload inspection, or IP logging on server side

**Transparency:**

* All collection code is open source and auditable
* This documentation describes exactly what is collected
* Data is stored in Google Sheet (not a black-box database)

**Legal:**

* No GDPR concerns (no personal data collected)
* No PII (personally identifiable information)
* Similar to standard web analytics

**Opt-In:**

* Must be explicitly enabled by administrator
* Can be disabled at any time
* No telemetry sent until configured

For Maintainers: Deploying the Receiver
----------------------------------------

See ``doc/admin/telemetry_receiver.gs`` for the Google Apps Script implementation.

Quick Setup
^^^^^^^^^^^

1. Create new Google Sheet
2. Open **Extensions** → **Apps Script**
3. Paste contents of ``telemetry_receiver.gs``
4. Go to **Project Settings** → **Script Properties**
5. Add property: ``API_KEY`` = ``your-secret-key``
6. Deploy as **Web App**:

   * Execute as: **Me**
   * Who has access: **Anyone**

7. Copy deployment URL
8. Distribute URL and API key to Eventyay admins

Sheet Structure
^^^^^^^^^^^^^^^

The script creates a ``heartbeats`` tab with these columns:

================== ================================================
Column             Description
================== ================================================
received_at_utc    Server timestamp when received
instance_id        UUID of this Eventyay installation
eventyay_version   Version string (e.g., "0.1")
schema_version     Payload schema version
build_metadata     Git branch/commit info
canonical_base_url SHA256 hash of base URL
deployment_type    docker / kubernetes / native
os_family          Linux / Darwin / Windows
database_type      postgresql / mysql / sqlite
database_version   Major version number
enabled_plugins    JSON array of plugin names
events_bucket      Bucketed event count
attendees_bucket   Bucketed attendee count
tickets_issued_bucket Bucketed ticket count
paid_tickets_bucket  Paid ticket count bucket
free_tickets_bucket  Free ticket count bucket
orders_bucket      Bucketed order count
uptime_bucket      Uptime range in days
background_jobs_enabled Boolean Celery status
storage_backend    file / s3 / etc.
error_count_bucket Error metrics (placeholder, always "0")
maintainer_contact Optional email address
raw_payload        Full JSON for debugging
================== ================================================

Features Implemented
--------------------

Daily heartbeat collection

Bucketed metrics (privacy-preserving)

Google Apps Script receiver

API key authentication

Rate limiting (23 hours)

Celery integration

Auto-discovery of deployment environment

SHA256 URL hashing

Opt-in (disabled by default)

Future Enhancements
-------------------

The following may be added in future versions:

* IP/country detection (best-effort)
* Additional performance metrics
* Error rate statistics
* Feature usage patterns
* BigQuery export option

All enhancements will be documented and code remains open source.

Troubleshooting
---------------

**Telemetry not sending:**

* Check ``telemetry_enabled`` is ``True``
* Verify 23 hours have passed since last send
* Ensure Celery workers are running
* Check endpoint URL and API key are correct

**401 Unauthorized:**

* API key mismatch between Eventyay and Apps Script
* Verify Script Properties configuration

**429 Rate Limited:**

* Same instance sent heartbeat within 23 hours
* This is expected behavior, wait for next cycle

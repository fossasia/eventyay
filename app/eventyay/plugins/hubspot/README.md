# HubSpot CRM Plugin for Eventyay

Minimal initial implementation of HubSpot integration for Eventyay.

## Features

✅ **When an order is paid**, attendees are automatically synced to HubSpot as contacts.

✅ **Asynchronous**, non-blocking integration via Celery.

✅ **Hardcoded minimal mapping** (marked TODO for future UI):
- `attendee_email` → HubSpot `email` (unique identifier)
- `attendee_name_parts['first_name']` → HubSpot `firstname`
- `attendee_name_parts['last_name']` → HubSpot `lastname`

✅ **Failure-safe**: Logs errors but doesn't block order confirmation.

✅ **Retry logic**: Up to 3 retries with 60-second backoff on network/API failures.

## Out of Scope (for Future PRs)

❌ Field-mapping UI
❌ OAuth flow
❌ HubSpot list/workflow management
❌ Order cancellation handling
❌ Database models for mapping storage

---

## Installation & Configuration

### 1. Plugin Registration

The plugin is automatically discovered by Eventyay's plugin system.

### 2. Enable for an Event

1. Go to **Event Settings** → **Plugins**
2. Enable **"HubSpot CRM"**
3. Go to **Event Settings** → **HubSpot CRM**
4. Check **"Enable HubSpot sync"**
5. Enter your **HubSpot Private App Access Token**
6. Save

### 3. Get Your HubSpot Token

1. Go to [HubSpot App Marketplace](https://app.hubspot.com/l/app-marketplace)
2. Create a **Private App**
3. Grant minimal scopes:
   - `crm.objects.contacts.write`
   - `crm.objects.contacts.read`
4. Copy the **"Private App Access Token"**
5. Paste into Eventyay plugin settings

---

## Manual Testing

### Prerequisites

- Local Eventyay development environment running
- Celery worker running (`celery -A eventyay worker -l info`)
- HubSpot test account with a Private App token

### Steps

#### 1. Configure the Plugin

```bash
# Access your local Eventyay instance
# Go to Event Settings → Plugins
# Enable "HubSpot CRM"

# Then go to Event Settings → HubSpot CRM
# - Check "Enable HubSpot sync"
# - Paste your HubSpot test token
# - Click Save
```

#### 2. Create a Test Order

```bash
# In Eventyay admin:
# 1. Create an event (if not already done)
# 2. Add a product/ticket
# 3. Manually create an order:
#    - Email: buyer@example.com
#    - Add position with attendee details:
#      * Attendee email: john.doe@example.com
#      * Attendee name: John Doe
```

#### 3. Mark Order as Paid

```bash
# In Event → Orders:
# 1. Find your test order
# 2. Click "Confirm payment" or similar
# 3. This triggers the order_paid signal
# 4. HubSpot sync task is queued
```

#### 4. Monitor Celery Worker

Watch the Celery worker output for logs:

```
[2026-01-29 12:34:56,789: INFO/MainProcess]
eventyay.plugins.hubspot.tasks: HubSpot sync completed for order TEST01: 
synced 1, failed 0, skipped 0
```

#### 5. Verify in HubSpot

1. Go to **Contacts** in HubSpot
2. Search for `john.doe@example.com`
3. Verify:
   - Email: `john.doe@example.com`
   - First name: `John`
   - Last name: `Doe`

#### 6. Screenshot for PR

Take a screenshot showing:
- HubSpot contact created with attendee details
- Celery worker log output confirming sync
- Eventyay plugin settings page

---

## Running Tests

```bash
cd /home/abhi/eventyay-fork/app

# Install pytest and pytest-mock if needed
pip install pytest pytest-mock pytest-django

# Run all HubSpot plugin tests
pytest eventyay/plugins/hubspot/tests/

# Run specific test
pytest eventyay/plugins/hubspot/tests/test_hubspot.py::TestHubSpotSignals::test_order_paid_queues_hubspot_task -v
```

### Test Coverage

- ✅ Signal correctly queues task when enabled
- ✅ Signal doesn't queue task when disabled
- ✅ Signal doesn't queue task when API key missing
- ✅ Attendee data correctly mapped to HubSpot payload
- ✅ Positions without email are skipped
- ✅ API errors are logged and don't break order flow

---

## Code Structure

```
eventyay/plugins/hubspot/
├── __init__.py
├── apps.py                 # Plugin metadata and configuration
├── signals.py              # order_paid & nav_event_settings handlers
├── tasks.py                # Celery task for async syncing
├── forms.py                # Settings form (enable + API key)
├── views.py                # Settings view
├── urls.py                 # Plugin URL routes
├── templates/
│   └── hubspot/
│       └── settings.html   # Settings page template
└── tests/
    ├── __init__.py
    └── test_hubspot.py     # Unit tests
```

---

## Future Enhancements (OUT OF SCOPE)

These are explicitly marked as `TODO` in the code:

1. **Field Mapping UI**
   - Allow organizers to configure which OrderPosition fields map to which HubSpot properties
   - File: `tasks.py` → `_map_attendee_to_hubspot_contact()` function

2. **OAuth Flow**
   - Replace hardcoded API key with proper OAuth
   - Store refresh tokens securely
   - Auto-refresh expired tokens

3. **HubSpot Lists & Workflows**
   - Add synced contacts to HubSpot lists (e.g., "Eventyay Attendees")
   - Trigger HubSpot workflows for automation

4. **Order Cancellation**
   - Handle order refunds/cancellations by removing/updating HubSpot contacts

5. **Bulk Sync**
   - Sync existing orders (historical attendees) to HubSpot

---

## Debugging

### Enable Debug Logging

In Django settings:

```python
LOGGING = {
    'version': 1,
    'loggers': {
        'eventyay.plugins.hubspot': {
            'level': 'DEBUG',
        }
    }
}
```

### Celery Task Stuck?

Check if Celery worker is running:

```bash
# In /home/abhi/eventyay-fork/app
celery -A eventyay worker -l debug
```

### API Key Invalid?

Test your token directly:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://api.hubapi.com/crm/v3/objects/contacts/batch/create \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"inputs": [{"properties": {"email": "test@example.com"}}]}'
```

---

## Known Limitations

1. **No validation**: API key validity is not checked at save time
2. **No mapping UI**: Field mapping is hardcoded
3. **No list management**: Contacts are synced but not added to lists
4. **No cancel handling**: Cancelling an order doesn't update HubSpot
5. **Email identifier only**: Uses email for deduplication, not contact ID

---

## License

Same as Eventyay (AGPL-3.0)

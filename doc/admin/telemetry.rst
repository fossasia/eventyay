# Telemetry System Documentation

Eventyay includes an optional telemetry system that sends anonymous usage data to help
the maintainers understand how the platform is being used.

## What Data is Collected

The telemetry system collects **anonymous, aggregated** data including:

- **Instance ID**: A randomly generated UUID unique to your installation
- **Version Information**: Eventyay version, Python version
- **Environment**: OS type, database type, deployment method
- **Usage Metrics** (bucketed for privacy):
  - Number of events (e.g., "10-50" not exact count)
  - Number of orders
  - Number of submissions
- **Enabled plugins**: List of active plugins

### What is NOT Collected

- No personal information (emails, names, addresses)
- No event content or details
- No ticket prices or financial data
- No IP addresses or geolocation

## Enabling/Disabling Telemetry

Telemetry is **disabled by default** and requires explicit opt-in.

### Via Admin Settings

1. Go to Admin > Global Settings
2. Find "Telemetry Settings" section
3. Toggle "Enable Telemetry"
4. (Optional) Add a contact email

### Via Configuration File

Add to your `eventyay.cfg`:

```ini
[telemetry]
enabled = true
endpoint = https://script.google.com/macros/s/YOUR-DEPLOYMENT-ID/exec
api_key = YOUR-API-KEY
contact_email = admin@example.com  # optional
```

### Via Environment Variables

```bash
EVENTYAY_TELEMETRY_ENABLED=true
EVENTYAY_TELEMETRY_ENDPOINT=https://script.google.com/macros/s/.../exec
EVENTYAY_TELEMETRY_API_KEY=your-api-key
```

## How It Works

1. Once per day, the telemetry service collects anonymous metrics
2. Data is sent via HTTPS POST to the configured endpoint
3. The endpoint (Google Apps Script) validates and stores the data
4. Maintainers use the data to understand version adoption and usage patterns

## Privacy Considerations

- **Bucketed counts**: Numbers are grouped into ranges (e.g., "100-500") not exact values
- **No PII**: No personal data is ever transmitted
- **Opt-in**: You must explicitly enable telemetry
- **Open source**: The collection code is fully open source and auditable

## For Maintainers: Deploying the Receiver

See `doc/admin/telemetry_receiver.gs` for the Google Apps Script code.

### Setup Steps

1. Create a new Google Sheet
2. Open Extensions > Apps Script
3. Paste the contents of `telemetry_receiver.gs`
4. Add `API_KEY` in Script Properties
5. Deploy as Web App
6. Distribute the deployment URL

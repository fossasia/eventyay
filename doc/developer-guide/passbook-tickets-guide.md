# Passbook / Apple Wallet Tickets — Developer & Admin Guide

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [File Structure](#file-structure)
4. [How It Works (End-to-End)](#how-it-works-end-to-end)
5. [Plugin Components in Detail](#plugin-components-in-detail)
6. [Settings Reference](#settings-reference)
7. [Apple Developer Setup (Certificates)](#apple-developer-setup-certificates)
8. [How to Test](#how-to-test)
9. [Troubleshooting](#troubleshooting)
10. [Extending the Plugin](#extending-the-plugin)

---

## Overview

The Passbook plugin (`eventyay.plugins.passbook`) allows event attendees to download their tickets as `.pkpass` files — the format used by **Apple Wallet** (iOS) and many Android wallet apps (such as Google Wallet, PassWallet, Pass2U).

When enabled, a **"Wallet/Passbook"** download button appears alongside the PDF ticket download on the order confirmation page. The generated `.pkpass` file contains:

- Event name, date, and location
- Product/ticket type
- Attendee name
- QR code barcode for check-in
- Organizer details on the back of the pass
- Optional custom branding (icon, logo, background, colors)

The passbook configuration is available in the **Tickets** tab under event **Settings → Tickets → Download formats → Passbook Tickets**.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Django Signal System                         │
│                                                                 │
│  register_ticket_outputs ──► PassbookOutput (our plugin)        │
│  register_global_settings ──► Passbook certificate fields       │
└─────────────────────────────────────────────────────────────────┘
        │                               │
        ▼                               ▼
┌───────────────┐             ┌───────────────────────┐
│ Ticket        │             │ Global Settings Form  │
│ Settings View │             │ (certificates, keys)  │
│ (per-event)   │             └───────────────────────┘
└───────┬───────┘
        │ ProviderForm renders
        │ settings_form_fields
        ▼
┌───────────────────────┐
│ Per-Event Settings    │
│ - Enable/disable      │
│ - Icon, logo, bg      │
│ - Colors, location    │
│ - Retina scaling      │
└───────────────────────┘
        │
        │ User clicks "Download"
        ▼
┌───────────────────────┐
│ PassbookOutput        │
│  .generate(position)  │
│                       │
│  1. Build EventTicket │
│  2. Add fields/data   │
│  3. Attach images     │
│  4. Sign with certs   │
│  5. Return .pkpass    │
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│ wallet-py3k library   │
│  Pass.create(...)     │
│  Signs & zips to      │
│  .pkpass format       │
└───────────────────────┘
```

### Key Design Decisions

- **Internal plugin**: Built as a first-party plugin inside `eventyay.plugins.passbook`, following the exact same pattern as the existing `eventyay.plugins.ticketoutputpdf`.
- **Signal-based registration**: Uses Django's `register_ticket_outputs` signal so the ticket settings page discovers it automatically — no hardcoded references needed.
- **Hierarkey settings**: Uses `django-hierarkey` for cascading settings (global → organizer → event), so certificates can be set once globally and inherited by all events.
- **Enabled by default**: New events get `ticketoutput_passbook__enabled = True` via `Event.set_defaults()`.

---

## File Structure

```
app/eventyay/plugins/passbook/
├── __init__.py              # Empty — marks the package
├── apps.py                  # Django AppConfig with EventyayPluginMeta
├── forms.py                 # PNGImageField (image upload + conversion)
├── passbook.py              # PassbookOutput — the main ticket output class
├── signals.py               # Signal handlers + global settings + hierarkey defaults
└── static/
    └── eventyay_passbook/
        ├── icon.png         # Default 87×87 fallback icon
        └── logo.png         # Default 480×150 fallback logo
```

### Modified Existing Files

| File | Change |
|------|--------|
| `app/eventyay/config/settings.py` | Added `'eventyay.plugins.passbook'` to `_OURS_APPS` |
| `app/eventyay/control/views/event.py` | Replaced legacy `pretix_passbook` import with internal plugin in quick-setup |
| `app/pyproject.toml` | Added `wallet-py3k` dependency |

---

## How It Works (End-to-End)

### 1. Plugin Discovery (App Startup)

When Django starts, the `PassbookApp.ready()` method imports `signals.py`. This triggers two signal receivers:

```python
@receiver(register_ticket_outputs, dispatch_uid='output_passbook')
def register_ticket_output(sender, **kwargs):
    return PassbookOutput

@receiver(register_global_settings, dispatch_uid='passbook_global_settings')
def register_passbook_global_settings(sender, **kwargs):
    return OrderedDict([...])  # certificate fields
```

### 2. Admin Configures Settings

**Global Settings** (one-time, at the organizer/global level):
- Admin goes to **Global Settings** and fills in the Apple certificate fields (Team ID, Pass Type ID, certificate file, WWDR CA, private key).

**Per-Event Settings** (on the Tickets tab):
- Navigate to **Settings → Tickets → Download formats**
- The "Passbook Tickets" panel appears with a checkbox to enable/disable
- Below the checkbox: icon, logo, background image uploads, color pickers, and event location fields

### 3. Ticket Download Flow

When an attendee clicks **"Wallet/Passbook"** on their order page:

1. **View layer** (`OrderDownload` / `OrderPositionDownload` in `presale/views/order.py`) receives the request
2. A Celery task calls `PassbookOutput.generate(position)` asynchronously
3. `generate()` calls `generate_pass()` which:
   - Creates a `wallet.models.EventTicket` card
   - Populates header fields (admission time or event name)
   - Adds primary field (event name), secondary field (product), auxiliary fields (dates, attendee name)
   - Adds back fields (organizer info, order code, purchase date, website link)
   - Sets the QR barcode with the ticket secret
   - Configures relevant dates and expiration
   - Sets GPS location if configured
   - Attaches icon, logo, and background images (with retina variants if self-scaling is enabled)
   - Applies custom colors
4. `generate()` then:
   - Reads the Apple certificate, WWDR CA, and private key from settings
   - Writes them to temporary files
   - Calls `passfile.create(cert, key, ca, password)` which uses OpenSSL to sign and package the `.pkpass` zip
5. Returns `(filename, mimetype, content)` → the view sends it as a download

### 4. What's Inside a .pkpass File

A `.pkpass` is a signed ZIP archive containing:

```
my-event-ABCDE.pkpass
├── pass.json          # All ticket data (fields, barcode, colors, dates)
├── manifest.json      # SHA-1 hashes of all files
├── signature           # PKCS#7 detached signature of manifest.json
├── icon.png           # 29×29 pass icon
├── icon@2x.png        # 58×58 retina icon (optional)
├── icon@3x.png        # 87×87 retina icon (optional)
├── logo.png           # 160×50 logo shown on pass
├── logo@2x.png        # 320×100 retina logo (optional)
├── logo@3x.png        # 480×150 retina logo (optional)
├── background.png     # 180×220 background (optional)
├── background@2x.png  # 360×440 retina background (optional)
└── background@3x.png  # 540×660 retina background (optional)
```

---

## Plugin Components in Detail

### `apps.py` — Plugin Registration

```python
class PassbookApp(AppConfig):
    name = 'eventyay.plugins.passbook'
    verbose_name = _('Passbook Tickets')

    class EventyayPluginMeta:
        name = _('Passbook Tickets')
        category = 'FORMAT'        # Shows up under ticket format plugins
        featured = True            # Prominently displayed in plugin list
```

**Compatibility checks** (surfaced in the admin):
- `wallet-py3k` Python package must be installed
- `openssl` binary must be available in `$PATH`
- Pillow is recommended for image conversion

### `passbook.py` — PassbookOutput Class

Extends `BaseTicketOutput` (defined in `eventyay/base/ticketoutput.py`).

| Property/Method | Purpose |
|---|---|
| `identifier = 'passbook'` | Unique ID; settings stored as `ticketoutput_passbook_*` |
| `verbose_name` | Display name in the admin UI |
| `download_button_text` | Button text shown to attendees |
| `download_button_icon` | Font Awesome icon class (`fa-mobile`) |
| `multi_download_enabled = False` | Passbook doesn't support multi-position files |
| `settings_form_fields` | Returns all configurable fields for the admin panel |
| `generate_pass(position)` | Builds the `wallet.models.Pass` object with all data |
| `generate(position)` | Signs and returns the final `(filename, mimetype, bytes)` |

### `signals.py` — Signal Handlers & Global Settings

**Two signal receivers:**

1. `register_ticket_output` → returns `PassbookOutput` class so the ticket settings page discovers it
2. `register_passbook_global_settings` → adds certificate fields to the global settings form

**Helper classes:**
- `validate_rsa_privkey()` — validates PEM private key format
- `CertificateFileField` — accepts PEM or DER certificate files, auto-converts DER→PEM via OpenSSL

**Hierarkey defaults** — registers all file-type settings with `None` defaults so the cascading settings system knows about them.

### `forms.py` — PNGImageField

A factory that creates a `forms.FileField` with a custom `clean()` method:
- Accepts any image format Pillow can read
- Automatically converts to PNG
- Uses `ClearableBasenameFileInput` widget for the admin file upload UI

---

## Settings Reference

### Global Settings (Organizer-Level)

These are configured once and apply to all events under the organizer.

| Setting Key | Type | Required | Description |
|---|---|---|---|
| `passbook_team_id` | `CharField` | Yes (for signing) | Apple Developer Team ID |
| `passbook_pass_type_id` | `CharField` | Yes (for signing) | Pass Type Identifier (e.g., `pass.com.yourorg.events`) |
| `passbook_certificate_file` | `FileField` | Yes (for signing) | Pass Type certificate in PEM format |
| `passbook_wwdr_certificate_file` | `FileField` | Yes (for signing) | Apple WWDR intermediate CA certificate |
| `passbook_key` | `TextField` | Yes (for signing) | RSA private key in PEM format |
| `passbook_key_password` | `CharField` | No | Password for the private key (if encrypted) |

### Per-Event Settings (Ticket Tab)

These appear in **Settings → Tickets → Download formats → Passbook Tickets**.

| Setting Key | Type | Description |
|---|---|---|
| `ticketoutput_passbook__enabled` | `BooleanField` | Enable/disable passbook output for this event |
| `ticketoutput_passbook_selfscale` | `BooleanField` | Enable manual retina image scaling |
| `ticketoutput_passbook_icon` | `FileField` | Event icon (29×29, suggest 87×87 upload) |
| `ticketoutput_passbook_icon2x` | `FileField` | Retina 2x icon (58×58) — only if selfscale |
| `ticketoutput_passbook_icon3x` | `FileField` | Retina 3x icon (87×87) — only if selfscale |
| `ticketoutput_passbook_logo` | `FileField` | Event logo (160×50, suggest 480×150 upload) |
| `ticketoutput_passbook_logo2x` | `FileField` | Retina 2x logo (320×100) — only if selfscale |
| `ticketoutput_passbook_logo3x` | `FileField` | Retina 3x logo (480×150) — only if selfscale |
| `ticketoutput_passbook_background` | `FileField` | Background image (180×220, suggest 540×660 upload) |
| `ticketoutput_passbook_background2x` | `FileField` | Retina 2x background (360×440) — only if selfscale |
| `ticketoutput_passbook_background3x` | `FileField` | Retina 3x background (540×660) — only if selfscale |
| `ticketoutput_passbook_bg_color` | `CharField` | Background hex color (e.g., `#1A237E`) |
| `ticketoutput_passbook_fg_color` | `CharField` | Text hex color (e.g., `#FFFFFF`) |
| `ticketoutput_passbook_label_color` | `CharField` | Label hex color (e.g., `#B0BEC5`) |
| `ticketoutput_passbook_latitude` | `FloatField` | GPS latitude for location-aware notifications |
| `ticketoutput_passbook_longitude` | `FloatField` | GPS longitude for location-aware notifications |

---

## Apple Developer Setup (Certificates)

To generate real `.pkpass` files, you need Apple Developer certificates. Here's the full process:

### Step 1: Get a Pass Type ID

1. Go to [Apple Developer → Certificates, Identifiers & Profiles](https://developer.apple.com/account/resources/identifiers/list/passTypeId)
2. Click **+** → select **Pass Type IDs**
3. Enter a description and identifier (e.g., `pass.com.yourorg.events`)
4. Click **Register**

### Step 2: Create a Pass Type Certificate

1. Select your new Pass Type ID → click **Create Certificate**
2. Upload a CSR (Certificate Signing Request). Generate one with:
   ```bash
   export CERT_NAME=pass-eventyay
   openssl genrsa -out $CERT_NAME.key 2048
   openssl pkey -in $CERT_NAME.key -traditional > $CERT_NAME.key.pem
   openssl req -new -key $CERT_NAME.key -out $CERT_NAME.csr
   ```
3. Upload `$CERT_NAME.csr` to Apple, download the `.cer` file
4. Convert the certificate to PEM:
   ```bash
   openssl x509 -inform der -in $CERT_NAME.cer -out $CERT_NAME.pem
   ```

### Step 3: Get the WWDR Certificate

Download from Apple:
```bash
wget https://www.apple.com/certificateauthority/AppleWWDRCAG4.cer
openssl x509 -inform der -in AppleWWDRCAG4.cer -out AppleWWDRCAG4.pem
```

### Step 4: Find Your Team ID

- Open the downloaded `.cer` in Keychain Access (macOS)
- Look for **Organizational Unit** — that's your Team ID
- Or find it at [developer.apple.com/account](https://developer.apple.com/account) → Membership

### Step 5: Configure in Eventyay

Go to **Global Settings** and fill in:

| Field | Value |
|---|---|
| Passbook team ID | Your Team ID (e.g., `AGK5BZEN3E`) |
| Passbook Pass Type ID | Your identifier (e.g., `pass.com.yourorg.events`) |
| Passbook certificate file | Upload `$CERT_NAME.pem` |
| Passbook CA Certificate | Upload `AppleWWDRCAG4.pem` |
| Passbook secret key | Paste contents of `$CERT_NAME.key.pem` |
| Passbook key password | Only if your key has a passphrase |

---

## How to Test

### Prerequisites

```bash
cd app/

# Activate virtual environment
source .venv/bin/activate

# Install dependencies (if not already)
uv sync --all-extras --all-groups
uv pip install wallet-py3k --python .venv/bin/python

# Verify openssl is available
which openssl

# Verify wallet-py3k is installed
python -c "from wallet.models import Pass, Barcode, EventTicket; print('OK')"
```

### Test 1: Verify Plugin Loads

```bash
python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventyay.config.settings')
import django; django.setup()

from eventyay.plugins.passbook.passbook import PassbookOutput
print('Identifier:', PassbookOutput.identifier)
print('Verbose name:', PassbookOutput.verbose_name)
print('Plugin loaded successfully')
"
```

Expected output:
```
Identifier: passbook
Verbose name: Passbook Tickets
Plugin loaded successfully
```

### Test 2: Verify Signal Registration

```bash
python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventyay.config.settings')
import django; django.setup()

from eventyay.base.signals import register_ticket_outputs, register_global_settings

# Check ticket output registration
results = register_global_settings.send(None)
for receiver, response in results:
    if response and 'passbook_team_id' in response:
        print('Global settings registered:')
        for key in response.keys():
            print(f'  - {key}')
        break

print()
print('Signal registration: OK')
"
```

### Test 3: Verify Django System Check

```bash
python manage.py check
```

Expected: `System check identified no issues`

### Test 4: UI Integration Test (Manual)

1. Start the development server:
   ```bash
   python manage.py runserver
   ```

2. Log in to the admin panel

3. Navigate to any event → **Settings → Tickets**

4. Scroll to **Download formats** — you should see a **"Passbook Tickets"** panel with:
   - A checkbox to enable/disable
   - A "Preview" button (top-right)
   - Settings fields for images, colors, and location

5. Check the checkbox to enable passbook tickets, click **Save**

6. Verify the provider appears as enabled (no warning about "no output provider")

### Test 5: Generate a Test Passbook (with self-signed certs)

For local testing without a real Apple Developer account, generate self-signed certs:

```bash
# Generate a self-signed certificate (NOT valid for real Apple Wallet,
# but good enough to test the generation pipeline)

# 1. Generate key
openssl genrsa -out test-passbook.key 2048
openssl pkey -in test-passbook.key -traditional > test-passbook.key.pem

# 2. Generate self-signed certificate
openssl req -new -x509 -key test-passbook.key -out test-passbook.pem \
  -days 365 -subj "/CN=Pass Type ID: pass.test.eventyay/OU=TEST123"

# 3. Use the same cert as "WWDR" for testing
cp test-passbook.pem test-wwdr.pem
```

Then configure in global settings:
- Team ID: `TEST123`
- Pass Type ID: `pass.test.eventyay`
- Certificate file: Upload `test-passbook.pem`
- CA Certificate: Upload `test-wwdr.pem`
- Secret key: Paste contents of `test-passbook.key.pem`

**Note:** Self-signed passes will NOT open in Apple Wallet (iOS requires Apple-signed certs), but the `.pkpass` file will be generated and you can inspect its contents:

```bash
# After downloading, inspect the .pkpass file
unzip -l my-event-ABCDE.pkpass
unzip -p my-event-ABCDE.pkpass pass.json | python -m json.tool
```

### Test 6: Run Existing Tests

```bash
pytest tests/ -x -q
```

Ensure no regressions were introduced.

### Test 7: Verify Default Enabled for New Events

```python
python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventyay.config.settings')
import django; django.setup()

from eventyay.base.models import Event
# Check that set_defaults includes passbook
import inspect
source = inspect.getsource(Event.set_defaults)
assert 'ticketoutput_passbook__enabled' in source
print('Default enabled: OK')
"
```

---

## Troubleshooting

### "No output provider is enabled"

The warning appears on the Tickets settings page when downloads are turned on but no format is enabled.

**Fix:** Check the "Passbook Tickets" checkbox under Download formats and save.

### ".pkpass file won't open in Apple Wallet"

Possible causes:
1. **Self-signed certificates** — Apple Wallet requires passes signed with a real Apple-issued Pass Type certificate
2. **Wrong WWDR certificate** — Download the latest from Apple: `AppleWWDRCAG4.cer`
3. **Team ID / Pass Type ID mismatch** — These must match your Apple Developer account exactly
4. **Key password incorrect** — If your private key is encrypted, enter the password in settings

### "OpenSSL binary not found"

The plugin requires `openssl` to sign passes.

```bash
# macOS (usually pre-installed)
which openssl

# Ubuntu/Debian
sudo apt-get install openssl

# Check in Docker
docker exec <container> which openssl
```

### "wallet-py3k not installed"

```bash
uv pip install wallet-py3k --python .venv/bin/python
# or
pip install wallet-py3k
```

### "Could not convert image to PNG"

The uploaded image format is unsupported or corrupted. Ensure:
- Pillow is installed: `pip install pillow`
- The image is a valid PNG, JPEG, or GIF file
- File is not corrupted or zero-length

### Pass shows default eventyay branding

Upload custom icon and logo images in the per-event passbook settings. Recommended sizes:
- **Icon:** 87×87 pixels (PNG)
- **Logo:** 480×150 pixels (PNG)
- **Background:** 540×660 pixels (PNG, use dark images for text contrast)

---

## Extending the Plugin

### Adding New Fields to the Pass

Edit `passbook.py` → `generate_pass()`. Use the `wallet.models.EventTicket` API:

```python
card.addPrimaryField('key', 'value', 'Label')
card.addSecondaryField('key', 'value', 'Label')
card.addAuxiliaryField('key', 'value', 'Label')
card.addBackField('key', 'value', 'Label')
card.addHeaderField('key', 'value', 'Label')
```

### Adding New Configuration Options

1. Add the form field to `settings_form_fields` in `passbook.py`
2. If it's a file field, register a hierarkey default in `signals.py`
3. Use the setting value in `generate_pass()` via `self.event.settings.get('ticketoutput_passbook_yourfield')`

### Supporting Google Wallet

Google Wallet uses a completely different format (JWT-based, not `.pkpass`). This would require a separate output plugin. Create a new plugin following the same pattern:

1. Create `eventyay/plugins/googlewallet/`
2. Implement a `GoogleWalletOutput(BaseTicketOutput)` class
3. Register via `register_ticket_outputs` signal

### Pass Updates (Push Notifications)

The current implementation generates static passes. For dynamic pass updates (e.g., gate changes), you would need:

1. A web service endpoint implementing Apple's PassKit Web Service API
2. Push notification support via Apple's APNs
3. A registration model to track device-pass relationships

This is a significant extension and would require additional infrastructure.

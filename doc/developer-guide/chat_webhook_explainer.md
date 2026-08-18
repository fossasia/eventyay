# Chat Webhook Feature — Complete Explainer

## Step-by-Step Demo: From Zero to Working Webhook

This section walks you through the entire setup assuming you have a running Eventyay Docker setup (`docker compose up`). Nothing else is needed.

### What you'll end up with

```
Your browser                     Your terminal
┌────────────────┐               ┌────────────────────────────┐
│ Eventyay room  │               │ Webhook receiver           │
│ chat: "Hello!" │──────────────►│ [WEBHOOK RECEIVED]         │
│                │  (automatic)  │   screen_name: Arnav       │
│                │               │   message: Hello!          │
│                │               │   signature valid: YES     │
└────────────────┘               └────────────────────────────┘
```

Every message you type in the room chat instantly appears in your receiver terminal. That's it. That's the feature.

---

### Step 1: Start the webhook receiver (Terminal 1)

Open a terminal on your Mac (not inside Docker) and run:

```bash
cd ~/Desktop/eventyay
python tools/test_webhook_receiver.py
```

You'll see:
```
Webhook test receiver running on http://0.0.0.0:9999
HMAC secret: test-webhook-secret-12345
Waiting for webhook deliveries...
```

**What just happened?** You started a tiny HTTP server on port 9999. This pretends to be the external moderation tool. It can:
- Respond to challenge verification (`GET ?challenge=...`)
- Receive webhook POSTs and print them
- Verify HMAC signatures

**Leave this terminal open.** You'll watch webhook payloads appear here.

---

### Step 2: Create a room with chat enabled (Browser)

1. Go to `http://localhost:8000` → log in as admin
2. Navigate to your event's video/live area
3. Click **Manage** (top right) → you're now in admin mode
4. Create a new room (or use an existing one)
5. Add the **"Chat"** module to the room (click the chat icon in room settings)
6. Note the **Room ID** — you can see it in the URL: `http://localhost:8000/.../video/rooms/203` → Room ID is `203`

If you already have a room with chat (like your "New room" with ID 203), skip to Step 3.

---

### Step 3: Tell the room to send webhooks (Terminal 2)

Open a second terminal and run this command. Replace `203` with your actual room ID:

```bash
docker exec -it eventyay-next-web python -c "
import django, os, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventyay.config.settings')
django.setup()
from eventyay.base.models.room import Room

room = Room.objects.get(id=203)
for m in room.module_config:
    if m['type'] == 'chat.native':
        m['config']['webhook_url'] = 'http://host.docker.internal:9999/webhook'
        m['config']['webhook_hmac_secret'] = 'test-webhook-secret-12345'
        print('Webhook configured!')
        break
else:
    print('ERROR: This room has no chat.native module. Add chat to the room first.')
    exit(1)

room.module_config = room.module_config  # force dirty
room.save()
print('Saved. Room', room.id, 'will now push webhooks.')
"
```

You should see:
```
Webhook configured!
Saved. Room 203 will now push webhooks.
```

**What just happened?** You added two fields to the room's chat config:
- `webhook_url` — where to send messages (`host.docker.internal` = your Mac from inside Docker)
- `webhook_hmac_secret` — the shared secret for HMAC signing (must match the receiver)

**Why `host.docker.internal`?** Docker containers can't use `localhost` to reach your Mac. `host.docker.internal` is Docker's magic hostname that resolves to the host machine.

---

### Step 4: Restart containers to pick up the new code (Terminal 2)

```bash
docker restart eventyay-next-web eventyay-next-worker
```

Wait ~20 seconds for them to come back up. You can check:
```bash
docker logs eventyay-next-worker --tail 5
```

Look for: `celery@... ready.` That means the worker is up and has the `send_chat_webhook` task loaded.

---

### Step 5: Send a chat message (Browser)

1. Go to `http://localhost:8000/Arn/ehdqma/video/rooms/203` (your room)
2. Type something in the chat, e.g. "Hello webhook!"
3. Press Enter / click Send

---

### Step 6: Watch the webhook arrive (Terminal 1)

Switch to Terminal 1 (your webhook receiver). You'll see:

```
============================================================
[WEBHOOK RECEIVED]
  Signature valid: YES
  Signature:       sha256=a1b2c3d4e5f6...
  Payload:
{
    "message_id": 42,
    "channel": "550e8400-...",
    "timestamp": "2026-04-30T10:05:00.123456+00:00",
    "screen_name": "Arnav",
    "sender_id": "a1b2c3d4-...",
    "centralauth_id": null,
    "message": "Hello webhook!",
    "message_type": "text",
    "profile_img": null,
    "user_language": "en",
    "meta": {}
}
============================================================
```

**That's it! The webhook is working.**

Every message and emoji reaction in this room will now be pushed to your receiver in real-time.

---

### Step 7: Test emoji reactions (Browser)

React to any message with an emoji (click the emoji reactions below the video). Check Terminal 1 again — you'll see a second webhook with `"message_type": "emoji"`.

---

### Step 8: Verify signature checking works

Try changing the secret in the receiver (stop it, edit `HMAC_SECRET` in `tools/test_webhook_receiver.py`, restart it). Send another message. The receiver will show `Signature valid: NO` — proving the HMAC verification catches mismatches.

---

### How to disable webhooks

Remove the webhook config from the room:

```bash
docker exec -it eventyay-next-web python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventyay.config.settings')
django.setup()
from eventyay.base.models.room import Room

room = Room.objects.get(id=203)
for m in room.module_config:
    if m['type'] == 'chat.native':
        m['config'].pop('webhook_url', None)
        m['config'].pop('webhook_hmac_secret', None)
room.save()
print('Webhooks disabled for room', room.id)
"
```

---

### Quick reference: What's running where

```
┌─────────────────────────────────────────────────────────┐
│ YOUR MAC (host machine)                                  │
│                                                          │
│  Terminal 1: python tools/test_webhook_receiver.py       │
│              (listens on port 9999, prints webhooks)     │
│                                                          │
│  Browser: http://localhost:8000/.../video/rooms/203      │
│           (you type chat messages here)                  │
│                                                          │
├─────────────────────────────────────────────────────────┤
│ DOCKER (containers)                                      │
│                                                          │
│  eventyay-next-web:                                      │
│    - Runs Django + WebSocket server                      │
│    - When you send a chat message, ChatModule.send()     │
│      queues a Celery task                                │
│                                                          │
│  eventyay-next-worker:                                   │
│    - Runs Celery worker                                  │
│    - Picks up send_chat_webhook task                     │
│    - Makes HTTP POST to host.docker.internal:9999        │
│                                                          │
│  eventyay-next-redis:                                    │
│    - Message broker between web and worker               │
│                                                          │
│  eventyay-next-db:                                       │
│    - PostgreSQL, stores room config with webhook URL     │
└─────────────────────────────────────────────────────────┘
```

---

### What the challenge verification is (and when it runs)

When you set a webhook URL via the **WebSocket config.patch command** (the organizer UI), Eventyay does a challenge check before saving:

```
1. You set webhook_url = "http://host.docker.internal:9999/webhook"

2. Eventyay immediately sends:
   GET http://host.docker.internal:9999/webhook?challenge=aB3xK9mP2qR7sT4uV...

3. Your receiver must respond:
   200 OK
   {"challenge": "aB3xK9mP2qR7sT4uV..."}  ← same token echoed back

4. If it matches → config saved
   If it doesn't → error "webhook.verification_failed"
```

**Note:** When you configure via `python -c` (Django shell) like in Step 3 above, the challenge is **skipped** because you're writing directly to the database. The challenge only runs through the WebSocket API. For production use via the organizer UI, the challenge ensures the URL owner has opted in.

---

## Understanding HMAC (The "How do I know this is really from Eventyay?" part)

### The problem

Anyone could send a POST request to your receiver pretending to be Eventyay. How does your receiver know the message is legit?

### The solution: shared secret + signature

Both Eventyay and your receiver know a secret password (the `webhook_hmac_secret`). Eventyay uses it to create a signature. Your receiver uses the same secret to verify the signature.

```
Eventyay:
    message = '{"message":"Hello"}'
    secret  = "test-webhook-secret-12345"
    signature = SHA256(message + secret) = "a1b2c3..."
    → sends message + "X-Eventyay-Signature: sha256=a1b2c3..."

Your receiver:
    receives message + signature header
    recomputes SHA256(received_message + same_secret) = "a1b2c3..."
    compares: "a1b2c3..." == "a1b2c3..." ✓ MATCH → it's really from Eventyay

Attacker:
    sends fake message + guessed signature
    receiver recomputes SHA256(fake_message + secret) = "x7y8z9..."
    compares: "x7y8z9..." != attacker's signature ✗ REJECTED
```

### Why it's secure

- The secret **never travels over the network** — both sides already have it
- Even if an attacker sees the signature, they can't forge a new one without the secret
- Uses `hmac.compare_digest()` which is timing-attack resistant (takes the same time whether the signature is right or wrong)

---

## What Are Webhooks?

A **webhook** is a way for one application to send real-time data to another application when something happens. Instead of the second app constantly asking "did anything happen yet?" (polling), the first app *pushes* the data the moment an event occurs.

**Real-world analogy:** Instead of checking your mailbox every 5 minutes, the postman rings your doorbell when a package arrives.

### How webhooks work in general

```
┌──────────┐    event happens    ┌──────────────┐
│ Eventyay │ ──── HTTP POST ───► │ External App │
│ (sender) │                     │  (receiver)  │
└──────────┘                     └──────────────┘
```

1. An event happens (e.g., someone sends a chat message)
2. Eventyay makes an HTTP POST request to a pre-configured URL
3. The external app receives the data and does something with it

### Webhooks in Django

Django doesn't have built-in webhook support — it's just HTTP. Eventyay uses:

- **Django Channels** — handles real-time WebSocket connections for the live chat
- **Celery** — a background task queue that sends the webhook HTTP request asynchronously so it doesn't slow down the chat
- **Redis** — the message broker that connects Django to Celery

When a chat message is sent:
```
User types message
    │
    ▼
Django Channels WebSocket consumer (ChatModule.send)
    │
    ├──► Broadcast to all connected users (existing behavior)
    │
    └──► Queue a Celery task (NEW: send_chat_webhook)
              │
              ▼
         Celery worker picks up the task
              │
              ▼
         HTTP POST to external URL with the message data
```

---

## What This Feature Does

This feature adds **optional per-room webhook configuration** to Eventyay's live chat system. When configured, every chat message and emoji reaction in a room is also sent as an HTTP POST to an external URL.

### Use case

The original request was from the Wikimania team building **chatstream-moderate** — an external moderation tool that:
1. Receives chat messages from Eventyay in real-time
2. Holds them in a moderation queue
3. Displays approved messages on a conference AV overlay screen

### What gets sent

Every `channel.message` and emoji reaction triggers a webhook POST with this payload:

```json
{
    "message_id": 12345,
    "channel": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2026-04-30T10:00:00.000000+00:00",
    "screen_name": "Arnav",
    "sender_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "centralauth_id": "WikimediaUsername",
    "message": "Hello everyone!",
    "message_type": "text",
    "profile_img": null,
    "user_language": "en",
    "meta": {}
}
```

For emoji reactions, `message_type` is `"emoji"` and `meta` contains:
```json
{
    "meta": {
        "target_message_id": 12345
    }
}
```

### Field reference

| Field | Type | Description |
|-------|------|-------------|
| `message_id` | integer | Monotonic event ID from Redis (unique per Eventyay instance) |
| `channel` | UUID string | The chat channel identifier |
| `timestamp` | ISO 8601 | When the message was created |
| `screen_name` | string | The sender's display name from their profile |
| `sender_id` | UUID string | Eventyay internal user ID |
| `centralauth_id` | string or null | Wikimedia username (if set) |
| `message` | string | The message body text |
| `message_type` | `"text"` or `"emoji"` | Type of event |
| `profile_img` | URL or null | User's avatar (currently null, extensible) |
| `user_language` | BCP 47 string | User's locale preference (e.g., `"en"`, `"fr"`) |
| `meta` | object | Extra data — for reactions: `{"target_message_id": ...}` |

---

## Security: HMAC-SHA256 Authentication

### What is HMAC?

**HMAC** (Hash-based Message Authentication Code) is a way to verify that:
1. The message really came from Eventyay (authenticity)
2. The message wasn't tampered with in transit (integrity)

It works using a **shared secret** — a password that both Eventyay and the receiver know.

### How it works

```
Eventyay side:
    payload = '{"message":"Hello",...}'
    secret  = "my-shared-secret"
    signature = HMAC-SHA256(payload, secret)
    → sends: POST with header X-Eventyay-Signature: sha256=<hex>

Receiver side:
    receives payload + signature header
    recomputes: HMAC-SHA256(received_payload, same_secret)
    compares with received signature
    → if they match, the message is authentic
```

### Why this pattern?

This is the same pattern used by GitHub webhooks, Stripe webhooks, and Slack webhooks. It's industry standard because:

- **No tokens in URLs** — the secret never travels over the wire
- **Per-request verification** — every single request is independently verified
- **Timing-attack resistant** — uses `hmac.compare_digest()` for constant-time comparison
- **Replay protection** — the `timestamp` field lets receivers reject old requests

### The signature header

Every webhook POST includes:
```
X-Eventyay-Signature: sha256=511cd8f42f1fd47fb30624ba4b12a023a804e5fbfe90adddf55c704f3dbba52e
```

The receiver verifies it like this (Python):
```python
import hmac
import hashlib

received_body = request.get_data()  # raw bytes
received_sig = request.headers["X-Eventyay-Signature"].removeprefix("sha256=")

expected_sig = hmac.new(
    b"my-shared-secret",  # your secret
    received_body,
    hashlib.sha256
).hexdigest()

if hmac.compare_digest(expected_sig, received_sig):
    print("Valid!")
else:
    print("REJECTED — signature mismatch")
```

---

## Challenge Verification

### What is it?

When you register a webhook URL, Eventyay first verifies that the URL actually belongs to you and is ready to receive webhooks. This prevents the webhook system from being abused to send requests to arbitrary URLs (SSRF protection).

### How it works

```
1. Organizer sets webhook_url = "https://example.com/webhook"

2. Eventyay sends:
   GET https://example.com/webhook?challenge=aB3xK9mP2qR7...

3. The receiver must respond with:
   {"challenge": "aB3xK9mP2qR7..."}   (echo the token back)

4. If the response matches → webhook is activated
   If it doesn't match → configuration is rejected
```

### Why?

Without this, an attacker with organizer access could point the webhook at any URL and use Eventyay as a request amplifier. The challenge proves the URL owner has opted in.

---

## How to Configure Webhooks on an Event

### Architecture overview

```
┌─────────────────────────────────────────────────┐
│                    Eventyay                       │
│                                                   │
│  ┌──────────┐    ┌──────────┐    ┌─────────────┐ │
│  │  Django   │    │  Celery  │    │   Redis     │ │
│  │ Channels  │───►│  Worker  │◄──►│   Broker    │ │
│  │(WebSocket)│    │          │    │             │ │
│  └──────────┘    └────┬─────┘    └─────────────┘ │
│                       │                           │
└───────────────────────┼───────────────────────────┘
                        │ HTTP POST
                        ▼
              ┌──────────────────┐
              │  Your Receiver   │
              │  (external app)  │
              └──────────────────┘
```

### Step 1: Set up your receiver

Your receiver is any HTTP server that can handle GET (challenge) and POST (webhooks). Minimal example:

```python
# receiver.py
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, hmac, hashlib

SECRET = "your-shared-secret"

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Challenge verification
        from urllib.parse import parse_qs, urlparse
        challenge = parse_qs(urlparse(self.path).query).get("challenge", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"challenge": challenge}).encode())

    def do_POST(self):
        # Webhook delivery
        body = self.rfile.read(int(self.headers["Content-Length"]))

        # Verify signature
        sig = self.headers.get("X-Eventyay-Signature", "").removeprefix("sha256=")
        expected = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
        valid = hmac.compare_digest(expected, sig)

        payload = json.loads(body)
        print(f"Message from {payload['screen_name']}: {payload['message']}")
        print(f"Signature valid: {valid}")

        self.send_response(200)
        self.end_headers()

HTTPServer(("0.0.0.0", 9999), Handler).serve_forever()
```

Run it: `python receiver.py`

### Step 2: Configure the room

The webhook config lives inside the room's `module_config` JSON field, under the `chat.native` module. Currently this is configured via:

**Option A: Django shell (direct DB update)**
```bash
docker exec -it eventyay-next-web python -c "
import django, os, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventyay.config.settings')
django.setup()
from eventyay.base.models.room import Room

room = Room.objects.get(id=YOUR_ROOM_ID)
for m in room.module_config:
    if m['type'] == 'chat.native':
        m['config']['webhook_url'] = 'https://your-receiver.example.com/webhook'
        m['config']['webhook_hmac_secret'] = 'your-shared-secret'
room.save()
print('Done!')
"
```

**Option B: WebSocket command (organizer UI)**
```json
["room.config.patch", 1, {
    "room": "<room-id>",
    "module_config": [
        {
            "type": "chat.native",
            "config": {
                "volatile": false,
                "webhook_url": "https://your-receiver.example.com/webhook",
                "webhook_hmac_secret": "your-shared-secret"
            }
        }
    ]
}]
```

When sent via WebSocket, Eventyay will:
1. Validate the URL (HTTPS required in production, HTTP allowed in DEBUG mode)
2. Send a challenge verification GET request
3. Only save the config if the challenge passes

### Step 3: Restart services

After configuring, restart the web and worker containers so they pick up the config:
```bash
docker restart eventyay-next-web eventyay-next-worker
```

### Step 4: Send a chat message

Go to the room in the Eventyay video UI, type a message, and your receiver will get an HTTP POST with the payload.

---

## Local Development Setup (Docker)

For local testing, the receiver runs on your host machine and the Docker containers reach it via `host.docker.internal`:

```
┌─────────────────────────┐     ┌──────────────────────┐
│   Docker containers      │     │   Your Mac (host)    │
│                          │     │                      │
│  web ──► worker ─────────┼────►│ test_webhook_receiver│
│          (Celery POST    │     │ (port 9999)          │
│           to host.docker │     │                      │
│           .internal:9999)│     │                      │
└─────────────────────────┘     └──────────────────────┘
```

### Quick start

```bash
# Terminal 1: Start the test receiver
python tools/test_webhook_receiver.py

# Terminal 2: Configure the room (one-time)
docker exec -it eventyay-next-web python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventyay.config.settings')
django.setup()
from eventyay.base.models.room import Room
room = Room.objects.get(id=203)  # your room ID
for m in room.module_config:
    if m['type'] == 'chat.native':
        m['config']['webhook_url'] = 'http://host.docker.internal:9999/webhook'
        m['config']['webhook_hmac_secret'] = 'test-webhook-secret-12345'
room.save()
print('Configured!')
"

# Terminal 3: Restart containers
docker restart eventyay-next-web eventyay-next-worker

# Now open the room in browser and send a chat message
# Watch Terminal 1 for the webhook payload
```

---

## Files Changed (Implementation Reference)

| File | What it does |
|------|-------------|
| `app/eventyay/features/live/tasks.py` | New Celery task `send_chat_webhook` — serializes payload, computes HMAC, POSTs to URL |
| `app/eventyay/features/live/modules/chat.py` | Added `_dispatch_chat_webhook()` helper; calls it after every `group_send` in `send()` and `react()` |
| `app/eventyay/features/live/modules/room.py` | Added `_verify_webhook_challenges()` for challenge verification on config save |
| `tools/test_webhook_receiver.py` | Standalone test receiver for local development |

### No database migration needed

The webhook config is stored inside the existing `module_config` JSONField on the Room model. No schema change required.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| No webhook received | Celery worker not restarted | `docker restart eventyay-next-worker` |
| No webhook received | Web container running old code | `docker restart eventyay-next-web` |
| `webhook.insecure_url` error | Using HTTP in production | Use HTTPS URL, or set `EVY_DEBUG=1` for local dev |
| `webhook.verification_failed` | Receiver not responding to challenge | Ensure receiver handles `GET ?challenge=...` |
| `webhook.missing_secret` | No HMAC secret configured | Add `webhook_hmac_secret` to the chat.native config |
| Signature mismatch at receiver | Wrong secret | Ensure both sides use the exact same secret string |
| Worker log: "failed after Xs" | Receiver unreachable from Docker | Use `host.docker.internal` instead of `localhost` |
| 404 errors in browser console | Unrelated — ticketing API issue | Not caused by this feature; pre-existing |

---

## Future Extensions

The same webhook mechanism can be extended to:
- **Q&A events** (`question.py` module) — ask, pin, unpin events with `message_type: "qa"`
- **Poll events** — poll creation, votes, results
- **Retry support** — set `max_retries > 0` on the Celery task for guaranteed delivery
- **Admin UI** — add webhook URL/secret fields to the room configuration form in the organizer dashboard

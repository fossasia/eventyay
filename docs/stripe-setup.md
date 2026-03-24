# Stripe Integration Setup Guide

This guide explains how to configure **Stripe Webhooks** and **Stripe OAuth onboarding** in Eventyay.

---

## 1. Stripe Webhook Setup

### Step 1: Create Webhook in Stripe

1. Go to the Stripe Dashboard: https://dashboard.stripe.com/
2. Navigate to **Developers → Webhooks**
3. Click **"Add endpoint"**

---

### Step 2: Enter Endpoint URL

Use your Eventyay backend endpoint:

```
https://your-domain.com/api/v1/stripe/webhook
```

For local development:

```
http://localhost:5000/api/v1/stripe/webhook
```
Note: In local development, port 5000 refers to the backend API server used by Eventyay.

---

### Step 3: Select Events

Enable the following events:

- `checkout.session.completed`
- `payment_intent.succeeded`
- `payment_intent.payment_failed`
- `charge.refunded`

---

### Step 4: Get Signing Secret

1. After creating the webhook, click on it
2. Copy the **Signing Secret**

Example:

```
whsec_XXXXXXXXXXXXXXXX
```

---

### Step 5: Add Webhook Secret in Eventyay

Go to:

**Admin → Settings → Payment**

Add:

- Stripe Webhook Secret = `whsec_XXXXXXXX`

---

## 2. Stripe OAuth Setup

### Step 1: Enable Stripe Connect (OAuth)

1. Go to Stripe Dashboard
2. Navigate to **Settings → Connect Settings**
3. Enable OAuth for:
   - Standard Accounts
   - Express Accounts

---

### Step 2: Get Client Credentials

From Stripe:

- Client ID → `ca_XXXXXXXX`
- Secret Key → `sk_test_XXXXXXXX` or `sk_live_XXXXXXXX`

You can find these under:

**Developers → API Keys**

---

### Step 3: Configure Redirect URIs

Add the following redirect URIs in Stripe:

```
https://your-domain.com/_stripe/oauth_return/   
```
Note: Replace `your-domain.com` with your actual backend/API domain.

```
http://localhost:3000/_stripe/oauth_return/
```
Note: Port 3000 refers to the frontend application where users are redirected after completing Stripe onboarding.

---

### Step 4: Add Credentials in Eventyay

Go to:

**Admin → Settings → Payment**

Add:

- Stripe Client ID
- Stripe Secret Key

---

## 3. Required Redirect URIs

Stripe requires all possible redirect URIs to be registered.

Make sure the following are added:

- `https://your-domain.com/_stripe/oauth_return/`
- `http://localhost:3000/_stripe/oauth_return/`

These are used after successful Stripe onboarding.

---

## 4. Expected Flow

1. Organizer clicks **"Connect Stripe"**
2. User is redirected to Stripe OAuth page
3. User completes onboarding
4. Stripe redirects back to:

```
/_stripe/oauth_return/
```

5. Eventyay stores the Stripe account connection

---

## 5. Common Issues

| Issue | Solution |
|------|---------|
| Webhook not working | Verify signing secret |
| OAuth fails | Check redirect URIs |
| Payments not updating | Ensure required events are enabled |

---

## Notes

- Always use correct webhook events
- Ensure redirect URIs exactly match
- Signing secret must match Stripe webhook configuration


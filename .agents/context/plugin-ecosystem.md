# Core, Business, and Stripe: repository boundaries

Read this for changes spanning ticket checkout, organizer billing, commercial
entitlements, plugin loading, or deployment. Paths below are relative to this
repository unless a different repository is named. Verify against the branch you
are changing; this is a navigation guide, not a replacement for code.

## Ownership

| Repository | Owns | Start here |
|---|---|---|
| [Eventyay](https://github.com/fossasia/eventyay) | Django runtime, organizers/events, orders/payments/refunds, billing identity, shared extension contracts | `app/eventyay/base/`, `app/eventyay/api/`, `app/eventyay/config/` |
| [Business](https://github.com/fossasia/eventyay-business) | Tier versions, subscriptions, add-ons, entitlement policy, platform fee ledger, consolidated invoices and collection | `eventyay_business/models.py`, `signals.py`, `services.py`, `invoicing_service.py`, `invoice_collection.py` |
| [Stripe](https://github.com/fossasia/eventyay-stripe) | Attendee payment providers, Connect, PaymentIntents, SCA, payment webhooks and refunds | `eventyay_stripe/payment.py`, `views.py`, `signals.py`, `urls.py` |

These are independent Git repositories. A development checkout can place Business
and Stripe side by side under `plugins/`; neither is nested inside the other.
Use `git -C <path> rev-parse --show-toplevel` before staging. Core's plugin directory
is a development mount, not the source of plugin commits.

## Installation and discovery

- `app/pyproject.toml` declares Business and Stripe dependencies and Git sources;
  `app/uv.lock` resolves them to commits. A plugin merge does not update that lock.
- `app/eventyay/config/settings.py` discovers modules through `pretix.plugin`
  metadata and adds ticket plugins to `INSTALLED_APPS`, subject to exclusions.
  This entry-point name remains a compatibility contract, despite new Python
  imports using `eventyay.*`.
- `app/eventyay/base/plugins.py`, `app/eventyay/helpers/plugin_enable.py`, and
  `app/eventyay/multidomain/plugin_handler.py` govern plugin metadata, enablement,
  and routing. Installation and event enablement are separate concerns.
- Business's app metadata is hidden/restricted; do not assume every installed
  plugin appears as a normal event checkbox. Stripe registers payment providers.
- `app/eventyay/config/urls.py` also supplies Stripe webhook compatibility paths.
  Preserve public aliases when changing plugin URL registration.

## Extension contracts

`app/eventyay/base/entitlements.py` exposes `check_entitlement`, `record_usage`,
and `get_capability_registry`. Signals live in `app/eventyay/base/signals.py`.
With no receiver, entitlement checks allow access; any denying receiver wins.
Usage reports require a stable idempotency key. Business supplies policy and
usage persistence; core callers should use the shared API instead of importing
Business models.

`app/eventyay/base/platform_fees.py` defines `PlatformFeePolicy` and its resolver.
No provider returns a zero policy; multiple providers raise a specific error.
Business resolves country/currency overrides, then tier fee entitlements, then
zero. This contract does not itself charge a payment.

`OrganizerBillingModel` in `app/eventyay/base/models/organizer.py` owns the
organizer's Stripe customer and saved payment references. Core's
`app/eventyay/helpers/stripe_utils.py` and `app/eventyay/api/views/stripe.py` handle
billing integration. Business reuses that identity rather than creating another
customer. The `legacy_billing_collection_disabled` and
`organizer_billing_payment_method_saved` signals coordinate collection ownership.

## End-to-end behavior

1. Attendee checkout creates core orders and payments; a Stripe provider creates
   a PaymentIntent and stores external references. Signed Stripe notifications
   and return/SCA handling update the core payment lifecycle.
2. Business listens for paid/canceled orders and refund updates, records fee
   ledger entries, and accounts for historical checkout application fees.
3. Business's invoicing service combines billable sources into organizer invoices;
   its collection service uses the core billing identity and Business collection
   authorization. PaymentIntent notifications update collection state.
4. Business retains legacy subscription/add-on Checkout handling around the
   consolidated billing cutover. Inspect `billing_migration.py`,
   `platform_fee_ledger.py`, and `stripe_service.py` in Business before changing
   that boundary.

The current Stripe plugin's `_prepare_api_connect_args` adds destination transfer
data when configured, not a new application fee. Refunds still inspect stored
`application_fee_amount` for older payments. Do not infer current fee collection
from old settings, README language, or refund compatibility code.

There are separate webhook consumers: attendee payments in Stripe, organizer
billing in core, and Business billing at `/control/business/stripe/webhook/`.
Trace the actual URL and object type before changing a handler. Core's Stripe
helper currently reads one global `stripe_webhook_secret_key`; do not assume
independent per-endpoint signing-secret settings exist.

## Tests and maintenance

Core contract tests include `app/tests/base/test_entitlements.py`,
`app/tests/base/test_platform_fees.py`,
`app/tests/base/test_legacy_billing_collection.py`, and
`app/tests/tickets/api/test_stripe_webhook_routes.py`. Plugin tests belong in their
own repositories. Run both producer and consumer tests for contract changes.

For each cross-repository PR, state the owner of the changed behavior, tested
core/plugin revisions, compatibility with absent plugins, and any deployment
ordering. Keep each change reviewable independently. Update this map when an
ownership boundary or contract changes.

## Design history

The parent [Eventyay epic #5890](https://github.com/fossasia/eventyay/issues/5890)
tracks the architecture and rollout. Its directly linked implementation PRs were
merged when reviewed on 2026-10-28; the epic remains open for deployment validation
and controlled organizer activation. Early checkout-splitting proposals were
superseded by [Stripe #55](https://github.com/fossasia/eventyay-stripe/pull/55).
Historical fee refund support remains intentional. Current activation additionally
requires the reconciliation gate from
[Business #130](https://github.com/fossasia/eventyay-business/pull/130).
Do not infer live deployment readiness from merged PRs or historical test counts.

# Contract review prompts

- Entitlements: no plugin, explicit denial, event/organizer scope, and repeat
  usage with the same idempotency key.
- Fees: zero policy, country/currency override, tier fallback, historical fee
  already collected, refunds/cancellation, and cutover date.
- Payments: identify which webhook consumer owns the object; check signature,
  account/mode, duplicate notifications, and persisted state transitions.
- Deployment: prove which plugin revision is installed; compare editable local
  paths with `app/uv.lock`. Avoid direct core imports of optional plugin models.

Select tests relevant to the change; these prompts do not authorize real charges
or production configuration changes.

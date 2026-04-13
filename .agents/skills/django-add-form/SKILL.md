---
name: django-add-form
description: Steps for creating or modifying Django forms and adding validation
---

## When to use

Use this skill when building or editing forms handling user input for views like back-office organizers (`control/`) or attendee-facing routes (`presale/`).

## Steps

1. Place the new form class strictly alongside its relevant sub-app (e.g., `app/eventyay/base/forms/`, `app/eventyay/control/forms/`).
2. Add specific, individual field-level validation by implementing `clean_<field>()` methods.
3. Add multi-field or cross-field validation logic by implementing generic `clean()` method overrides.

## Validation

1. Confirm the form has definitively been organized within its intended domain scope (e.g. keeping control constraints strictly out of presale domains).

## Gotchas

- Do not bypass Django's built-in validation mechanisms logic when working with forms.
- Do not mix `control/forms/` configurations into `presale/` logic.

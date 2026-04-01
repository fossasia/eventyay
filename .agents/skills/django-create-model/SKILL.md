---
name: django-create-model
description: Steps for creating or modifying a Django model
---

## When to use

Use this skill when defining a new database model or modifying an existing one.

## Steps

1. Locate the correct sub-app for the model (e.g., `app/eventyay/base/models/` for shared models or a specific sub-app's `models.py`).
2. Define the model class. Ensure it inherits from a base class located in `app/eventyay/base/` if applicable.
3. Define the related model managers.

## Validation

1. Verify the model file is placed correctly inside the sub-app's directory hierarchy.
2. Confirm the model isn't mistakenly placed in a standalone top-level directory.

## Gotchas

- Cross-check standard rules (`agents.md`) when writing model queries, especially regarding event multi-tenancy (`django_scopes.scope(event=event)`).

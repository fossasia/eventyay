---
name: django-run-locally
description: Steps for initiating the Django development server without Docker
---

## When to use

Use this skill to spin up or invoke the local development backend sequence for rapid testing processes.

## Steps

1. Navigate securely into the active architecture directory: `cd app`
2. Synchronously install or update environment dependencies strictly through `uv`: `uv sync --all-extras --all-groups`
3. Activate the standard CLI venv wrapper: `. .venv/bin/activate`
4. Deploy local DB schema synchronization calls: `python manage.py migrate`
5. *(Optional)* Setup initial admin: `python manage.py create_admin_user`
6. Build Frontend Assets:
   ```bash
   make npminstall
   python manage.py collectstatic --noinput
   python manage.py compress --force
   ```
7. Initialize the development environment natively: `python manage.py runserver`

## Validation

1. Verify server startup output bindings properly format against standard generic ports (ex. `127.0.0.1:8000`).
2. There should be **no pending/unapplied migration warnings** displayed.
3. Verify `http://127.0.0.1:8000` loads properly without missing CSS/MIME type errors.

## Gotchas

- **Strict Environment Imports**: If context dynamically requires variable settings locally, ALWAYS safely fetch these utilizing `from django.conf import settings`. Never import the isolated system settings configuration natively (e.g. absolutely never execute `from eventyay.config import settings`).
- **CSS not loading / MIME type errors**: Ensure you have successfully run `collectstatic` and `compress --force` steps to properly build the Javascript/CSS chunks.

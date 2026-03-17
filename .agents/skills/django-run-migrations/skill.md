---
name: django-run-migrations
description: Steps for generating and applying Django migrations
---

## When to use

Use this skill continuously after modifying any `models.py` schema logic to apply the changes to the database.

## Steps

1. Navigate to the app context: `cd app/`
2. Generate the required migration definitions by running: `python manage.py makemigrations`
3. Execute and apply the generated migration file to the DB safely: `python manage.py migrate`

## Validation

1. Verify that the terminal explicitly outputs "Applying..." states and succeeds without tracebacks.
2. Quickly review the auto-generated `.py` migration output to ensure logical alignment with your model edits.

## Gotchas

- **Do not manually edit auto-generated migration files** unless executing an explicitly necessary, advanced requirement (i.e. complex data backfill operations).

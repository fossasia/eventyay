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

- **Do not manually edit auto-generated migration files** unless executing an explicitly necessary, advanced requirement (i.e. complex data backfill operations). Never rewrite migrations that have already been applied to a shared or production database; instead, create a new migration for any additional schema changes.

## Tips
If your changes in Django models don't cause a change in the actual database schema, you don't need to create a migration at all. 

Typical changes that do **not** affect the DB schema include:
- `choices`
- `verbose_name`
- `help_text`

In these cases:
- Do not run `makemigrations` just to capture these metadata-only changes.
- Do not edit existing migration files that may already have been applied. The only safe exception is in a narrowly scoped, pre-merge situation where a migration has never been applied to any shared or production database and you are cleaning up that pending migration before it lands. Otherwise, always create a new migration to capture real schema changes.

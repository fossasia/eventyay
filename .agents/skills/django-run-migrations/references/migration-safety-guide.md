# Migration Safety Guide

## Creation

- Generate migrations from `app/` using `python manage.py makemigrations`.
- Review generated operations before applying.

## Application

- Apply with `python manage.py migrate`.
- Watch for irreversible or destructive operations.

## Safety Rules

- Do not rewrite already-applied shared migrations.
- Prefer additive migrations for follow-up changes.
- Keep data migrations explicit and testable.

## Validation

- Run targeted tests for impacted models and queries.
- Confirm no pending migrations remain after changes.

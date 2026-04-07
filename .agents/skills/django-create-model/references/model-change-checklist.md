# Model Change Checklist

## Location

- Model is placed in the correct domain app (`models.py` or `models/`).

## Schema Design

- Field defaults, nullability, and indexes are intentional.
- Relationships use clear `related_name` values.

## Query Behavior

- Event-owned lookups are scoped with `django_scopes.scope(event=event)`.
- Common read paths consider `select_related`/`prefetch_related`.

## Migration Readiness

- Migration generation is clean and minimal.
- Potential data migration impact is documented when needed.

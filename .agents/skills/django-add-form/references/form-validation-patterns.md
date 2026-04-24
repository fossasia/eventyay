# Form Validation Patterns

## Field-level Validation

- Use `clean_<fieldname>()` for single-field validation.
- Raise `ValidationError` with clear, user-facing messages.

## Cross-field Validation

- Use `clean()` for interdependent constraints.
- Call `super().clean()` first and work with `cleaned_data`.

## Placement and Ownership

- Keep forms in the owning domain app.
- Avoid mixing organizer (`control`) and attendee (`presale`) concerns.

## Review Checks

- Validation runs for both happy-path and failure cases.
- Errors are deterministic and actionable.

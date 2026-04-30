---
applyTo: "app/eventyay/**/jinja-templates/**/*.jinja"
---

# Jinja Template Instructions

## Formatting

- Prefer single quotes in template markup and expressions.
- Use different quote styles when nesting quotes inside expressions.
- Use 2-space indentation.

## Template logic

- Keep templates focused on presentation. Move non-trivial business logic to Python views/forms/helpers.
- Avoid complex conditional chains inside HTML attributes. Compute values before rendering when possible.

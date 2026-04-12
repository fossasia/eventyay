---
name: frontend-ui
description: Frontend UI implementation, accessibility, and responsive checks for Django templates and Vue components
---

# Skill: Frontend UI

## When to Use

Use this skill when implementing or modifying UI behavior in:

- `app/eventyay/static/` assets
- `app/eventyay/webapp/` Vue applications
- Django templates under `app/eventyay/**/templates/`

## Core Workflow

1. Identify whether the change belongs to legacy static assets or a Vue app.
2. Keep behavior in external scripts (no inline JS; no jQuery).
3. Ensure responsive behavior across common mobile and desktop widths.
4. Validate accessibility basics: labels, keyboard navigation, focus visibility, and semantic landmarks.
5. Add or update tests when UI behavior changes are user-visible.

## Guardrails

- Follow `.github/instructions/js.instructions.md` for JS/Vue conventions.
- Follow `.github/instructions/django-template.instructions.md` for template conventions.
- Preserve existing design language unless the task explicitly requests a redesign.

## Supporting Artifacts

- Implementation references: `references/`
- Reusable templates/checklists: `assets/`
- Example validation scenarios: `tests/`

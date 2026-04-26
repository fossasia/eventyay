# Eventyay AI Agent Instructions (Single Source of Truth)

This is the canonical instruction file for all coding agents in this repository.

Supported agents include GitHub Copilot, Claude, Codex, Cursor, ChatGPT, and similar tools.

## Precedence

1. `agents.md` is the default policy for all agents (single source of truth).
2. `.github/instructions/*.md` rules are mandatory when their `applyTo` pattern matches the edited file.
3. `.agents/skills/` contains reusable operational knowledge about the repository structure and deployment.
4. Agent adapter files (`CLAUDE.md`, `CODEX.md`, `.cursorrules`, `.github/copilot-instructions.md`) should stay minimal and must not duplicate or override project rules.

## Verified Project Facts

- Runtime baseline is Python 3.12 (`app/pyproject.toml`).
- Core stack: Django 5.2+, PostgreSQL, Redis, Celery, Channels, Vue 3.
- Primary development paths:
  - `app/eventyay/` for product code
  - `app/tests/` for tests
  - `doc/` for documentation
- Legacy product names (`pretix`, `pretalx`, `venueless`) are historical references only.
- If top-level legacy directories such as `talk/`, `video/`, or `src/` appear in a branch, treat them as reference-only unless explicitly requested.

## Non-Negotiable Architecture Rules

1. Multi-tenancy: event-owned ORM queries must be wrapped with `django_scopes.scope(event=event)`.
2. Imports: keep imports at file top; only use local imports for circular-import resolution.
3. Errors: preserve specific exception types; do not replace with generic `Exception`.
4. JavaScript: no jQuery and no inline scripts; use external ES modules.
5. Namespaces: use `eventyay.*` imports for new code; do not introduce new `pretix.*`, `pretalx.*`, or `venueless.*` imports.
6. ORM efficiency: prefer `select_related` and `prefetch_related` to avoid N+1 queries.

## File-Scoped Standards

Always apply the matching scoped rule file before editing:

- Python: `.github/instructions/python.instructions.md`
- JavaScript: `.github/instructions/js.instructions.md`
- Django templates: `.github/instructions/django-template.instructions.md`
- TOML: `.github/instructions/toml.instructions.md`
- Git commits: `.github/instructions/git-commit.instructions.md`

## Verified Commands

Run from `app/` unless noted:

- Install deps: `uv sync --all-extras --all-groups`
- Activate venv: `. .venv/bin/activate`
- Migrate DB: `python manage.py migrate`
- Run dev server: `python manage.py runserver`
- Run Celery worker: `celery -A eventyay worker -l info`
- Build assets (dev): `make staticfiles`
- Build assets (prod): `make production`
- Test suite: `pytest tests/`

## Agent Checklist

Before submitting changes:

1. Confirm edited files are in the intended path (`app/eventyay/`, `app/tests/`, or explicitly requested paths).
2. Confirm imports and namespaces follow `eventyay.*` conventions.
3. Confirm event data queries are scoped with `scope(event=event)` where required.
4. Confirm error handling keeps specific exception types.

## Context Index (`.agents/context/`)

| Context file | Purpose |
|---|---|
| `.agents/context/architecture.md` | Context: Architecture and project structure |

## Skills Index (`.agents/skills/`)

| Skill directory/file | Purpose |
|---|---|
| `.agents/skills/repo-navigation/SKILL.md` | Repository layout and where to find code |
| `.agents/skills/django-create-model/SKILL.md` | Steps for creating or modifying a Django model |
| `.agents/skills/django-create-api-endpoint/SKILL.md` | Steps for adding a new Django REST Framework API endpoint |
| `.agents/skills/django-add-form/SKILL.md` | Steps for creating or modifying Django forms and adding validation |
| `.agents/skills/django-run-migrations/SKILL.md` | Steps for generating and applying Django migrations |
| `.agents/skills/django-run-locally/SKILL.md` | Steps for initiating the Django development server without Docker |
| `.agents/skills/docker-deployment/SKILL.md` | Docker Compose, container services, deployment |
| `.agents/skills/documentation/SKILL.md` | How to update project documentation |
| `.agents/skills/frontend-ui/SKILL.md` | Frontend UI implementation, accessibility, and responsive checks |
| `.agents/skills/pull-request-workflow/SKILL.md` | Branching, commits, PR preparation, and review follow-up |

## Important Notes

- Skills **summarize and reference** existing instruction files; they do not duplicate coding rules.
- When in doubt, defer to the coding standards in `.github/instructions/`.
- All product code lives under `app/eventyay/`; use `eventyay.*` imports.
- New skills should follow this layout: `SKILL.md`, `references/`, `assets/`, and optional `tests/`.
- Do not add partial script scaffolding under skills unless command usage and working-directory assumptions are fully documented and validated.
---
name: code-review
description: How to review code and Pull Requests in the Eventyay repository against canonical instructions.
---

# Code Review Protocol

This skill provides the standard operating procedure for AI agents (like GitHub Copilot, Claude, etc.) performing code reviews on the Eventyay repository.

## 1. Initial Triage & Architecture Checks

Before reviewing specific business logic, strictly enforce these Non-Negotiable Architecture Rules (from `AGENTS.md`):

*   **Location Verification**: New product code must reside under `app/eventyay/`. Tests must reside under `app/tests/`. Ensure legacy directories (`talk/`, `video/`, `src/`) are not being actively modified unless requested.
*   **Legacy Namespaces**: Reject any new imports or logic using `pretix.*`, `pretalx.*`, or `venueless.*`. All new code must use the `eventyay.*` namespace.
*   **Multi-tenancy (Crucial)**: Any ORM query accessing event-specific data MUST be wrapped securely with `django_scopes.scope(event=event)`. Flag missing scopes immediately.
*   **ORM Efficiency**: Check for N+1 query vulnerabilities. Ensure `select_related` and `prefetch_related` are used appropriately.
*   **Error Handling**: Reject the use of generic `Exception` blocks. Code must catch specific exception types.
*   **Imports Structure**: Imports must be at the top of the file. Local imports inside functions/methods are strictly for resolving circular dependencies.
*   **Frontend Hard Rules**: No jQuery. No inline scripts in templates. JavaScript must use external ES modules.

## 2. File-Scoped Standard Enforcement

During the review, you MUST apply the canonical scoped rules based on the files modified in the pull request:

| File Type | Instruction File to Enforce | Key Review Focus |
| :--- | :--- | :--- |
| **Python** (`.py`) | `.github/instructions/python.instructions.md` | Python 3.12 compatibility, correct typing, proper Django 5.2+ usage, Celery task definitions. |
| **JavaScript/Vue** (`.js`, `.vue`) | `.github/instructions/js.instructions.md` | Vue 3 composition API standards, ES modules, strict absence of jQuery. |
| **Django Templates** (`.html`) | `.github/instructions/django-template.instructions.md` | Structural integrity, template tag correctness, absence of inline JavaScript. |
| **Jinja Templates** (`.html`, `.j2`) | `.github/instructions/jinja.instructions.md` | Syntax correctness, context safety and proper escaping. |
| **Dockerfile** | `.github/instructions/dockerfile.instructions.md` | Security, multi-stage build best practices, minimal layer size. |
| **TOML** (`.toml`) | `.github/instructions/toml.instructions.md` | Syntax validity, `uv` dependency alignment (`app/pyproject.toml`). |
| **Git Commits** | `.github/instructions/git-commit.instructions.md` | Conventional commit formatting, descriptive bodies. |

## 3. Security, Validation & State

*   **Permissions**: Verify that new endpoints or views enforce appropriate Django/DRF permissions and scopes.
*   **Validation**: Ensure all incoming data is validated via Django forms or DRF serializers.
*   **Runtime Context**: Keep in mind the stack runs on PostgreSQL, Redis, Channels, and Celery. Review background tasks for idempotency and transaction safety.

## 4. Providing Actionable Feedback

When leaving review comments:
1.  **Be Explicit**: Do not just say "fix imports". Say "Use `eventyay.*` for this import instead of `pretalx.*`".
2.  **Provide Code Snippets**: If an ORM query is missing a scope, provide the correct wrapped `django_scopes.scope(...)` snippet.
3.  **Cite Sources**: Reference `AGENTS.md` or the specific file in `.github/instructions/` to reinforce the source of truth.
4.  **Prioritize Severity**: Call out missing Django Scopes, N+1 queries, and generic exceptions as block-level issues.

# AI Agent Navigation Guide

AI agents should read instructions in this order:

1. `agents.md` — canonical policy for all agents (single source of truth)
2. `copilot-instructions.md` — GitHub Copilot adapter
3. `CLAUDE.md` — Claude adapter
4. `CODEX.md` — Codex adapter
5. `.github/instructions/` — file-scoped coding standards
6. `.agents/skills/` — reusable operational knowledge about the repository

## Skills Index

| Skill file | Purpose |
|---|---|
| `skills/repo-navigation.md` | Repository layout and where to find code |
| `skills/django-backend.md` | Django project structure, models, API, forms |
| `skills/python-style.md` | Python coding conventions |
| `skills/javascript-style.md` | JavaScript / frontend conventions |
| `skills/docker-deployment.md` | Docker Compose, container services, deployment |
| `skills/git-workflow.md` | Commit style and PR expectations |
| `skills/documentation.md` | How to update project documentation |

## Important Notes

- Skills **reference** existing instruction files; they do not duplicate them.
- When in doubt, defer to `agents.md` as the authoritative source.
- All product code lives under `app/eventyay/`; use `eventyay.*` imports.

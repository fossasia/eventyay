---
name: pull-request-workflow
description: Branching, commits, PR preparation, and review follow-up for Eventyay contributions
---

# Skill: Pull Request Workflow

## When to Use

Use this skill when preparing changes for review, responding to feedback, and finalizing a PR against `dev`.

## Core Workflow

1. Create a focused feature branch from `dev`.
2. Keep changes scoped to one concern and update tests for behavior changes.
3. Run targeted checks before requesting review.
4. Write a concise commit message that states what changed.
5. Prepare a clear PR description with context, test evidence, and risk notes.
6. Address reviewer comments with concrete follow-up commits.

## Guardrails

- Follow `.github/instructions/git-commit.instructions.md` for commit quality.
- Keep diffs small and avoid unrelated refactors.
- Do not amend shared history unless explicitly requested.

## Supporting Artifacts

- Workflow playbooks: `references/`
- Reusable templates: `assets/`
- Example review scenarios: `tests/`

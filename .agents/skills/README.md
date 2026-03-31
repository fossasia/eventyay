# Skills Directory Guide

This directory stores reusable operational skills for agents.

## Required Skill Layout

Each skill directory should contain:

- `SKILL.md` (metadata + concise workflow)
- `scripts/` (reusable executable helpers)
- `references/` (detailed docs loaded on demand)
- `assets/` (templates/checklists/snippets)
- `tests/` (scenario docs or test cases)

## Validation

Run the layout validator from repository root:

```bash
./tools/validate_skill_layout.sh
```

## Quality Boost Ideas

- Add an optional `examples/` folder with before/after snippets.
- Add a small CI job to run `tools/validate_skill_layout.sh`.
- Add trigger keywords in each `description` to improve discovery.
- Keep `SKILL.md` concise and move deep detail into `references/`.

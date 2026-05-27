# Skills Directory Guide

This directory stores reusable operational skills for agents.

## Required Skill Layout

Each skill directory should contain:

- `SKILL.md` (metadata + concise workflow)
- `references/` (detailed docs loaded on demand)
- `assets/` (templates/checklists/snippets)
- `tests/` (scenario docs or test cases, optional but recommended)

Avoid adding script stubs inside skill directories unless they are production-ready, have clear invocation guidance, and work from documented directories.

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

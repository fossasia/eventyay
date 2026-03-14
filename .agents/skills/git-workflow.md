# Skill: Git Workflow

Full commit message guidelines are defined in:

**`.github/instructions/git-commit.instructions.md`**

Read that file first. This skill provides a concise summary.

## Commit Message Style

- Write a short, imperative summary line that fits in one line (no verbose phrases like "Refactor X to improve readability and performance").
- If more detail is needed, add a blank line followed by a longer description.
- Do not reference upstream repositories, issues, or PRs.

**Good:**
```
Add email validation to registration form
```

**With body:**
```
Fix N+1 query in event list view

Use select_related('organiser') to fetch related objects in a
single query instead of one per event.
```

## Branching

- Work in feature branches; open PRs against the default branch.
- Keep commits focused and atomic.

## PR Expectations

- All CI checks must pass before merging.
- Keep diffs small and focused on a single concern.
- Update or add tests for any changed behavior.

## Important Constraints

- Only work inside this repository.
- All changes must be self-contained; do not reference external forks or upstream issues.

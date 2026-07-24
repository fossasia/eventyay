# Contributing to Eventyay

We welcome contributions to Eventyay.

## Getting Started

1. Fork the repository
2. Clone your fork
3. Create a branch from `dev` (see [Branch creation](#branch-creation))
4. Refer to [`README.rst`](README.rst) for development setup instructions

## Branch creation

Create a **new branch from `dev`** for every change. Do not commit directly to `dev` or `main`.

### Branch naming

Use a **prefix that describes the kind of change**, then a short slug. Use the same vocabulary in branch names, commit messages, and PR titles.

| Prefix | When to use | Example |
|--------|-------------|---------|
| `feat/` or `feature/` | New functionality | `feat/schedule-export` |
| `fix/` or `fix-` | Bug fix | `fix/presale-checkout-login` |
| `hotfix/` | Urgent production fix | `hotfix/payment-timeout` |
| `chore/` or `patch/` | Tooling, deps, housekeeping | `chore/update-ci-cache` |
| `docs/` | Documentation only | `docs/api-auth-guide` |
| `test/` | Test-only changes | `test/quota-edge-cases` |
| `refactor/` | Restructure without behavior change | `refactor/control-forms` |
| `ci/` | GitHub Actions / CI only | `ci/parallelize-tests` |
| `i18n/` | Translations / locale | `i18n/dutch-cfp-strings` |
| `migration/` | Database migrations (when migration-focused) | `migration/organizer-follower` |
| `perf/` | Performance improvement | `perf/schedule-caching` |
| `style/` | Formatting only | `style/lint-templates` |

**Tips:**

- Use lowercase and hyphens in the slug (`fix/order-form-scroll`, not `fix/OrderFormScroll`).
- Tie work to an issue when one exists: `fix/3128-pagination` or `issue-3128` — both are fine.
- One concern per branch. Split unrelated fixes into separate PRs.
- **Branch name drives the intent label** (`fix`, `chore`, `refactor`, …). A PR titled `chore: …` on branch `email-change` will not get the `chore` label — rename the branch to `chore/…` if you want that label.

```bash
git checkout dev
git pull upstream dev   # or origin dev, depending on your remote setup
git checkout -b fix/presale-checkout-login
```

### Automatic PR labels

Once merged, the [PR labeler workflow](.github/workflows/labeler.yml) applies up to **5 labels** per pull request, in this order:

1. **Area** — where in Eventyay (e.g. `video`, `schedule`, `orga`, `base`, `common`)
2. **Stack** — file types changed (`frontend`, `backend`)
3. **Test** — if test files changed
4. **Intent** — from branch prefix (`fix`, `chore`, `refactor`, `perf`, `style`, `revert`)
5. **Other** — if slots remain (e.g. `database`, `ci`, `documentation`, `dependencies`)

Area labels come from **changed files**, not the branch name. See [`.github/scripts/pr-labeler-lib.mjs`](.github/scripts/pr-labeler-lib.mjs) for the full path rules.

## Commit messages

Write messages that explain **what** changed and **why** when the why is not obvious. Avoid vague subjects like “fix bugs” or “update code”.

### Format

Use [Conventional Commits](https://www.conventionalcommits.org/) style:

```text
type(optional-scope): short summary

Optional longer body when the summary is not enough.
```

**Common types** (same vocabulary as branch prefixes):

| Type | Purpose |
|------|---------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation |
| `chore` | Maintenance (including dependency bumps: `chore(deps): …`) |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or updating tests |
| `ci` | CI/CD configuration |
| `perf` | Performance improvement |
| `style` | Formatting, whitespace, no logic change |

**Examples:**

```text
fix(presale): show login modal when checkout requires auth

feat(api): expose room schedule in public API

docs: update event screenshots in admin guide

chore(deps): bump pyotp from 2.9.0 to 2.10.0 in /app
```

### Rules

- **Subject line:** One line, imperative mood (“add field”, not “added field”). Keep it short enough for most Git clients.
- **Body:** Optional. Add a blank line after the subject, then explain motivation, trade-offs, or migration notes.
- **Atomic commits:** Each commit should be a coherent unit. Do not mix unrelated changes.
- **Squash fix-ups:** Before merge (or when squashing the PR), fold in tiny follow-ups (“address review”, “lint”, “typo”) so the final history stays readable.
- **No filler:** Skip phrases like “refactor to improve readability and performance” — say what you refactored instead.

Agent-oriented detail lives in [`.github/instructions/git-commit.instructions.md`](.github/instructions/git-commit.instructions.md).

## How to Contribute

### Code

- Follow existing project conventions.
- Add or update tests when behavior changes.
- Run tests and linters locally before pushing; **ensure CI is green** before you request review.
- Typical checks (from `app/`): `pytest tests/` after syncing dependencies and migrating as described in [`README.rst`](README.rst) and [`agents.md`](agents.md).

### Bug Reports

- Use GitHub Issues
- Include steps to reproduce
- Provide relevant environment details

### Documentation

- Improve clarity and accuracy
- Fix typos and formatting issues

### AI-assisted changes

If you use AI tools to help with changes, follow the instructions in [`.github/instructions/`](.github/instructions/) that apply to the files you touch (for example Python, JavaScript, Django templates).

## Pull request guidelines

1. **Link every PR to a GitHub issue.** Use GitHub’s closing keywords in the **PR description** (not the title), for example: `Fixes #123`.
2. **Keep PRs reviewable in less than a day.** Break large work into smaller issues and smaller PRs.
3. **Design changes:** Add screenshots or a short video so reviewers can see the UI or visual impact.
4. **Copilot:** Enable GitHub Copilot on your account when possible; this repo can auto-trigger Copilot reviews, which speeds up feedback.
5. **Reviewers:** Do not tag reviewers repeatedly; the PR will be reviewed in turn.
6. **Issues:** Avoid picking up issues that are already assigned to someone else unless you coordinate with them.
7. In the **PR description**, briefly summarize the change and reference the linked issue (with closing keywords in the description only).
8. **Large or long-running work:** Open a **draft** pull request early so direction is visible and others are less likely to duplicate effort.

**Workflow:** Push your branch to your fork, open a Pull Request against `dev`, and respond to review feedback.

## Further reading

- [`agents.md`](agents.md) — stack, layout (`app/eventyay/`, `app/tests/`, `doc/`), and architecture rules contributors should respect.
- [docs.eventyay.com](https://docs.eventyay.com) — published documentation (sources in [`doc/`](doc/)).

## Licensing

All contributions are accepted under the Apache License 2.0.
See [CLA.md](CLA.md) for details.

# Contributing to Eventyay

We welcome contributions to Eventyay.

## Getting Started

1. Fork the repository
2. Clone your fork
3. Create a new branch for your changes
4. Refer to [`README.rst`](README.rst) for development setup instructions

## Branching and commits

- Work in feature branches and open pull requests against the `dev` branch.
- Keep commits focused and atomic.
- Write clear, meaningful commit messages that describe **what** changed and **why**—not generic text like “fix bugs”.
- Prefer a **short summary line** (one line in most Git clients). If more context is needed, add a **blank line**, then a longer body.
- Avoid unnecessary verbosity in the subject (for example, you do not need to explain that a refactor improves readability; say what you refactored).
- **Squash** minor fix-up commits (style tweaks, CI fixes, “address review”) so the final history stays readable and is not cluttered with tiny commits.

Project conventions for Git and PRs are also summarized in [`.github/instructions/git-commit.instructions.md`](.github/instructions/git-commit.instructions.md).

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

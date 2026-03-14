# Skill: Documentation

## Documentation Files

| File | Purpose |
|---|---|
| `README.rst` | Project overview and getting-started guide (reStructuredText) |
| `CONTRIBUTING.md` | Contributor guidelines and development setup |
| `DEPLOYMENT.md` | Production deployment walkthrough |
| `.github/instructions/DOCKERFILE.instructions.md` | Docker Compose usage and container reference |
| `doc/` | Extended project documentation |

## How to Update `README.rst`

- Written in **reStructuredText** (`.rst`).
- Keep the getting-started steps current when CLI commands or workflows change.
- Maintain existing section structure; add new sections at a logical location.

## How to Update `doc/`

- Files may be `.rst` or `.md` depending on the sub-section.
- Follow the existing style of the surrounding files.
- Run a documentation build locally if a build pipeline is configured.

## How to Update `CONTRIBUTING.md`

- Keep the setup instructions in sync with `README.rst`.
- Document any new tooling or workflow changes that affect contributors.

## General Guidelines

- Keep documentation concise and accurate.
- Prefer concrete examples over abstract descriptions.
- When changing a CLI command, update all documentation that references it.
- Documentation changes do not require tests unless there are specific doc-tests.

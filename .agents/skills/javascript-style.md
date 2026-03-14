# Skill: JavaScript Style

Full JavaScript coding standards are defined in:

**`.github/instructions/js.instructions.md`**

Read that file first. This skill provides a concise summary.

## Key Expectations

- **No jQuery.** Use the standard DOM API or lightweight libraries.
- **ES modules only.** Do not use IIFEs or global variables.
- **No inline scripts.** All JavaScript must be in external files (required by CSP).
- Handle errors explicitly; never create empty `catch` blocks.
- When using `ky` (or similar), preserve its specific error types (`HTTPError`) rather than wrapping them in a generic `Error`.

## Frontend Code Locations

| Path | Purpose |
|---|---|
| `app/eventyay/static/` | Static assets served by Django (CSS, legacy JS) |
| `app/eventyay/webapp/` | Modern JS applications (Vue 3, built with a bundler) |

Sub-applications inside `webapp/` each have their own `node_modules/` and build pipeline. Check the relevant `package.json` for build commands.

## Vue 3

The project uses Vue 3 for interactive front-end components. Follow Vue 3 Composition API conventions when adding new components.

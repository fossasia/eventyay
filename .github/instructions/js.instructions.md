---
description: 'JavaScript & Vue development standards (legacy JS without build step + modern bundled Vue 3 apps)'
applyTo: 'app/**/*.{js,ts,vue}'
---

## Development Standards

### Modernization

- Do not use jQuery
- Use ES modules, not IIFEs.
- Implement as external scripts; do not use inline scripts because they are blocked by CSP.

### Error handling

- Always log errors with contextual information. You may skip this when letting the error bubble up to be handled by a higher-level component or function.
- Use `try/catch` blocks in async functions to handle exceptions gracefully. You may skip this when letting the error bubble up to be handled by a higher-level component or function, but you must add a comment documenting that the function may throw errors. For example:

  ```ts
  /**
  * @throws {HTTPError} when the network request fails
  */
  async function fetchData() {
    const response = await ky.get('/some-endpoint')
    return response.json()
  }
  ```

- When working with a library that provides its own error types (such as `ky` with `HTTPError`), do not replace this specific error type with a generic one. For example, do not do this:
  ```ts
  try {
    await ky.get('/some-endpoint')
  } catch (error) {
    throw new Error('Failed to fetch data') // Bad: replacing HTTPError with generic Error
  }
  ```

  Instead, let the error bubble up (with a comment), or do this:

  ```ts
  try {
    await ky.get('/some-endpoint')
  } catch (error) {
    if (error instanceof HTTPError) {
      // Handle HTTPError specifically
      throw error // Re-throw the original error
    }
    throw new Error('An unexpected error occurred') // Handle other errors
  }
  ```

- Do not create empty `catch` blocks.

### DOM access

- Be careful when using `.closest(selector)` because it makes the page fragile to DOM changes. Choose a `selector` carefully so that the code does not break when the DOM changes.

## Comments

- Do not add a comment when the code is already obvious and the comment is almost the same as the code.

## Frontend Code Locations

| Path | Purpose |
|---|---|
| `app/eventyay/static/` | Static assets served by Django (CSS, legacy JS) |
| `app/eventyay/webapp/` | Modern JS applications (Vue 3, built with a bundler) |

Sub-applications inside `webapp/` each have their own `node_modules/` and build pipeline. Check the relevant `package.json` for build commands.

## Vue 3

The project uses Vue 3 for interactive front-end components. Follow Vue 3 Composition API conventions when adding new components.

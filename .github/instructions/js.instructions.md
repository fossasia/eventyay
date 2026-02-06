---
description: 'JavaScript (directly run, without a build step) development standards and best practices with Composition API and TypeScript'
applyTo: 'app/**/*.js'
---

## Development Standards

### Modernization

- Do not use jQuery
- Use ES modules, not IIFEs.
- Implement as external scripts; do not use inline scripts, because they are blocked by CSP.

### Error handling

- Always log errors with contextual information. You may skip this when you let the error bubble up and be handled in a higher-level component or function.
- Use `try/catch` blocks in async functions to handle exceptions gracefully. You may skip this when you let the error bubble up and be handled in a higher-level component or function, but you need to add a comment to document possible error throwing. For example:

  ```ts
  /**
  * @throws {HTTPError} when the network request fails
  */
  async function fetchData() {
    const response = await ky.get('/some-endpoint')
    return response.json()
  }
  ```

- When you work with a library that comes with its own error types (like `ky` with `HTTPError`), do not replace this specific error type with a generic one. For example, do not do this:
  ```ts
  try {
    await ky.get('/some-endpoint')
  } catch (error) {
    throw new Error('Failed to fetch data') // Bad: replacing HTTPError with generic Error
  }
  ```

  Instead, just let the error bubble up (with a comment), or do this:

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

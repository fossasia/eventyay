
---
description: 'JavaScript (directly run, non-build) development standards and best practices with Composition API and TypeScript'
applyTo: 'app/**/*.js'
---

## Development Standards

### Modernization

- Don't use jQuery
- Use module type, not IIFE.
- Implemented as external script, don't use inline script, because it is blocked by CSP.

### Error handling

- Always log errors with contextual information, can skip it when you let the error bubble up and handled in higher component / function.
- Use `try/catch` blocks in async functions to handle exceptions gracefully, can skip it when you let the error bubble up and handled in higher component / function, but you need to add a comment to inform possible error throwing. For example:

  ```ts
  /**
  * @throws {HTTPError} when the network request fails
  */
  async function fetchData() {
    const response = await ky.get('/some-endpoint')
    return response.json()
  }
  ```

- When you work with a library that comes with its own error types (like `ky` with `HTTPError`), don't replace this specific error type with a generic one. For example, don't do this:
  ```ts
  try {
    await ky.get('/some-endpoint')
  } catch (error) {
    throw new Error('Failed to fetch data') // Bad: replacing HTTPError with generic Error
  }
  ```

  Instead, just let error bubble up (with a comment), or do this:

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

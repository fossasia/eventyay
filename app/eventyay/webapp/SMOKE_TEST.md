Smoke test for ErrorBoundary and error reporting

This file documents a quick manual smoke test to verify that the frontend error handling and reporting are working.

1) Start the dev server

   cd app/eventyay/webapp
   npm install        # if dependencies are not installed
   npm run start

2) Test component-level boundary

   - Open the app in the browser and navigate to a page where `AppBar` is visible.
   - In the browser console run the following to simulate an error inside AppBar's render path:

     // Simulate an error that bubbles through Vue
     setTimeout(() => { throw new Error('SMOKE: AppBar test error') }, 0)

   - The `ErrorBoundary` wrapping `AppBar` should display a fallback UI and the reporter should attempt to POST the error to the configured `config.api.feedback` endpoint (or log to console if none configured).

3) Test global unhandled rejection

   - In the browser console:

     Promise.reject(new Error('SMOKE: unhandled rejection test'))

   - The global `unhandledrejection` handler should report the error; check console/network for evidence.

4) Test window.onerror

   - In the browser console:

     undefinedFunctionCall() // ReferenceError

   - This should be reported by the `window.error` handler.

5) Verify dedupe

   - Rapidly trigger the same error multiple times (within 30s). The reporter will dedupe identical errors and should only send one request within the dedupe window.

Notes

- For production use, integrate a hosted error-tracking provider (Sentry/Datadog) and configure source maps for readable stacks.
- The smoke test assumes `config.api.feedback` is set in your environment (see `app/eventyay/webapp/config.js`) — otherwise the reporter will write to console.

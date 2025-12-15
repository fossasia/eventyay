/* Minimal error reporting utility used by client-side error boundaries.
 * Sends a best-effort POST to the configured feedback endpoint and
 * falls back to console logging when unavailable.
 */
import config from 'config'

// Simple in-memory dedupe cache to avoid spamming the backend with identical errors
const DEDUPE_WINDOW_MS = 30 * 1000 // 30s
const dedupe = new Map()

function safeStringify(obj) {
  try {
    return JSON.stringify(obj)
  } catch (e) {
    return String(obj)
  }
}

function signatureFor(payload) {
  // Use message + stack + meta.source as signature
  return `${payload.message}|${payload.stack || ''}|${(payload.meta && payload.meta.source) || ''}`
}

function scrubUrl(url) {
  try {
    const u = new URL(url, window.location.href)
    u.search = '' // drop query params to avoid leaking tokens
    return u.toString()
  } catch (e) {
    return url
  }
}

export default async function reportError(error, meta = {}) {
  try {
    const payload = {
      type: 'frontend_error',
      message: error?.message || String(error),
      stack: error?.stack || null,
      url: scrubUrl(window.location.href),
      userAgent: navigator.userAgent,
      meta: meta || {}
    }

    const sig = signatureFor(payload)
    const now = Date.now()
    const last = dedupe.get(sig)
    if (last && now - last < DEDUPE_WINDOW_MS) {
      // duplicate within window — drop silently
      return
    }
    dedupe.set(sig, now)

    // occasionally prune the map to avoid memory growth
    if (dedupe.size > 5000) {
      const cutoff = now - DEDUPE_WINDOW_MS
      for (const [k, t] of dedupe) {
        if (t < cutoff) dedupe.delete(k)
      }
    }

    const feedbackUrl = config?.api?.feedback
    if (feedbackUrl) {
      // fire-and-forget; do not block UI
      fetch(feedbackUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: safeStringify(payload),
        keepalive: true
      }).catch(() => {
        // fallback to console if network/reporting fails
        // eslint-disable-next-line no-console
        console.error('[ErrorReporter] failed to POST error', payload)
      })
    } else {
      // no endpoint configured; fallback to console
      // eslint-disable-next-line no-console
      console.error('[ErrorReporter] No feedback endpoint configured. Error:', payload)
    }
  } catch (e) {
    // never throw from the reporter
    // eslint-disable-next-line no-console
    console.error('[ErrorReporter] failed to report error', e)
  }
}

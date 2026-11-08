/**
 * Normalizes session and talk resources for download/external link display.
 * Appends '#resource' to PDF resources (preserving query params/hashes) so
 * the in-browser PDF viewer opens correctly, while preserving link resources.
 */
export function normalizeDisplayResources (resources = []) {
	if (!Array.isArray(resources)) return []
	return resources.map((r) => {
		if (!r) return r
		const resPath = r.resource || r.link
		if (resPath) {
			const cleanPath = resPath.split(/[?#]/)[0]
			if (cleanPath.toLowerCase().endsWith('.pdf') && !resPath.includes('#')) {
				return {
					...r,
					resource: r.resource ? `${r.resource}#resource` : undefined,
					link: r.link ? `${r.link}#resource` : undefined,
				}
			}
		}
		return r
	})
}

const UNSAFE_SCHEMES = new Set(['javascript', 'data', 'vbscript'])

/**
 * Resolves a resource URL to an absolute URL.
 * Preserves all safe absolute schemes (HTTP, HTTPS, FTP, SFTP, mailto, etc.).
 * Rejects unsafe schemes such as javascript: to prevent script execution.
 * Path-relative URLs are resolved against the full event URL (including any subpath).
 * If the provided base URL points to an API path, resolves against its origin instead.
 * Root-relative URLs are resolved against the origin.
 */
export function resolveAbsoluteUrl (url, eventUrl = '') {
	if (!url) return url
	const schemeMatch = String(url).match(/^([a-zA-Z][a-zA-Z0-9+.-]*):/i)
	if (schemeMatch) {
		const scheme = schemeMatch[1].toLowerCase()
		if (UNSAFE_SCHEMES.has(scheme)) {
			return ''
		}
		return url
	}
	try {
		const windowOrigin = (typeof window !== 'undefined' && window.location?.origin) || 'http://localhost'
		const base = new URL(eventUrl || '/', windowOrigin)
		if (url.startsWith('/') || /\/api(\/|$)/i.test(base.pathname)) {
			return new URL(url, base.origin).href
		}
		if (!base.pathname.endsWith('/')) {
			base.pathname += '/'
		}
		return new URL(url, base).href
	} catch (error) {
		console.error('Failed to resolve absolute resource URL', { url, eventUrl, error })
		return url
	}
}

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

const SAFE_SCHEMES = new Set(['http:', 'https:', 'ftp:', 'ftps:', 'sftp:', 'mailto:', 'tel:'])

function isApiEndpoint (pathname) {
	return /^(?:\/[a-z]{2}(?:-[a-z]{2,4})?)?\/api(?:\/|$)/i.test(pathname)
}

/**
 * Resolves a resource URL to an absolute URL.
 * Preserves all safe absolute schemes (HTTP, HTTPS, FTP, SFTP, mailto, etc.).
 * Rejects unsafe schemes such as javascript: to prevent script execution,
 * including obfuscated schemes with leading whitespace or embedded ASCII control characters.
 * Path-relative URLs are resolved against the full event URL (including any subpath).
 * If the provided base URL points to an actual API endpoint (e.g. /api/v1/...), resolves against its origin instead.
 * Root-relative URLs are resolved against the origin.
 */
export function resolveAbsoluteUrl (url, eventUrl = '') {
	if (!url) return url

	const sanitized = String(url).trim()
	const cleaned = sanitized.replace(/[\x00-\x20]+/g, '')
	const schemeMatch = cleaned.match(/^([a-zA-Z][a-zA-Z0-9+.-]*):/i)
	if (schemeMatch) {
		const scheme = `${schemeMatch[1].toLowerCase()}:`
		if (!SAFE_SCHEMES.has(scheme)) {
			return ''
		}
		if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/i.test(sanitized)) {
			return sanitized
		}
	}

	try {
		const windowOrigin = (typeof window !== 'undefined' && window.location?.origin) || 'http://localhost'
		const base = new URL(eventUrl || '/', windowOrigin)
		if (sanitized.startsWith('/') || isApiEndpoint(base.pathname)) {
			const resolved = new URL(sanitized, base.origin)
			return SAFE_SCHEMES.has(resolved.protocol.toLowerCase()) ? resolved.href : ''
		}
		if (!base.pathname.endsWith('/')) {
			base.pathname += '/'
		}
		const resolved = new URL(sanitized, base)
		return SAFE_SCHEMES.has(resolved.protocol.toLowerCase()) ? resolved.href : ''
	} catch (error) {
		console.error('Failed to resolve absolute resource URL', { url, eventUrl, error })
		return ''
	}
}

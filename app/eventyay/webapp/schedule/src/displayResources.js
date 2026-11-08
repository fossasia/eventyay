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

/**
 * Resolves a resource URL to an absolute URL.
 * Preserves all absolute schemes (HTTP, HTTPS, FTP, SFTP, etc.).
 * Path-relative URLs are resolved against the full event URL (including any subpath).
 * Root-relative URLs are resolved against the origin.
 */
export function resolveAbsoluteUrl (url, eventUrl = '') {
	if (!url) return url
	if (/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//i.test(url)) return url
	try {
		const windowOrigin = (typeof window !== 'undefined' && window.location?.origin) || 'http://localhost'
		const base = new URL(eventUrl || '/', windowOrigin)
		if (url.startsWith('/')) {
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

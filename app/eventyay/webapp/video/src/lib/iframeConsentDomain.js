/**
 * Normalize a domain string for iframe consent allowlists (lowercase hostname, no port).
 * Accepts bare hostnames, host:port, or full URLs. Returns null when input is invalid.
 */
export function normalizeIframeConsentDomain(domain) {
	if (typeof domain !== 'string') return null
	const trimmed = domain.trim().toLowerCase()
	if (!trimmed) return null
	try {
		const withScheme = /^[a-z][a-z0-9+.-]*:/i.test(trimmed) ? trimmed : `http://${trimmed}`
		return new URL(withScheme).hostname
	} catch {
		return null
	}
}

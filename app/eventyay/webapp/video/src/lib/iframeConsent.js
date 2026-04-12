import store from 'store'
import { normalizeIframeConsentDomain } from 'lib/iframeConsentDomain'

/**
 * Returns the iframe blocker configuration that applies to the given hostname.
 * Iterates over all configured domains (skipping the reserved 'default' key) and
 * returns the first match. Falls back to the 'default' entry when no domain matches.
 * Returns { enabled: false } as a safe no-op when the world state is not yet loaded.
 */
export function getBlockerConfig(domain) {
	const blockers = store.state.world?.iframe_blockers
	const normalized = normalizeIframeConsentDomain(domain)
	if (!blockers || !normalized) return { enabled: false }
	for (const [configDomain, config] of Object.entries(blockers)) {
		if (configDomain === 'default') continue
		if (normalized === configDomain || normalized.endsWith('.' + configDomain)) return config
	}
	return blockers.default ?? { enabled: false }
}

/**
 * Returns true when the given hostname has an active consent blocker and the
 * domain is not present in `unblockedIframeDomains` (Vuex / localStorage).
 * Temporary "show once" consent in IframeBlocker is not visible here; callers
 * that need one-off bypass pass `skipConsentCheck` when creating the iframe.
 */
export function isDomainBlocked(domain) {
	const normalized = normalizeIframeConsentDomain(domain)
	if (!normalized) return false
	const config = getBlockerConfig(normalized)
	if (!config?.enabled) return false
	return !store.state.unblockedIframeDomains.has(normalized)
}

/**
 * Extracts the hostname (without port) from a URL string. Resolves protocol-relative
 * and relative URLs against the current page when available. Returns null for
 * non-string input or URLs that cannot be parsed.
 */
export function getUrlDomain(url) {
	if (typeof url !== 'string') return null
	try {
		const base =
			typeof window !== 'undefined' && window.location?.href ? window.location.href : undefined
		const hostname = new URL(url, base).hostname
		return hostname ? normalizeIframeConsentDomain(hostname) : null
	} catch {
		return null
	}
}

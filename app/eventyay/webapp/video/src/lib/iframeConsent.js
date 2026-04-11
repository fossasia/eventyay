import store from 'store'

/**
 * Returns the iframe blocker configuration that applies to the given hostname.
 * Iterates over all configured domains (skipping the reserved 'default' key) and
 * returns the first match. Falls back to the 'default' entry when no domain matches.
 * Returns { enabled: false } as a safe no-op when the world state is not yet loaded.
 */
export function getBlockerConfig(domain) {
	const blockers = store.state.world?.iframe_blockers
	if (!blockers || !domain) return { enabled: false }
	for (const [configDomain, config] of Object.entries(blockers)) {
		if (configDomain === 'default') continue
		if (domain === configDomain || domain.endsWith('.' + configDomain)) return config
	}
	return blockers.default ?? { enabled: false }
}

/**
 * Returns true when the given hostname has an active consent blocker and the
 * user has not yet granted consent for this domain (neither persistently via
 * localStorage nor temporarily via showingOnce within a component instance).
 */
export function isDomainBlocked(domain) {
	if (!domain) return false
	const config = getBlockerConfig(domain)
	if (!config?.enabled) return false
	return !store.state.unblockedIframeDomains.has(domain)
}

/**
 * Extracts the hostname (without port) from a URL string.  Returns null for
 * non-string input or URLs that cannot be parsed by the URL constructor.
 */
export function getUrlDomain(url) {
	if (typeof url !== 'string') return null
	try {
		return new URL(url).hostname
	} catch {
		return null
	}
}

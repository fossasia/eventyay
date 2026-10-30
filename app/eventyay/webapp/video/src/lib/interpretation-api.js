import api from 'lib/api'

export function apiErrorDetail(data) {
	const detail = data?.detail
	if (typeof detail === 'string') return detail
	if (Array.isArray(detail)) return detail.map((item) => String(item)).join(', ')
	if (detail && typeof detail === 'object') {
		return Object.entries(detail)
			.map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`)
			.join('; ')
	}
	return ''
}

function isPopulatedSlug(val) {
	if (typeof val !== 'string' && typeof val !== 'number') return false
	const s = String(val).trim()
	return s.length > 0 && s !== 'undefined' && s !== 'null'
}

const ROUTE_KEYWORDS = new Set([
	'video',
	'event',
	'events',
	'rooms',
	'channels',
	'schedule',
	'about',
	'standalone',
	'control',
	'orga',
	'admin',
	'api',
	'static',
	'common',
	'plugins',
	'login',
	'kiosks',
	'chat'
])

export function interpretationRouting(store) {
	const world = store?.state?.world || store?.world
	let organizer = world?.organizer_slug
	let event = world?.slug || world?.id

	// When slugs come directly from store.world, they are already validated by the backend.
	if (isPopulatedSlug(organizer) && isPopulatedSlug(event)) {
		return { organizer: String(organizer).trim(), event: String(event).trim() }
	}

	if (typeof window !== 'undefined') {
		const injected = window.eventyay || window.venueless
		if (!isPopulatedSlug(organizer)) {
			organizer = injected?.organizerSlug || injected?.organizer_slug
		}
		if (!isPopulatedSlug(event)) {
			event = injected?.eventSlug || injected?.event_slug
		}

		if (isPopulatedSlug(organizer) && isPopulatedSlug(event)) {
			return { organizer: String(organizer).trim(), event: String(event).trim() }
		}

		// Check injected URLs (e.g., videoUrl, interpretationUrl, ticketUrl, basePath)
		const candidateUrls = [
			injected?.basePath,
			injected?.videoUrl,
			injected?.interpretationUrl,
			injected?.ticketUrl,
			injected?.talkUrl,
			injected?.homeUrl,
			injected?.publicVideoUrl
		].filter(Boolean)

		for (const u of candidateUrls) {
			if (isPopulatedSlug(organizer) && isPopulatedSlug(event)) break
			const parts = String(u).split('/').filter(Boolean)
			if (parts[0] === 'video' && parts[1] === 'event' && parts.length >= 4) {
				if (!isPopulatedSlug(organizer) && !ROUTE_KEYWORDS.has(parts[2])) organizer = parts[2]
				if (!isPopulatedSlug(event) && !ROUTE_KEYWORDS.has(parts[3])) event = parts[3]
			} else if (parts[0] === 'video' && parts[1] === 'plugins' && parts.length >= 4) {
				if (!isPopulatedSlug(organizer) && !ROUTE_KEYWORDS.has(parts[2])) organizer = parts[2]
				if (!isPopulatedSlug(event) && !ROUTE_KEYWORDS.has(parts[3])) event = parts[3]
			} else if (parts[1] === 'event' && parts.length >= 4) {
				if (!isPopulatedSlug(organizer) && !ROUTE_KEYWORDS.has(parts[2])) organizer = parts[2]
				if (!isPopulatedSlug(event) && !ROUTE_KEYWORDS.has(parts[3])) event = parts[3]
			} else if (parts.length >= 3 && parts[2] === 'video' && !ROUTE_KEYWORDS.has(parts[0])) {
				if (!isPopulatedSlug(organizer)) organizer = parts[0]
				if (!isPopulatedSlug(event) && !ROUTE_KEYWORDS.has(parts[1])) event = parts[1]
			}
		}

		// Fallback to window.location.pathname parsing using explicit route shapes
		if (!isPopulatedSlug(organizer) || !isPopulatedSlug(event)) {
			const pathParts = window.location.pathname.split('/').filter(Boolean)
			// Shape 1: /video/event/:organizer/:event/...
			if (pathParts[0] === 'video' && pathParts[1] === 'event' && pathParts.length >= 4) {
				if (!isPopulatedSlug(organizer) && !ROUTE_KEYWORDS.has(pathParts[2])) organizer = pathParts[2]
				if (!isPopulatedSlug(event) && !ROUTE_KEYWORDS.has(pathParts[3])) event = pathParts[3]
			}
			// Shape 2: /:organizer/:event/video/...
			else if (pathParts.length >= 3 && pathParts[2] === 'video' && !ROUTE_KEYWORDS.has(pathParts[0])) {
				if (!isPopulatedSlug(organizer)) organizer = pathParts[0]
				if (!isPopulatedSlug(event) && !ROUTE_KEYWORDS.has(pathParts[1])) event = pathParts[1]
			}
			// Shape 3: /control/event/:organizer/:event/... or /orga/event/:organizer/:event/...
			else if (pathParts[1] === 'event' && pathParts.length >= 4) {
				if (!isPopulatedSlug(organizer) && !ROUTE_KEYWORDS.has(pathParts[2])) organizer = pathParts[2]
				if (!isPopulatedSlug(event) && !ROUTE_KEYWORDS.has(pathParts[3])) event = pathParts[3]
			}
			// Shape 4: Generic /:organizer/:event/... where the first segments are not known route keywords
			else if (pathParts.length >= 2 && !ROUTE_KEYWORDS.has(pathParts[0]) && !ROUTE_KEYWORDS.has(pathParts[1])) {
				if (!isPopulatedSlug(organizer)) organizer = pathParts[0]
				if (!isPopulatedSlug(event)) event = pathParts[1]
			}
		}
	}

	if (!isPopulatedSlug(organizer) || !isPopulatedSlug(event)) {
		return { organizer: null, event: null }
	}

	return {
		organizer: String(organizer).trim(),
		event: String(event).trim(),
	}
}

export function interpretationApiUrl(store, roomId, suffix = 'config/') {
	const { organizer, event } = interpretationRouting(store)
	if (!organizer || !event || !roomId) {
		return null
	}
	return `/api/v1/organizers/${organizer}/events/${event}/rooms/${roomId}/interpretation/${suffix}`
}

export async function fetchListenerToken(store, roomId) {
	const url = interpretationApiUrl(store, roomId, 'token/')
	if (!url) {
		return null
	}
	try {
		const response = await fetch(url, {
			headers: await interpretationAuthHeaders(),
			credentials: 'include',
		})
		if (!response.ok) return null
		const data = await response.json().catch(() => ({}))
		return data.token || null
	} catch (e) {
		return null
	}
}

export async function interpretationAuthHeaders(json = false) {
	let authHeader = null
	if (api?._config?.token) {
		authHeader = `Bearer ${api._config.token}`
	} else if (api?._config?.clientId) {
		authHeader = `Client ${api._config.clientId}`
	}
	const headers = { Accept: 'application/json' }
	if (json) headers['Content-Type'] = 'application/json'
	if (authHeader) headers.Authorization = authHeader
	if (json && typeof document !== 'undefined') {
		const match = document.cookie.match(/eventyay_csrftoken=([^;]+)/)
		if (match) headers['X-CSRFToken'] = match[1]
	}
	return headers
}

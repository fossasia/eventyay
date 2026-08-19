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

export function interpretationRouting(store) {
	const world = store.state.world
	let organizer = world?.organizer_slug
	let event = world?.slug || world?.id
	if (!organizer || organizer === 'default') {
		const pathParts = window.location.pathname.split('/').filter(Boolean)
		if (pathParts.length >= 2) {
			organizer = pathParts[0]
			event = pathParts[1]
		}
	}
	return { organizer, event }
}

export function interpretationApiUrl(store, roomId, suffix = 'config/') {
	const { organizer, event } = interpretationRouting(store)
	return `/api/v1/organizers/${organizer}/events/${event}/rooms/${roomId}/interpretation/${suffix}`
}

export function interpretationAuthHeaders(json = false) {
	const authHeader = api._config.token
		? `Bearer ${api._config.token}`
		: api._config.clientId
			? `Client ${api._config.clientId}`
			: null
	const headers = { Accept: 'application/json' }
	if (json) headers['Content-Type'] = 'application/json'
	if (authHeader) headers.Authorization = authHeader
	if (json) {
		const match = document.cookie.match(/eventyay_csrftoken=([^;]+)/)
		if (match) headers['X-CSRFToken'] = match[1]
	}
	return headers
}

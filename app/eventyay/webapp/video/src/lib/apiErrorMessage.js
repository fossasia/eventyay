const ERROR_KEYS = ['__all__', 'non_field_errors', 'detail', 'message']

function messageFrom(value) {
	if (Array.isArray(value)) return messageFrom(value[0])
	if (typeof value === 'string' && value.trim()) return value.trim()
	return null
}

export function apiErrorMessage(payload, fallback = 'Bad Request') {
	if (typeof payload === 'string') return payload.trim() || fallback
	if (!payload || typeof payload !== 'object') return fallback
	for (const key of ERROR_KEYS) {
		const message = messageFrom(payload[key])
		if (message) return message
	}
	return messageFrom(Object.values(payload)[0]) || fallback
}

/**
 * @param {Response} response
 * @param {string} [fallback]
 */
export async function readApiErrorMessage(response, fallback = 'Bad Request') {
	let text = ''
	try {
		text = await response.text()
	} catch (error) {
		console.warn('Failed to read API error response', error)
		return fallback
	}
	if (!text.trim()) return fallback
	try {
		return apiErrorMessage(JSON.parse(text), fallback)
	} catch (error) {
		console.warn('API error response was not JSON', error)
		return text.trim()
	}
}

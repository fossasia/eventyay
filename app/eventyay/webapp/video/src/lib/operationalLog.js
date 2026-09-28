const SAFE = /^[A-Za-z0-9._:-]{1,128}$/
const ALLOWED_ACTIONS = new Set([
	'iframe.load',
	'iframe.error',
	'ws.connect',
	'ws.close',
	'ws.error',
	'bbb.join',
	'jitsi.join',
	'janus.connect',
	'janus.fail',
	'zoom.sdk',
	'hls.error',
	'upload',
	'whep.connect',
	'interpretation.token',
	'interpretation.config',
	'schedule.fav',
	'schedule.save',
	'schedule.fetch',
	'stream.poll',
	'stream.schedule',
	'bbb.recordings',
	'captions.ws',
])

function safeValue(value) {
	if (typeof value === 'number' && Number.isFinite(value)) return value
	if (typeof value === 'string' && SAFE.test(value)) return value
	return null
}

const lastFailure = new Map()

function shouldReport(key) {
	const now = Date.now()
	const previous = lastFailure.get(key) || 0
	if (now - previous < 5000) return false
	lastFailure.set(key, now)
	return true
}

function reportFailure(fields) {
	try {
		const api = typeof window !== 'undefined' ? window.api : null
		if (!api || api.socketState !== 'open' || typeof api.call !== 'function') return
		api.call('event.client_log', fields, {timeout: 5000}).catch(() => {})
	} catch (error) {
		// Reporting must never break the app.
	}
}

export function logOperational({
	component = 'video',
	action,
	outcome,
	error_code,
	backend,
	status,
	duration_ms,
} = {}) {
	if (!ALLOWED_ACTIONS.has(action)) return
	if (outcome !== 'success' && outcome !== 'failure') outcome = 'failure'
	const record = {
		datetime: new Date().toISOString(),
		component,
		action,
		outcome,
	}
	const errorCode = safeValue(error_code)
	const backendName = safeValue(backend)
	const statusCode = safeValue(status)
	const duration = safeValue(duration_ms)
	if (errorCode != null) record.error_code = errorCode
	if (backendName != null) record.backend = backendName
	if (statusCode != null) record.status = statusCode
	if (duration != null) record.duration_ms = duration
	const line = Object.entries(record).map(([key, value]) => `${key}=${value}`).join(' ')
	if (outcome === 'failure') {
		console.warn('[eventyay]', line)
		const key = `${action}:${record.error_code || ''}:${record.backend || ''}`
		if (shouldReport(key)) {
			reportFailure({
				action,
				outcome,
				error_code: errorCode,
				backend: backendName,
			})
		}
	} else {
		console.info('[eventyay]', line)
	}
}

export default logOperational

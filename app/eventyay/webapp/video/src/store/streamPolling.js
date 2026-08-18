export const STREAM_POLL_BASE_DELAY = 60000
export const STREAM_POLL_MAX_DELAY = 300000
export const STREAM_POLL_MAX_TRANSIENT_ERRORS = 5
export const STREAM_POLL_PERMANENT_STATUSES = [401, 403]

export function httpErrorStatus (error) {
	return error?.status ?? error?.response?.status
}

export function isPermanentStreamPollError (error) {
	return STREAM_POLL_PERMANENT_STATUSES.includes(httpErrorStatus(error))
}

export function nextStreamPollDelay (currentDelay, maxDelay = STREAM_POLL_MAX_DELAY) {
	return Math.min((currentDelay || STREAM_POLL_BASE_DELAY) * 2, maxDelay)
}

export function shouldStopAfterTransientErrors (count) {
	return count >= STREAM_POLL_MAX_TRANSIENT_ERRORS
}

export function streamPollJitter (ms) {
	return ms + Math.random() * 2000
}

export function usesHttpStreamFallback (connected) {
	return !connected
}

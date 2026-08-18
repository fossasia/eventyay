/**
 * Stream polling backoff, visibility, and permanent-error helpers.
 * Run: node --test src/store/streamPolling.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import {
	STREAM_POLL_MAX_DELAY,
	httpErrorStatus,
	isPermanentStreamPollError,
	nextStreamPollDelay,
	shouldStopAfterTransientErrors,
	usesHttpStreamFallback,
} from './streamPolling.js'

test('permanent errors stop polling on 401 and 403', () => {
	for (const status of [401, 403]) {
		assert.equal(isPermanentStreamPollError({status}), true)
	}
	assert.equal(isPermanentStreamPollError({status: 400}), false)
	assert.equal(isPermanentStreamPollError({status: 500}), false)
	assert.equal(isPermanentStreamPollError({}), false)
})

test('httpErrorStatus reads nested response status', () => {
	assert.equal(httpErrorStatus({response: {status: 403}}), 403)
	assert.equal(httpErrorStatus({status: 404}), 404)
})

test('transient errors double the delay until the cap', () => {
	assert.equal(nextStreamPollDelay(60000), 120000)
	assert.equal(nextStreamPollDelay(200000), STREAM_POLL_MAX_DELAY)
	assert.equal(nextStreamPollDelay(STREAM_POLL_MAX_DELAY), STREAM_POLL_MAX_DELAY)
})

test('HTTP fallback runs only when the socket is down', () => {
	assert.equal(usesHttpStreamFallback(true), false)
	assert.equal(usesHttpStreamFallback(false), true)
})

test('polling stops after five consecutive transient errors', () => {
	assert.equal(shouldStopAfterTransientErrors(4), false)
	assert.equal(shouldStopAfterTransientErrors(5), true)
	assert.equal(shouldStopAfterTransientErrors(6), true)
})

test('fallback polling resumes after websocket disconnect', () => {
	assert.equal(usesHttpStreamFallback(true), false, 'connected socket should not poll')
	assert.equal(usesHttpStreamFallback(false), true, 'disconnected socket should poll')
	assert.equal(isPermanentStreamPollError({status: 400}), false, '400 should keep fallback retrying')
	let delay = 60000
	for (let i = 0; i < 3; i += 1) {
		delay = nextStreamPollDelay(delay)
	}
	assert.equal(delay, STREAM_POLL_MAX_DELAY)
})

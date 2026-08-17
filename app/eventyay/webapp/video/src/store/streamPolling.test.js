/**
 * Stream polling backoff, visibility, and permanent-error helpers.
 * Run: node --test src/store/streamPolling.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import {
	STREAM_POLL_MAX_DELAY,
	httpErrorStatus,
	isAuthFailureError,
	isPermanentStreamPollError,
	nextStreamPollDelay,
	shouldStopAfterTransientErrors,
	usesHttpStreamFallback,
} from './streamPolling.js'

test('permanent errors stop polling on 400, 401, and 403', () => {
	for (const status of [400, 401, 403]) {
		assert.equal(isPermanentStreamPollError({status}), true)
	}
	assert.equal(isPermanentStreamPollError({status: 404}), false)
	assert.equal(isPermanentStreamPollError({status: 500}), false)
	assert.equal(isPermanentStreamPollError({}), false)
})

test('auth failures are 401 and 403', () => {
	assert.equal(isAuthFailureError({status: 401}), true)
	assert.equal(isAuthFailureError({response: {status: 403}}), true)
	assert.equal(isAuthFailureError({status: 404}), false)
	assert.equal(httpErrorStatus({response: {status: 403}}), 403)
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

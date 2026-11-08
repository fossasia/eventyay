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
	earliestFutureMs,
	secondsUntilStart,
	streamIsActive,
	keepLocalStreamOverEmptyServer,
	streamStartsInFuture,
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

test('a stream is active only inside its slot', () => {
	const nowMs = Date.parse('2026-10-21T12:00:00Z')
	const stream = {
		url: 'https://example.com/live',
		start_time: '2026-10-21T11:00:00Z',
		end_time: '2026-10-21T12:30:00Z',
	}
	assert.equal(streamIsActive(stream, nowMs), true)
	assert.equal(streamIsActive(stream, Date.parse('2026-10-21T12:30:00Z')), false)
	assert.equal(streamIsActive({...stream, start_time: '2026-10-21T12:05:00Z'}, nowMs), false)
	assert.equal(streamIsActive(null, nowMs), false)
})

test('the countdown reaches zero only at the start instant', () => {
	const start = '2026-10-21T12:00:10Z'
	const startMs = Date.parse(start)
	assert.equal(secondsUntilStart(start, startMs - 10000), 10)
	assert.equal(secondsUntilStart(start, startMs - 1), 1)
	assert.equal(secondsUntilStart(start, startMs), 0)
	assert.equal(secondsUntilStart(start, startMs + 500), 0)
	assert.equal(secondsUntilStart('not-a-date', startMs), null)
})

test('a cached empty response is ignored only just after the slot starts', () => {
	const nowMs = Date.parse('2026-10-21T12:00:10Z')
	const local = {
		url: 'https://example.com/live',
		start_time: '2026-10-21T12:00:00Z',
		end_time: '2026-10-21T12:30:00Z',
	}
	assert.equal(keepLocalStreamOverEmptyServer(local, null, nowMs), true)
	assert.equal(keepLocalStreamOverEmptyServer(local, null, Date.parse('2026-10-21T12:00:40Z')), false)
	assert.equal(keepLocalStreamOverEmptyServer({url: 'https://example.com/live'}, null, nowMs), false)
	assert.equal(keepLocalStreamOverEmptyServer(local, {url: 'https://example.com/other', start_time: '2026-10-21T12:00:00Z'}, nowMs), false)
})

test('a future stream is not treated as an expired one', () => {
	const nowMs = Date.parse('2026-10-21T12:00:00Z')
	const future = {start_time: '2026-10-21T12:00:10Z', end_time: '2026-10-21T12:10:00Z'}
	const expired = {start_time: '2026-10-21T11:00:00Z', end_time: '2026-10-21T11:30:00Z'}
	assert.equal(streamStartsInFuture(future, nowMs), true)
	assert.equal(streamIsActive(future, nowMs), false)
	assert.equal(streamStartsInFuture(expired, nowMs), false)
	assert.equal(streamIsActive(expired, nowMs), false)
})

test('the next boundary is the soonest future timestamp', () => {
	const nowMs = Date.parse('2026-10-21T12:00:00Z')
	assert.equal(earliestFutureMs(['2026-10-21T11:00:00Z', '2026-10-21T12:10:00Z'], nowMs), Date.parse('2026-10-21T12:10:00Z'))
	assert.equal(earliestFutureMs(['2026-10-21T11:00:00Z'], nowMs), null)
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

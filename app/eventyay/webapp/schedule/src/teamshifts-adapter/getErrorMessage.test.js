/**
 * Checks that TeamShifts error reasons reach the shift dialogs.
 * Run: node --test src/teamshifts-adapter/getErrorMessage.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { getErrorMessage } from './index.js'

function errorResponse (body, contentType, status = 400) {
	return new Response(body, { status, headers: { 'Content-Type': contentType } })
}

test('reads detail and error from JSON responses', async () => {
	assert.equal(await getErrorMessage(errorResponse('{"detail": "Role capacity has been reached."}', 'application/json')), 'Role capacity has been reached.')
	assert.equal(await getErrorMessage(errorResponse('{"error": "Invalid value"}', 'application/json')), 'Invalid value')
	assert.equal(await getErrorMessage(errorResponse('{"detail": ["Not a string"], "error": "Invalid value"}', 'application/json')), 'Invalid value')
})

test('reads plain-text error bodies', async () => {
	assert.equal(await getErrorMessage(errorResponse("'end' must be after 'start'.", 'text/html; charset=utf-8')), "'end' must be after 'start'.")
})

test('returns an empty string when there is no message to show', async () => {
	assert.equal(await getErrorMessage(errorResponse('', 'text/html')), '')
	assert.equal(await getErrorMessage(errorResponse('{"status": "error"}', 'application/json')), '')
	assert.equal(await getErrorMessage(errorResponse('{"detail": {"end": ["Invalid"]}, "error": " "}', 'application/json')), '')
	assert.equal(await getErrorMessage(errorResponse('<!doctype html><title>Not Found</title>', 'text/html')), '')
})

test('does not show server errors or long plain-text bodies', async () => {
	assert.equal(await getErrorMessage(errorResponse('Traceback (most recent call last):\n  File "views.py"', 'text/plain', 500)), '')
	assert.equal(await getErrorMessage(errorResponse('Bad Gateway', 'text/plain', 502)), '')
	assert.equal(await getErrorMessage(errorResponse('{"detail": "Internal error: relation does not exist"}', 'application/json', 500)), '')
	assert.equal(await getErrorMessage(errorResponse('x'.repeat(301), 'text/plain')), '')
	assert.equal(await getErrorMessage(errorResponse(JSON.stringify({ detail: 'x'.repeat(301) }), 'application/json')), '')
	assert.equal(await getErrorMessage(undefined), '')
})

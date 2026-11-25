/**
 * Run: node --test src/lib/chatErrors.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import ApiError from './ApiError.js'
import { chatErrorMessage } from './chatErrors.js'

const t = key => key

test('chatErrorMessage explains an empty message', () => {
	assert.equal(chatErrorMessage(new ApiError({code: 'chat.empty'}), t), 'You cannot send an empty message.')
})

test('chatErrorMessage names the denied action', () => {
	const denied = new ApiError({code: 'chat.denied'})
	assert.equal(chatErrorMessage(denied, t), 'You are not allowed to send messages here.')
	assert.equal(chatErrorMessage(denied, t, 'edit'), 'You are not allowed to edit this message.')
	assert.equal(chatErrorMessage(denied, t, 'delete'), 'You are not allowed to delete this message.')
	assert.equal(chatErrorMessage(new ApiError({code: 'protocol.denied'}), t, 'edit'), 'You are not allowed to edit this message.')
})

test('chatErrorMessage falls back for timeouts, disconnects and unknown codes', () => {
	assert.equal(chatErrorMessage(new Error('call timed out'), t), 'Your message could not be sent. Please try again.')
	assert.equal(chatErrorMessage(new ApiError({code: 'something.else'}), t, 'edit'), 'Your changes could not be saved. Please try again.')
	assert.equal(chatErrorMessage(undefined, t, 'delete'), 'The message could not be deleted. Please try again.')
})

test('chatErrorMessage passes keys through the translation function', () => {
	assert.equal(chatErrorMessage(new ApiError({code: 'chat.empty'}), key => `x:${key}`), 'x:You cannot send an empty message.')
})

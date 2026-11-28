/**
 * Run: node --test src/lib/roomInteractions.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import ApiError from './ApiError.js'
import {
	MAX_QUESTION_LENGTH,
	canSubmitQuestion,
	isQuestionTooLong,
	normalizeQuestion,
	questionLength,
	roomInteractionErrorMessage,
} from './roomInteractions.js'

const t = key => key

test('normalizeQuestion trims whitespace and tolerates non-strings', () => {
	assert.equal(normalizeQuestion('  Why?\n'), 'Why?')
	assert.equal(normalizeQuestion(''), '')
	assert.equal(normalizeQuestion(undefined), '')
	assert.equal(normalizeQuestion(null), '')
})

test('blank or whitespace-only questions cannot be submitted', () => {
	assert.equal(canSubmitQuestion('', false), false)
	assert.equal(canSubmitQuestion('   \n\t', false), false)
	assert.equal(canSubmitQuestion('Why?', false), true)
})

test('questions cannot be submitted twice while a request is running', () => {
	assert.equal(canSubmitQuestion('Why?', true), false)
})

test('questions longer than the limit cannot be submitted', () => {
	assert.equal(canSubmitQuestion('a'.repeat(MAX_QUESTION_LENGTH), false), true)
	assert.equal(canSubmitQuestion('a'.repeat(MAX_QUESTION_LENGTH + 1), false), false)
	assert.equal(canSubmitQuestion(` ${'a'.repeat(MAX_QUESTION_LENGTH)} `, false), true)
})

test('length is counted in code points, like the server', () => {
	const emoji = '\u{1F600}'
	assert.equal(questionLength(`a${emoji}`), 2)
	const atLimit = 'a'.repeat(MAX_QUESTION_LENGTH - 1) + emoji
	assert.equal(atLimit.length, MAX_QUESTION_LENGTH + 1)
	assert.equal(isQuestionTooLong(atLimit), false)
	assert.equal(canSubmitQuestion(atLimit, false), true)
	const overLimit = 'a'.repeat(MAX_QUESTION_LENGTH) + emoji
	assert.equal(isQuestionTooLong(overLimit), true)
	assert.equal(canSubmitQuestion(overLimit, false), false)
})

test('server error codes map to readable messages', () => {
	const cases = {
		'question.empty': 'Please enter a question.',
		'question.too_long': 'Your question is too long.',
		'question.inactive': 'Questions are currently disabled.',
		'question.unknown': 'This question no longer exists.',
		'poll.inactive': 'Polls are currently disabled.',
		'poll.closed': 'This poll is no longer open for voting.',
		'poll.unknown_option': 'This option is no longer available.',
		'protocol.denied': 'You are not allowed to do this.',
	}
	for (const [code, message] of Object.entries(cases)) {
		assert.equal(roomInteractionErrorMessage(new ApiError({code}), t), message)
	}
})

test('unknown codes, timeouts and missing errors fall back to a generic message', () => {
	const fallback = 'Something went wrong. Please try again.'
	assert.equal(roomInteractionErrorMessage(new ApiError({code: 'command.error'}), t), fallback)
	assert.equal(roomInteractionErrorMessage(new Error('call timed out'), t), fallback)
	assert.equal(roomInteractionErrorMessage(undefined, t), fallback)
})

test('messages go through the translation function', () => {
	const upper = key => key.toUpperCase()
	assert.equal(roomInteractionErrorMessage(new ApiError({code: 'poll.closed'}), upper), 'THIS POLL IS NO LONGER OPEN FOR VOTING.')
})

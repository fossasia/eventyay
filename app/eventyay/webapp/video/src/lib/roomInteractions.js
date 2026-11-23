// Keep in sync with MAX_QUESTION_LENGTH in eventyay/features/live/modules/question.py
export const MAX_QUESTION_LENGTH = 1000

export function normalizeQuestion(text) {
	return typeof text === 'string' ? text.trim() : ''
}

/**
 * Length in Unicode code points, the way the server counts it (Python `len`).
 * `String.length` counts UTF-16 code units, so an emoji would count twice.
 */
export function questionLength(text) {
	return [...normalizeQuestion(text)].length
}

export function isQuestionTooLong(text) {
	return questionLength(text) > MAX_QUESTION_LENGTH
}

export function canSubmitQuestion(text, isSubmitting) {
	return !isSubmitting && questionLength(text) > 0 && !isQuestionTooLong(text)
}

/**
 * User-facing message for a failed question, poll or moderation call.
 *
 * @param {Error} error rejection from `api.call`; `ApiError` carries the server's `{code, message}` in `apiError`
 * @param {(key: string) => string} t translation function
 */
export function roomInteractionErrorMessage(error, t) {
	switch (error?.apiError?.code) {
		case 'question.empty':
			return t('Please enter a question.')
		case 'question.too_long':
			return t('Your question is too long.')
		case 'question.inactive':
			return t('Questions are currently disabled.')
		case 'question.unknown':
			return t('This question no longer exists.')
		case 'poll.inactive':
			return t('Polls are currently disabled.')
		case 'poll.closed':
			return t('This poll is no longer open for voting.')
		case 'poll.unknown_option':
			return t('This option is no longer available.')
		case 'protocol.denied':
			return t('You are not allowed to do this.')
		default:
			return t('Something went wrong. Please try again.')
	}
}

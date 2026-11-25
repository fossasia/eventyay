const DENIED = {
	send: 'You are not allowed to send messages here.',
	edit: 'You are not allowed to edit this message.',
	delete: 'You are not allowed to delete this message.',
}

const FAILED = {
	send: 'Your message could not be sent. Please try again.',
	edit: 'Your changes could not be saved. Please try again.',
	delete: 'The message could not be deleted. Please try again.',
}

/**
 * User-facing message for a failed `chat.send` call.
 *
 * @param {Error} error rejection from `api.call`; `ApiError` carries the server's `{code, message}` in `apiError`
 * @param {(key: string) => string} t translation function
 * @param {'send'|'edit'|'delete'} action what the call was doing
 */
export function chatErrorMessage(error, t, action = 'send') {
	switch (error?.apiError?.code) {
		case 'chat.empty':
			return t('You cannot send an empty message.')
		case 'chat.denied':
		case 'protocol.denied':
			return t(DENIED[action] || DENIED.send)
		default:
			return t(FAILED[action] || FAILED.send)
	}
}

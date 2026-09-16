import {translate} from 'i18n'

// Function to get the display name of a user
export function getUserName(user) {
	// Return a localized string if the user is deleted
	if (user.deleted) return translate('Deleted User')

	// Return the display name if available, otherwise return the sender or a default string
	return user.profile?.display_name ?? user.sender ?? translate('Unknown user')
}

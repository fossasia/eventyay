import { apiErrorDetail, interpretationApiUrl, interpretationAuthHeaders } from 'lib/interpretation-api'
import { normalizeYoutubeVideoId } from 'lib/validators'

export async function fetchInterpretationLanguageStreams(store, roomId) {
	const response = await fetch(interpretationApiUrl(store, roomId, 'streams/'), {
		headers: interpretationAuthHeaders(),
		credentials: 'include',
	})
	const data = await response.json().catch(() => ({}))
	if (!response.ok) {
		throw new Error(apiErrorDetail(data) || 'Could not load interpretation language streams')
	}
	return data
}

export async function saveInterpretationLanguageStreams(store, roomId, languageStreams) {
	const response = await fetch(interpretationApiUrl(store, roomId, 'config/'), {
		method: 'PATCH',
		headers: interpretationAuthHeaders(true),
		credentials: 'include',
		body: JSON.stringify({ language_streams: languageStreams }),
	})
	const data = await response.json().catch(() => ({}))
	if (!response.ok) {
		throw new Error(apiErrorDetail(data) || 'Could not save interpretation language streams')
	}
	return data
}

export function cloneLanguageStreamEntries(entries) {
	return JSON.parse(JSON.stringify(entries || []))
}

export function normalizeLanguageStreamEntry(entry) {
	if (!entry?.youtube_id) return
	const id = normalizeYoutubeVideoId(entry.youtube_id)
	if (id) entry.youtube_id = id
}

export function defaultLanguageStreamEntry() {
	return { language: '', youtube_id: '', use_video: false }
}

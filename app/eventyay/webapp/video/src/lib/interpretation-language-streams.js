import { apiErrorDetail, interpretationApiUrl, interpretationAuthHeaders } from './interpretation-api.js'
import { normalizeYoutubeVideoId } from './validators.js'

export async function fetchInterpretationLanguageStreams(store, roomId) {
	const response = await fetch(interpretationApiUrl(store, roomId, 'streams/'), {
		headers: await interpretationAuthHeaders(),
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
		headers: await interpretationAuthHeaders(true),
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
	if (!entry) return
	const raw = (entry.url || entry.youtube_id || '').trim()
	if (!raw) return
	const ytId = normalizeYoutubeVideoId(raw)
	if (ytId) {
		entry.url = ytId
		entry.youtube_id = ytId
	} else {
		entry.url = raw
		entry.youtube_id = raw
	}
}

export function defaultLanguageStreamEntry() {
	return { language: '', url: '', youtube_id: '', use_video: false }
}

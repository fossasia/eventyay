import ISO6391 from 'iso-639-1'
import { apiErrorDetail, interpretationApiUrl, interpretationAuthHeaders } from './interpretation-api.js'
import { logOperational } from './operationalLog.js'
import { normalizeYoutubeVideoId, toYoutubeWatchUrl } from './validators.js'

export async function fetchInterpretationLanguageStreams(store, roomId) {
	const url = interpretationApiUrl(store, roomId, 'streams/')
	if (!url) {
		throw new Error('Interpretation API route unavailable')
	}
	const response = await fetch(url, {
		headers: await interpretationAuthHeaders(),
		credentials: 'include',
	})
	if (response.status === 404) {
		return { unsupported: true, use_plugin_language_streams: false, language_streams: [] }
	}
	const data = await response.json().catch(() => ({}))
	if (!response.ok) {
		logOperational({action: 'interpretation.config', outcome: 'failure', backend: 'interpretation', error_code: 'http_error', status: response.status})
		throw new Error(apiErrorDetail(data) || 'Could not load interpretation language streams')
	}
	return data
}

export async function saveInterpretationLanguageStreams(store, roomId, languageStreams) {
	const url = interpretationApiUrl(store, roomId, 'config/')
	if (!url) {
		throw new Error('Could not save interpretation language streams: missing routing parameters')
	}
	const response = await fetch(url, {
		method: 'PATCH',
		headers: await interpretationAuthHeaders(true),
		credentials: 'include',
		body: JSON.stringify({
			language_streams: (languageStreams || []).map(serializeLanguageStreamEntry),
		}),
	})
	const data = await response.json().catch(() => ({}))
	if (!response.ok) {
		logOperational({action: 'interpretation.config', outcome: 'failure', backend: 'interpretation', error_code: 'save_failed', status: response.status})
		throw new Error(apiErrorDetail(data) || 'Could not save interpretation language streams')
	}
	return data
}

export function cloneLanguageStreamEntries(entries) {
	return JSON.parse(JSON.stringify(entries || [])).map((entry) => {
		normalizeLanguageStreamEntry(entry)
		return entry
	})
}

export function serializeLanguageStreamEntry(entry) {
	if (!entry || typeof entry !== 'object') return entry
	const copy = { ...entry }
	const raw = [copy.url, copy.youtube_id]
		.map((value) => (value || '').trim())
		.find(Boolean) || ''
	if (!raw) {
		copy.url = ''
		copy.youtube_id = ''
		return copy
	}
	const ytId = normalizeYoutubeVideoId(raw)
	if (ytId) {
		copy.url = ytId
		copy.youtube_id = ytId
	} else {
		copy.url = raw
		copy.youtube_id = raw
	}
	return copy
}

export function normalizeLanguageStreamEntry(entry) {
	if (!entry) return
	const raw = [entry.url, entry.youtube_id]
		.map((value) => (value || '').trim())
		.find(Boolean) || ''
	if (!raw) {
		entry.url = ''
		if (entry.youtube_id == null) entry.youtube_id = ''
		return
	}
	const ytId = normalizeYoutubeVideoId(raw)
	if (ytId) {
		entry.youtube_id = ytId
		entry.url = toYoutubeWatchUrl(raw)
	} else {
		entry.url = raw
		entry.youtube_id = raw
	}
}

export function defaultLanguageStreamEntry() {
	return { language: '', url: '', youtube_id: '', use_video: false }
}

export function getWhepUrlForLanguage(language, fallbackEntries = []) {
	if (!language || typeof language !== 'string') return ''
	const rawLang = language.trim()
	if (!rawLang) return ''

	const langName = rawLang.toLowerCase()
	let langCode = (ISO6391.getCode(rawLang) || '').toLowerCase()
	if (!langCode && rawLang.length <= 3) {
		langCode = rawLang.toLowerCase()
	}

	if (!Array.isArray(fallbackEntries) || fallbackEntries.length === 0) {
		return ''
	}

	// Only return a WHEP URL if an active booth exists in fallbackEntries for this language.
	// If no booth exists yet, leave it empty so the URL is populated only after save creates the booth.
	for (const entry of fallbackEntries) {
		if (!entry || typeof entry !== 'object') continue
		const entryLang = (entry.language || '').trim().toLowerCase()
		let entryCode = (ISO6391.getCode(entry.language) || entry.language_code || '').toLowerCase()
		if (!entryCode && (entry.language || '').trim().length <= 3) {
			entryCode = (entry.language || '').trim().toLowerCase()
		}
		const entryUrl = (entry.url || entry.youtube_id || '').trim()
		if (!entryUrl) continue

		if (entryUrl.includes('/whep') && (entryLang === langName || (langCode && entryCode === langCode))) {
			return entryUrl
		}
	}

	return ''
}

export async function syncInterpretationServices(store, roomId) {
	const url = interpretationApiUrl(store, roomId, 'sync/')
	if (!url) {
		throw new Error('Could not sync interpretation services: missing routing parameters')
	}
	const response = await fetch(url, {
		method: 'POST',
		headers: await interpretationAuthHeaders(),
		credentials: 'include',
	})
	const data = await response.json().catch(() => ({}))
	if (!response.ok) {
		logOperational({action: 'interpretation.config', outcome: 'failure', backend: 'interpretation', error_code: 'sync_failed', status: response.status})
		throw new Error(apiErrorDetail(data) || 'Could not sync interpretation services')
	}
	return data
}

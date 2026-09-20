import {
	isUsableAudioTranslationEntry,
	normalizeAudioTranslationSource,
	normalizeYoutubeVideoId
} from './lib/validators.js'

const ORIGINAL_LANGUAGE = 'Original'

export function roomUsesPluginLanguageStreams(room) {
	return Boolean(room?.interpretation_use_plugin_streams)
}

function ensureOriginalLanguageEntry(languages) {
	const list = Array.isArray(languages) ? [...languages] : []
	if (!list.some(entry => entry?.language === ORIGINAL_LANGUAGE)) {
		list.unshift({ language: ORIGINAL_LANGUAGE, url: null, youtube_id: null, use_video: false })
	}
	return list
}

export function pluginLanguageStreams(room) {
	if (!roomUsesPluginLanguageStreams(room)) {
		return []
	}
	const streams = room?.interpretation_language_streams
	if (!Array.isArray(streams)) {
		return ensureOriginalLanguageEntry([])
	}
	// Keep caption-only rows (e.g. Original floor WS) even without WHEP audio.
	const usable = streams.filter(entry => {
		if (!entry?.language) return false
		if (entry.caption_ws_url) return true
		return isUsableAudioTranslationEntry(entry)
	})

	// Product rule: a language is offered once, either a human booth or the AI
	// voice, never both. When the backend sends both, the human interpreter wins,
	// and a caption-only row never hides a stream that carries audio.
	// The dropdown and the stored selection are keyed by language, so offering the
	// same language twice would first need a distinct selection identity per stream.
	const byLanguage = new Map()
	for (const entry of usable) {
		const key = languageKey(entry)
		const existing = byLanguage.get(key)
		if (!existing || streamRank(entry) > streamRank(existing)) {
			byLanguage.set(key, entry)
		}
	}

	return ensureOriginalLanguageEntry(Array.from(byLanguage.values()))
}

// Entries for one language can differ in spelling ("German" / "german ") but share a code.
function languageKey(entry) {
	return String(entry.language_code || entry.language || '').trim().toLowerCase()
}

/**
 * Add the VoxBento listener token to a caption or TTS WebSocket URL. VoxBento
 * needs it to accept the connection when booth access is protected.
 */
export function withListenerToken(url, token) {
	if (!url || !token) return url
	return `${url}${url.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}`
}

/**
 * Classify a language stream entry as 'ai' (VoxBento TTS over WebSocket),
 * 'human' (interpreter booth over WHEP) or null (YouTube or no audio).
 *
 * The interpretation plugin sends a booth's WHEP URL in `youtube_id`, so a
 * non-YouTube URL there counts as a human booth too.
 */
export function interpretationStreamType(entry) {
	if (!entry) return null
	if (entry.stream_type === 'ai' || entry.tts_ws_url) return 'ai'
	if (entry.stream_type === 'human' || entry.whep_url || entry.whip_url) return 'human'
	const source = entry.url || entry.youtube_id
	if (source && !normalizeYoutubeVideoId(source) && normalizeAudioTranslationSource(source)) return 'human'
	return null
}

// Human booth beats AI voice, and both beat a caption-only row.
function streamRank(entry) {
	const type = interpretationStreamType(entry)
	if (type === 'human') return 2
	if (type === 'ai') return 1
	return 0
}

export function firstCaptionLanguage(languages) {
	const list = Array.isArray(languages) ? languages : []
	const withCaptions = list.filter(entry => entry?.caption_ws_url)
	const nonOriginal = withCaptions.find(entry => entry.language !== ORIGINAL_LANGUAGE)
	return (nonOriginal || withCaptions[0] || list[0])?.language || ORIGINAL_LANGUAGE
}

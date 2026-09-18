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
	const usable = Array.isArray(streams)
		? streams.filter(entry => isUsableAudioTranslationEntry(entry))
		: []

	// Product rule: a language is offered once, either a human booth or the AI
	// voice, never both. When the backend sends both, the human interpreter wins.
	// The dropdown and the stored selection are keyed by language, so offering the
	// same language twice would first need a distinct selection identity per stream.
	const byLanguage = new Map()
	for (const entry of usable) {
		const existing = byLanguage.get(entry.language)
		if (!existing || (!isHumanStream(existing) && isHumanStream(entry))) {
			byLanguage.set(entry.language, entry)
		}
	}

	return ensureOriginalLanguageEntry(Array.from(byLanguage.values()))
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

function isHumanStream(entry) {
	return interpretationStreamType(entry) === 'human'
}

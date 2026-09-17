import { isUsableAudioTranslationEntry } from './lib/validators.js'

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

	// A language is offered once: either a human booth or the AI voice, never both.
	// When the backend sends both, the human interpreter wins.
	const byLanguage = new Map()
	for (const entry of usable) {
		const existing = byLanguage.get(entry.language)
		if (!existing || (!isHumanStream(existing) && isHumanStream(entry))) {
			byLanguage.set(entry.language, entry)
		}
	}

	return ensureOriginalLanguageEntry(Array.from(byLanguage.values()))
}

function isHumanStream(entry) {
	return Boolean(entry?.whep_url || entry?.whip_url)
}

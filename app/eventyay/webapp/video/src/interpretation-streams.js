import { isUsableAudioTranslationEntry } from 'lib/validators'

const ORIGINAL_LANGUAGE = 'Original'

export function roomUsesPluginLanguageStreams(room) {
	return Boolean(room?.interpretation_use_plugin_streams)
}

function ensureOriginalLanguageEntry(languages) {
	const list = Array.isArray(languages) ? [...languages] : []
	if (!list.some(entry => entry?.language === ORIGINAL_LANGUAGE)) {
		list.unshift({ language: ORIGINAL_LANGUAGE, youtube_id: null, use_video: false })
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
	return ensureOriginalLanguageEntry(usable)
}

import { isUsableAudioTranslationEntry } from './lib/validators.js'

const ORIGINAL_LANGUAGE = 'Original'

export function roomUsesPluginLanguageStreams(room) {
	if (room?.interpretation_use_plugin_streams) return true
	const scheduleStreams = room?.currentStream?.config?.language_streams
		|| room?.currentStream?.config?.languageUrls
		|| room?.currentStream?.language_streams
	return Array.isArray(scheduleStreams) && scheduleStreams.length > 0
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
	const scheduleStreams = room?.currentStream?.config?.language_streams
		|| room?.currentStream?.config?.languageUrls
		|| room?.currentStream?.language_streams
	const streams = (Array.isArray(scheduleStreams) && scheduleStreams.length > 0)
		? scheduleStreams
		: room?.interpretation_language_streams
	if (!Array.isArray(streams)) {
		return ensureOriginalLanguageEntry([])
	}
	// Keep caption-only rows (e.g. Original floor WS) even without WHEP audio.
	const usable = streams.filter(entry => {
		if (!entry?.language) return false
		if (entry.caption_ws_url) return true
		return isUsableAudioTranslationEntry(entry)
	})
	return ensureOriginalLanguageEntry(usable)
}

export function firstCaptionLanguage(languages) {
	const list = Array.isArray(languages) ? languages : []
	const withCaptions = list.filter(entry => entry?.caption_ws_url)
	const nonOriginal = withCaptions.find(entry => entry.language !== ORIGINAL_LANGUAGE)
	return (nonOriginal || withCaptions[0] || list[0])?.language || ORIGINAL_LANGUAGE
}

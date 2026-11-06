import { normalizeAudioTranslationSource } from './lib/validators.js'

const ORIGINAL_LANGUAGE = 'Original'

export function isUsableLanguageStreamEntry(entry) {
	if (!entry?.language) return false
	if (entry.caption_ws_url) return true
	if (entry.language === ORIGINAL_LANGUAGE) return true
	return Boolean(interpretationAudioSource(entry))
}

export function interpretationAudioSource(entry) {
	return normalizeAudioTranslationSource(
		entry?.tts_ws_url
		|| entry?.whep_url
		|| entry?.whip_url
		|| entry?.url
		|| entry?.youtube_id
	)
}

export function interpretationStreamKind(entry) {
	if (!entry || entry.language === ORIGINAL_LANGUAGE) return null
	return entry.tts_ws_url ? 'AI' : 'Human'
}

export function roomUsesPluginLanguageStreams(room) {
	return Boolean(room?.interpretation_use_plugin_streams)
}

function ensureOriginalLanguageEntry(languages, originalCaptionUrl) {
	const list = Array.isArray(languages) ? [...languages] : []
	if (!list.some(entry => entry?.language === ORIGINAL_LANGUAGE)) {
		list.unshift({
			language: ORIGINAL_LANGUAGE, url: null, youtube_id: null, use_video: false,
			...(originalCaptionUrl ? { caption_ws_url: originalCaptionUrl } : {}),
		})
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
	const usableScheduleStreams = Array.isArray(scheduleStreams)
		? scheduleStreams.filter(isUsableLanguageStreamEntry)
		: []
	const streams = usableScheduleStreams.length > 0
		? usableScheduleStreams
		: room?.interpretation_language_streams
	if (!Array.isArray(streams)) {
		return ensureOriginalLanguageEntry([])
	}
	const roomStreams = Array.isArray(room?.interpretation_language_streams)
		? room.interpretation_language_streams
		: []
	const usable = streams.filter(isUsableLanguageStreamEntry).map(entry => {
		const captionUrl = entry.caption_ws_url
			|| roomStreams.find(roomEntry => roomEntry?.language === entry.language)?.caption_ws_url
		return captionUrl ? { ...entry, caption_ws_url: captionUrl } : entry
	})
	const originalCaptionUrl = roomStreams.find(entry => entry?.language === ORIGINAL_LANGUAGE)?.caption_ws_url
	return ensureOriginalLanguageEntry(usable, originalCaptionUrl)
}

export function firstCaptionLanguage(languages) {
	const list = Array.isArray(languages) ? languages : []
	const withCaptions = list.filter(entry => entry?.caption_ws_url)
	const nonOriginal = withCaptions.find(entry => entry.language !== ORIGINAL_LANGUAGE)
	return (nonOriginal || withCaptions[0] || list[0])?.language || ORIGINAL_LANGUAGE
}

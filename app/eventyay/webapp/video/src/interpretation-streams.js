import ISO6391 from 'iso-639-1'
import { isUsableAudioTranslationEntry } from './lib/validators.js'

const ORIGINAL_LANGUAGE = 'Original'

export function isUsableLanguageStreamEntry(entry) {
	if (!entry?.language) return false
	if (entry.caption_ws_url) return true
	return isUsableAudioTranslationEntry(entry)
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

function getScheduleConfig(schedule) {
	if (!schedule?.config) return null
	if (typeof schedule.config === 'string') {
		try {
			return JSON.parse(schedule.config)
		} catch (e) {
			return null
		}
	}
	return schedule.config
}

export function pluginLanguageStreams(room) {
	if (!roomUsesPluginLanguageStreams(room)) {
		return []
	}
	const activeOrUpcomingSchedule = room?.currentStream || room?.upcomingStream
	const config = getScheduleConfig(activeOrUpcomingSchedule)
	const scheduleStreams = config?.language_streams
		|| config?.languageUrls
		|| activeOrUpcomingSchedule?.language_streams
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
	const originalCaptionUrl = roomStreams.find(entry => entry?.language === ORIGINAL_LANGUAGE)?.caption_ws_url
	const usable = streams.filter(isUsableLanguageStreamEntry).map(entry => {
		let captionUrl = entry.caption_ws_url
			|| roomStreams.find(roomEntry => roomEntry?.language === entry.language)?.caption_ws_url
		if (!captionUrl && originalCaptionUrl && entry.language && entry.language !== ORIGINAL_LANGUAGE) {
			const langCode = (ISO6391.getCode(entry.language) || entry.language_code || entry.language).toLowerCase()
			const floorRegex = /([/-])floor(\?.*)?$/
			if (floorRegex.test(originalCaptionUrl)) {
				captionUrl = originalCaptionUrl.replace(floorRegex, `$1${langCode}$2`)
			}
		}
		return captionUrl ? { ...entry, caption_ws_url: captionUrl } : entry
	})
	return ensureOriginalLanguageEntry(usable, originalCaptionUrl)
}

export function firstCaptionLanguage(languages) {
	const list = Array.isArray(languages) ? languages : []
	const withCaptions = list.filter(entry => entry?.caption_ws_url)
	const nonOriginal = withCaptions.find(entry => entry.language !== ORIGINAL_LANGUAGE)
	return (nonOriginal || withCaptions[0] || list[0])?.language || ORIGINAL_LANGUAGE
}

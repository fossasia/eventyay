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
			console.warn('Failed to parse schedule config JSON:', schedule.id, e)
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
		? scheduleStreams.filter(isUsableAudioTranslationEntry)
		: []
	const fromSchedule = usableScheduleStreams.length > 0
	const streams = fromSchedule
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
		// Schedule configurations must not inject arbitrary caption WebSocket URLs
		let captionUrl = fromSchedule
			? roomStreams.find(roomEntry => roomEntry?.language === entry.language)?.caption_ws_url
			: (entry.caption_ws_url || roomStreams.find(roomEntry => roomEntry?.language === entry.language)?.caption_ws_url)
		if (
			!captionUrl &&
			(!fromSchedule ? (entry.caption_ws_url !== '' && entry.caption_ws_url !== false) : true) &&
			originalCaptionUrl &&
			typeof entry.language === 'string' &&
			entry.language.trim() &&
			entry.language !== ORIGINAL_LANGUAGE
		) {
			const rawLang = entry.language.trim()
			const code = ISO6391.getCode(rawLang)
				|| (typeof entry.language_code === 'string' ? entry.language_code.trim() : null)
				|| rawLang
			const langCode = typeof code === 'string' ? code.toLowerCase() : ''
			const floorRegex = /([/-])floor(\?.*)?$/
			if (langCode && floorRegex.test(originalCaptionUrl)) {
				captionUrl = originalCaptionUrl.replace(floorRegex, `$1${langCode}$2`)
			}
		}
		const baseEntry = { ...entry }
		if (fromSchedule) {
			delete baseEntry.caption_ws_url
			baseEntry.is_schedule_stream = true
		}
		return captionUrl ? { ...baseEntry, caption_ws_url: captionUrl } : baseEntry
	})
	return ensureOriginalLanguageEntry(usable, originalCaptionUrl)
}

export function firstCaptionLanguage(languages) {
	const list = Array.isArray(languages) ? languages : []
	const withCaptions = list.filter(entry => entry?.caption_ws_url)
	const nonOriginal = withCaptions.find(entry => entry.language !== ORIGINAL_LANGUAGE)
	return (nonOriginal || withCaptions[0] || list[0])?.language || ORIGINAL_LANGUAGE
}

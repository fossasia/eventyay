import moment from 'moment-timezone'

export function getLocalizedString (string) {
	if (!string) return ''
	if (typeof string === 'string') return string
	const lang = document.querySelector('html').lang || 'en'
	return string[lang] || string.en || Object.values(string)[0] || ''
}

export function getSessionTypeLabel (sessionType) {
	if (!sessionType) return ''
	if (typeof sessionType === 'string') return sessionType
	if (typeof sessionType === 'object') {
		const localized = getLocalizedString(sessionType)
		if (typeof localized === 'string' && localized.length) return localized
		const firstTextValue = Object.values(sessionType).find(v => typeof v === 'string' && v.length)
		if (firstTextValue) return firstTextValue
	}
	return ''
}

const checkPropScrolling = (node, prop) => ['auto', 'scroll'].includes(getComputedStyle(node, null).getPropertyValue(prop))
const isScrolling = node => checkPropScrolling(node, 'overflow') || checkPropScrolling(node, 'overflow-x') || checkPropScrolling(node, 'overflow-y')
export function findScrollParent (node) {
	if (!node || node === document.body) return
	if (isScrolling(node)) return node
	return findScrollParent(node.parentNode)
}
export function getPrettyDuration (start, end) {
	let minutes = end.diff(start, 'minutes')
	if (minutes <= 60) {
		return `${minutes}min`
	}
	const hours = Math.floor(minutes / 60)
	minutes = minutes % 60
	if (minutes) {
		return `${hours}h${minutes}min`
	}
	return `${hours}h`
}

export function getSessionTime(session, timezone, locale, hasAmPm) {
	const startInZone = session.start.clone().tz(timezone)
	if (hasAmPm) {
		return {
			time: startInZone.format('h:mm'),
			ampm: startInZone.format('A')
		}
	} else {
		return {
			time: startInZone.format('LT')
		}
	}
}

export function isProperSession(session) {
	return !!session.id
}

export function getContrastColor(bgColor) {
	if (!bgColor) return ''
	bgColor = bgColor.replace('#', '')
	const r = parseInt(bgColor.slice(0, 2), 16)
	const g = parseInt(bgColor.slice(2, 4), 16)
	const b = parseInt(bgColor.slice(4, 6), 16)
	const brightness = (r * 299 + g * 587 + b * 114) / 1000
	return brightness > 128 ? 'black' : 'white'
}

export function getIconByFileEnding(url) {
	if (!url) return 'file-download-outline'
	const path = url.split(/[?#]/)[0].toLowerCase()
	if (/\.pdf$/.test(path)) return 'link'
	if (/\.xlsx?$/.test(path)) return 'file-excel-outline'
	if (/\.docx?$/.test(path)) return 'file-word-outline'
	if (/\.pptx?$/.test(path)) return 'file-powerpoint-outline'
	if (/\.(mp3|ogg|wav|flac)$/.test(path)) return 'file-music-outline'
	if (/\.(jpe?g|png|tiff)$/.test(path)) return 'file-image-outline'
	if (/(\.(mp4|mov|webm|avi)$)|\/\/(youtube\.com|youtu\.be|vimeo\.com)\//.test(path)) return 'file-video-outline'
	return 'file-download-outline'
}

export function computeTalkExporters(baseUrl, code) {
	const base = baseUrl ? baseUrl.replace(/\/?$/, '/') : '/'
	return {
		ics: `${base}talk/${code}.ics`,
		json: `${base}talk/${code}.json`,
		xml: `${base}talk/${code}.xml`,
		xcal: `${base}talk/${code}.xcal`,
		google_calendar: `${base}talk/${code}/export/google-calendar`,
		webcal: `${base}talk/${code}/export/webcal`,
	}
}

export function computeSpeakerExporters(speakerBaseUrl) {
	const base = speakerBaseUrl ? speakerBaseUrl.replace(/\/?$/, '') : ''
	return {
		ics: `${base}/talks.ics`,
		json: `${base}/talks.json`,
		xml: `${base}/talks.xml`,
		xcal: `${base}/talks.xcal`,
		google_calendar: `${base}/talks/export/google-calendar`,
		webcal: `${base}/talks/export/webcal`,
	}
}

export function buildExportMenuItems(exporters) {
	if (!exporters) return []
	const qr = exporters.qrcodes || {}
	return [
		{ id: 'google_calendar', label: 'Add to Google Calendar', url: exporters.google_calendar, icon: 'fa-google', qrcode_svg: qr.google_calendar },
		{ id: 'webcal', label: 'Add to Other Calendar', url: exporters.webcal, icon: 'fa-calendar', qrcode_svg: qr.webcal },
		{ id: 'ics', label: 'iCal', url: exporters.ics, icon: 'fa-calendar', qrcode_svg: qr.ics },
		{ id: 'json', label: 'JSON (frab compatible)', url: exporters.json, icon: 'fa-code', qrcode_svg: qr.json },
		{ id: 'xml', label: 'XML (frab compatible)', url: exporters.xml, icon: 'fa-code', qrcode_svg: qr.xml },
		{ id: 'xcal', label: 'XCal (frab compatible)', url: exporters.xcal, icon: 'fa-calendar', qrcode_svg: qr.xcal },
	].filter(o => o.url)
}

export function areScheduleExportsDisabled ({ version = '', scheduleMetaVersion = '', isFeaturedPage = false, exportersCount = 0, isWipPreview = false, scheduleExportsDisabled = false } = {}) {
	if (scheduleExportsDisabled) return true
	if (isWipPreview || (version || scheduleMetaVersion) === 'wip') return true
	if (isFeaturedPage && !exportersCount) return true
	return false
}

export function parseBooleanAnswer (value) {
	if (typeof value === 'boolean') return value
	return ['true', '1', 'yes'].includes(String(value).toLowerCase())
}

export function resolveAbsoluteUrl (url, eventUrl = '') {
	if (!url) return url
	if (/^https?:\/\//i.test(url)) return url
	try {
		const origin = new URL(eventUrl || '/', window.location.origin).origin
		return new URL(url, origin).href
	} catch {
		return url
	}
}

export function buildQrcodesUrl (eventUrl, kind, code) {
	if (!eventUrl || !code) return ''
	const base = eventUrl.replace(/\/?$/, '/')
	return `${base}schedule/widgets/qrcodes/${kind}/${code}.json`
}

export function normalizePopularityCount (session) {
	const value = Number(
		session?.fav_count
		?? session?.favorite_count
		?? session?.favourites_count
		?? session?.stars
		?? 0
	)
	return Number.isFinite(value) ? value : 0
}

export function isPopularityFeatureEnabled (flags = {}) {
	return !!flags.session_popularity_enabled
}

export function isPopularityVisibleOnSchedule ({ flags = {} } = {}) {
	if (!isPopularityFeatureEnabled(flags)) return false
	if ('session_popularity_show_on_schedule' in flags) {
		return !!flags.session_popularity_show_on_schedule
	}
	return !!(flags.session_popularity_show_on_calendar || flags.session_popularity_show_on_list)
}

export function isPopularitySortAvailable ({ flags = {} } = {}) {
	return isPopularityFeatureEnabled(flags)
}

export function isFeaturedSpeakersSortAvailable ({ flags = {}, speakers = [] } = {}) {
	if (!flags.featured_speakers_enabled) return false
	return speakers.some(speaker => speaker?.is_featured)
}

export function featuredPosition (speaker) {
	const position = speaker?.featured_position
	if (position === null || position === undefined || position === '') {
		return Number.MAX_SAFE_INTEGER
	}
	const numeric = Number(position)
	return Number.isFinite(numeric) ? numeric : Number.MAX_SAFE_INTEGER
}

export function compareFeaturedSpeakers (a, b, { featuredFirst = false } = {}) {
	if (featuredFirst) {
		if (a?.is_featured && !b?.is_featured) return -1
		if (!a?.is_featured && b?.is_featured) return 1
	}
	const positionDelta = featuredPosition(a) - featuredPosition(b)
	if (positionDelta !== 0) return positionDelta
	const nameA = (a?.name || '').trim()
	const nameB = (b?.name || '').trim()
	if (!!nameA !== !!nameB) return nameA ? -1 : 1
	return nameA.localeCompare(nameB)
}

export function buildEventPageUrl (eventUrl, pagePath = '', isWipPreview = false) {
	if (!eventUrl) return ''
	const base = eventUrl.replace(/\/?$/, '/')
	const wipPrefix = isWipPreview ? 'schedule/v/wip/' : ''
	const normalizedPath = String(pagePath).replace(/^\//, '')
	return `${base}${wipPrefix}${normalizedPath}`
}

export function speakerCodeFromReference (sp) {
	if (!sp) return null
	if (typeof sp === 'string') return sp
	return sp.code || null
}

export function isTalkSchedulePending (talk) {
	return Boolean(talk?.schedule_pending || !talk?.start)
}

export function talkToSession (talk, {
	timezone,
	speakersLookup = {},
	tracksLookup = {},
	roomsLookup = {},
	includePopularity = false,
} = {}) {
	const isPending = isTalkSchedulePending(talk)
	const speakers = (talk.speakers || []).map((sp) => {
		if (typeof sp === 'object' && sp?.code) return sp
		const code = speakerCodeFromReference(sp)
		return speakersLookup[code] || { code }
	}).filter(Boolean)
	const track = typeof talk.track === 'object' ? talk.track : tracksLookup[talk.track]
	const base = {
		id: talk.code,
		code: talk.code,
		title: talk.title,
		abstract: talk.abstract,
		description: talk.description,
        do_not_record: talk.do_not_record,
        duration: talk.duration,
		speakers,
		track,
		tags: talk.tags,
		session_type: talk.session_type,
		content_locale: talk.content_locale,
		resources: talk.resources,
		answers: talk.answers,
		exporters: talk.exporters,
		recording_iframe: talk.recording_iframe,
		stream_url: talk.stream_url || null,
		stream_type: talk.stream_type || null,
	}
	if (includePopularity) {
		base.fav_count = normalizePopularityCount(talk)
	}
	if (isPending) {
		return { ...base, start: null, end: null, schedule_pending: true, room: null }
	}
	return {
		...base,
		start: moment.tz(talk.start, timezone),
		end: moment.tz(talk.end, timezone),
		room: typeof talk.room === 'object' ? talk.room : roomsLookup[talk.room],
	}
}

export function sortSessionsByStart (sessions) {
	return sessions.slice().sort((a, b) => {
		if (a.schedule_pending && !b.schedule_pending) return 1
		if (!a.schedule_pending && b.schedule_pending) return -1
		if (a.schedule_pending && b.schedule_pending) {
			return getLocalizedString(a.title).localeCompare(getLocalizedString(b.title))
		}
		return a.start.diff(b.start)
	})
}

export function talksToScheduleSessions (talks, context) {
	if (!talks?.length || !context?.timezone) return []
	return sortSessionsByStart(talks.map(talk => talkToSession(talk, context)))
}

export function sessionsForSpeaker (sessionsBySpeaker, speakerId) {
	if (!speakerId || !sessionsBySpeaker) return []
	const key = speakerId.toLowerCase()
	return sessionsBySpeaker[key] || sessionsBySpeaker[speakerId] || []
}

export function buildSessionsBySpeaker (sessions, { lowercaseKeys = true } = {}) {
	if (!sessions?.length) return {}
	return sessions.reduce((acc, session) => {
		(session.speakers || []).forEach((speaker) => {
			const code = speakerCodeFromReference(speaker)
			if (!code) return
			const key = lowercaseKeys ? code.toLowerCase() : code
			if (!acc[key]) acc[key] = []
			acc[key].push(session)
		})
		return acc
	}, {})
}

export function getCsrfToken () {
	const match = document.cookie.match(/eventyay_csrftoken=([^;]+)/)
	return match ? match[1] : ''
}

export function buildStarredSharingUrl (eventUrl) {
	const base = (eventUrl || '').replace(/\/$/, '')
	return `${base}/schedule/starred-sharing.json`
}

/** Read sharing preference rendered by the server (agenda pages or video shell). */
export function readInlineStarredSharingPreference () {
	const messagesEl = document.querySelector('#pretalx-messages')
	if (messagesEl?.dataset.loggedIn === 'true') {
		return messagesEl.dataset.showPublicly === 'true'
	}
	if (window.eventyay?.showPublicly !== undefined) {
		return !!window.eventyay.showPublicly
	}
	return null
}

export function hasInlineStarredSharingPreference () {
	return document.querySelector('#pretalx-messages') != null
		|| window.eventyay?.showPublicly !== undefined
}

/** Keep server-rendered shells in sync after the user toggles sharing in-place. */
export function syncInlineStarredSharingPreference (value) {
	const enabled = !!value
	const messagesEl = document.querySelector('#pretalx-messages')
	if (messagesEl) {
		messagesEl.dataset.showPublicly = enabled ? 'true' : 'false'
	}
	if (window.eventyay) {
		window.eventyay.showPublicly = enabled
	}
}

export async function loadStarredSharingPreference (eventUrl) {
	const inline = readInlineStarredSharingPreference()
	if (hasInlineStarredSharingPreference()) {
		return inline === true
	}
	if (!eventUrl) return false
	try {
		const response = await fetch(buildStarredSharingUrl(eventUrl), { credentials: 'same-origin' })
		if (!response.ok) return false
		const data = await response.json()
		return !!data?.show_publicly
	} catch {
		return false
	}
}

export async function updateStarredSharingPreference (eventUrl, value) {
	if (!eventUrl) throw new Error('missing event URL')
	const headers = { 'Content-Type': 'application/json' }
	const csrf = getCsrfToken()
	if (csrf) headers['X-CSRFToken'] = csrf
	const response = await fetch(buildStarredSharingUrl(eventUrl), {
		method: 'POST',
		headers,
		credentials: 'same-origin',
		body: JSON.stringify({ show_publicly: !!value }),
	})
	if (!response.ok) throw new Error('sharing preference update failed')
	const data = await response.json()
	const enabled = !!data?.show_publicly
	syncInlineStarredSharingPreference(enabled)
	return enabled
}

/**
 * Fetch schedule widget JSON. Returns null when no schedule is published,
 * throws on unexpected network/parse failures.
 */
export async function fetchWidgetScheduleData (eventUrl, { version = '', enrichData = false } = {}) {
	const versionPath = version ? `v/${version}/` : ''
	const params = new URLSearchParams()
	if (enrichData) params.set('enrich', '1')
	const query = params.toString()
	const suffix = query ? `?${query}` : ''
	const urls = [
		`${eventUrl}schedule/${versionPath}widgets/schedule.json${suffix}`,
		`${eventUrl}schedule/${versionPath}widget/v2.json${suffix}`,
	]
	for (const url of urls) {
		let response
		try {
			response = await fetch(url)
		} catch {
			continue
		}
		if (response.status === 404) {
			return null
		}
		if (!response.ok) {
			continue
		}
		try {
			const data = await response.json()
			if (data?.schedule_unavailable) {
				return null
			}
			return data
		} catch {
			continue
		}
	}
	throw new Error('schedule widget fetch failed')
}

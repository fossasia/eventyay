import moment from 'moment-timezone'
import { getVideoEmbedUrl } from './videoEmbed.js'

export { getVideoEmbedUrl }

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

export function resolveScheduleApiBase ({ baseUrl = '', apiUrl = '', remoteApiUrl = '', onHomeServer = false } = {}) {
	if (baseUrl) return baseUrl
	if (onHomeServer && apiUrl) return apiUrl
	if (remoteApiUrl) return remoteApiUrl
	return apiUrl || ''
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

// Schedule runs as a web component without Font Awesome; use inline SVG icons.
export const SOCIAL_ICON_SVG = {
	website: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2a10 10 0 100 20 10 10 0 000-20zm7.9 9h-3.2a15.4 15.4 0 00-1.3-5 8.03 8.03 0 014.5 5zM12 4c.9 0 2.3 1.9 3 5H9c.7-3.1 2.1-5 3-5zM4.1 11h3.2a15.4 15.4 0 011.3-5 8.03 8.03 0 00-4.5 5zM7.3 13H4.1a8.03 8.03 0 004.5 5 15.4 15.4 0 01-1.3-5zm1.7 0h6c-.7 3.1-2.1 5-3 5s-2.3-1.9-3-5zm8.7 0h3.2a8.03 8.03 0 01-4.5 5c.6-1.5 1.1-3.2 1.3-5zM12 20c-.9 0-2.3-1.9-3-5h6c-.7 3.1-2.1 5-3 5z"/></svg>',
	github: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 .3a12 12 0 00-3.8 23.4c.6.1.8-.3.8-.6v-2.2c-3.3.7-4-1.4-4-1.4-.5-1.4-1.3-1.8-1.3-1.8-1.1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1.1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.8-1.6-2.7-.3-5.5-1.3-5.5-6 0-1.3.5-2.4 1.2-3.2-.1-.3-.5-1.5.1-3.2 0 0 1-.3 3.3 1.2a11.5 11.5 0 016 0c2.3-1.5 3.3-1.2 3.3-1.2.6 1.7.2 2.9.1 3.2.8.8 1.2 1.9 1.2 3.2 0 4.7-2.8 5.7-5.5 6 .4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A12 12 0 0012 .3z"/></svg>',
	linkedin: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M4.98 3.5C4.98 4.88 3.86 6 2.5 6S0 4.88 0 3.5 1.12 1 2.5 1s2.48 1.12 2.48 2.5zM.24 8.25h4.52V24H.24V8.25zM8.34 8.25h4.33v2.14h.06c.6-1.14 2.08-2.34 4.28-2.34 4.58 0 5.42 3.01 5.42 6.93V24h-4.52v-6.86c0-1.64-.03-3.74-2.28-3.74-2.28 0-2.63 1.78-2.63 3.62V24H8.34V8.25z"/></svg>',
	x: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M18.9 2H22l-6.8 7.8L23 22h-6.2l-4.9-6.4L6.3 22H3.2l7.3-8.3L1 2h6.3l4.4 5.8L18.9 2zm-1.1 18h1.7L7.3 3.9H5.5L17.8 20z"/></svg>',
	facebook: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M22 12a10 10 0 10-11.6 9.9v-7H7.9V12h2.5V9.8c0-2.5 1.5-3.9 3.8-3.9 1.1 0 2.2.2 2.2.2v2.4h-1.3c-1.2 0-1.6.8-1.6 1.5V12h2.8l-.4 2.9h-2.4v7A10 10 0 0022 12z"/></svg>',
	instagram: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M7 2h10a5 5 0 015 5v10a5 5 0 01-5 5H7a5 5 0 01-5-5V7a5 5 0 015-5zm0 2a3 3 0 00-3 3v10a3 3 0 003 3h10a3 3 0 003-3V7a3 3 0 00-3-3H7zm11 1.8a1.2 1.2 0 110 2.4 1.2 1.2 0 010-2.4zM12 7a5 5 0 110 10 5 5 0 010-10zm0 2a3 3 0 100 6 3 3 0 000-6z"/></svg>',
	youtube: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M23.5 6.2a3 3 0 00-2.1-2.1C19.5 3.5 12 3.5 12 3.5s-7.5 0-9.4.6A3 3 0 00.5 6.2 31.5 31.5 0 000 12a31.5 31.5 0 00.5 5.8 3 3 0 002.1 2.1c1.9.6 9.4.6 9.4.6s7.5 0 9.4-.6a3 3 0 002.1-2.1A31.5 31.5 0 0024 12a31.5 31.5 0 00-.5-5.8zM9.8 15.5v-7l6.3 3.5-6.3 3.5z"/></svg>',
	gitlab: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 21.2L8.2 9.5h7.6L12 21.2zM.7 9.5h5.3L8.2 1.8c.1-.4.7-.4.8 0L12 9.5H.7c-.5 0-.7.6-.4 1L12 23.5 23.7 10.5c.3-.4.1-1-.4-1H18l2.2-7.7c.1-.4.7-.4.8 0L23.3 9.5"/></svg>',
	mastodon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2c-3.3 0-6 1-6 3.5v7.6c0 2.2 1.8 3 3.4 3.3.7.1 1.3.1 1.9.1l-.4 2c-.1.5.3 1 .8 1h.2c2.5 0 4.6-1 5.8-2.7 1-1.4 1.3-3.2 1.3-5.1V5.5C19 3 16.3 2 12 2zm-2.3 10.7c0 .6-.5 1.1-1.1 1.1S7.5 13.3 7.5 12.7V7.8c0-.6.5-1.1 1.1-1.1s1.1.5 1.1 1.1v4.9zm5.1 0c0 .6-.5 1.1-1.1 1.1s-1.1-.5-1.1-1.1V7.8c0-.6.5-1.1 1.1-1.1s1.1.5 1.1 1.1v4.9z"/></svg>',
	telegram: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M9.8 15.7l-.4 5.2c.5 0 .8-.2 1.1-.5l2.6-2.5 5.4 4c1 .5 1.7.3 2-.9L23.9 3.8c.3-1.3-.5-1.9-1.5-1.5L1.5 10.2C.2 10.7.2 11.4 1.3 11.7l5.6 1.7L19.2 5.5c.6-.4 1.2-.2.7.3L9.8 15.7z"/></svg>',
}

export function getSocialIconHtml(link) {
	if (!link) return ''
	if (SOCIAL_ICON_SVG[link.key]) return SOCIAL_ICON_SVG[link.key]
	if (link.icon_svg) return link.icon_svg
	const letter = (link.label || link.key || '?').toString().charAt(0).toUpperCase()
	return (
		`<svg viewBox="0 0 32 32" aria-hidden="true">` +
		`<rect x="1" y="1" width="30" height="30" rx="7" fill="currentColor"></rect>` +
		`<text x="16" y="21" text-anchor="middle" font-size="14" font-family="Arial, sans-serif" font-weight="700" fill="#ffffff">${letter}</text>` +
		`</svg>`
	)
}

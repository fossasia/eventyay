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

export function areScheduleExportsDisabled ({ version = '', scheduleMetaVersion = '', isFeaturedPage = false, exportersCount = 0, isWipPreview = false } = {}) {
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

export function buildEventPageUrl (eventUrl, pagePath = '', isWipPreview = false) {
	if (!eventUrl) return ''
	const base = eventUrl.replace(/\/?$/, '/')
	const wipPrefix = isWipPreview ? 'schedule/v/wip/' : ''
	const normalizedPath = String(pagePath).replace(/^\//, '')
	return `${base}${wipPrefix}${normalizedPath}`
}

const DETAIL_BACK_DESTINATIONS = {
	schedule: {
		messageKey: 'back_to_schedule',
		defaultLabel: 'Back to schedule',
		pagePath (isWipPreview) {
			return isWipPreview ? '' : 'schedule/'
		},
	},
	speakers: {
		messageKey: 'back_to_speakers',
		defaultLabel: 'Back to speakers',
		pagePath () {
			return 'speakers/'
		},
	},
}

export function getDetailBackLink ({ eventUrl, destination, isWipPreview = false, messages = {} }) {
	const config = DETAIL_BACK_DESTINATIONS[destination]
	if (!config || !eventUrl) return null
	return {
		href: buildEventPageUrl(eventUrl, config.pagePath(isWipPreview), isWipPreview),
		label: messages[config.messageKey] || config.defaultLabel,
	}
}

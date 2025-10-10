// import i18n from 'i18n'

export function getLocalizedString (string) {
	if (!string) return ''
	if (typeof string === 'string') return string
	const lang = document.querySelector('html').lang || 'en'
	return string[lang] || string.en || Object.values(string)[0] || ''
}

const checkPropScrolling = (node, prop) => ['auto', 'scroll'].includes(getComputedStyle(node, null).getPropertyValue(prop))
const isScrolling = node => checkPropScrolling(node, 'overflow') || checkPropScrolling(node, 'overflow-x') || checkPropScrolling(node, 'overflow-y')
export function findScrollParent (node) {
	if (!node || node === document.body) return
	if (isScrolling(node)) return node
	return findScrollParent(node.parentNode)
}
export function getPrettyDuration (start, end) {
	let minutes = end.diff(start).shiftTo('minutes').minutes
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

export function timeWithoutAmPm (time, locale) {
	const parts = new Intl.DateTimeFormat(locale, { hour: 'numeric', minute: 'numeric', timeZone: time.zoneName }).formatToParts(time)
	return parts.filter(part => part.type !== 'dayPeriod').map(part => part.value).join('')
}

export function timeAmPm (time, locale) {
	const parts = new Intl.DateTimeFormat(locale, { hour: 'numeric', minute: 'numeric', timeZone: time.zoneName }).formatToParts(time)
	return parts.filter(part => part.type === 'dayPeriod')[0].value
}

export function getSessionTime(session, timezone, locale, hasAmPm) {
	if (hasAmPm) {
		return {
			time: timeWithoutAmPm(session.start.setZone(timezone), locale),
			ampm: timeAmPm(session.start.setZone(timezone), locale)
		}
	} else {
		return {
			time: session.start.setZone(timezone).toLocaleString({ hour: 'numeric', 'minute': 'numeric' })
		}
	}
}

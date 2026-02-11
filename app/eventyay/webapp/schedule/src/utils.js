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

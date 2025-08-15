// import i18n from 'i18n'
import { DateTime } from 'luxon'

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

export function getPrettyDate (start) {
	return start.toLocaleString({'weekday': 'short', 'day': '2-digit', 'month': 'short'})
}

export function getLanguage () {
	const lang = document.querySelector('html').lang || 'en'
	return lang
}

export function getSessionType (item) {
	if (typeof item?.session_type === 'string') {
		return item.session_type
	} else if (typeof item?.session_type === 'object') {
		const sessionTypeKeys = Object.keys(item.session_type)
		const keyLanguage = sessionTypeKeys.find(key => key === getLanguage()) ||
			sessionTypeKeys.find(key => key === 'en') ||
			sessionTypeKeys[0]

		return item.session_type[keyLanguage]
	}
	return null
}

export function getSelectedName (item) {
	if (typeof item?.name === 'string') {
		return item.name
	} else if (typeof item?.name === 'object') {
		const keys = Object.keys(item.name)
		const keyLanguage = keys.find(key => key === getLanguage()) ||
			keys.find(key => key === 'en') ||
			keys[0]

		return item.name[keyLanguage]
	}
	return null
}

export function filterSessionTypesByLanguage (data) {
	const uniqueSessionTypes = new Set()

	data?.forEach(item => {
		const sessionType = getSessionType(item)
		if (sessionType) {
			uniqueSessionTypes.add(sessionType)
		}
	})

	return Array.from(uniqueSessionTypes).map(sessionType => ({
		value: sessionType,
		label: sessionType
	}))
}

export function filterItemsByLanguage (data) {
	const languageMap = new Map()

	data?.forEach(item => {
		const selectedName = getSelectedName(item)
		if (selectedName) {
			languageMap.set(item.id, selectedName)
		}
	})

	return Array.from(languageMap).map(([id, name]) => ({value: id, label: name}))
}

export function matchesSessionTypeFilter (talk, selectedIds) {
	if (typeof talk?.session_type === 'string') {
		return selectedIds.includes(talk.session_type)
	} else if (typeof talk?.session_type === 'object') {
		return Object.keys(talk.session_type).some(key => selectedIds.includes(talk.session_type[key]))
	}
	return false
}

/**
 *
 * @param {*} talksData
 * @param {*} refKey
 * @param {Array<T>} selectedIds
 * @param {Array<T>} previousResults
 * @returns {Array<T>}
 */
export function filterTalk (talksData, refKey, selectedIds, previousResults) {
	const talks = talksData

	return talks
		.filter(talk => {
			const matchesSessionType = refKey === 'session_type' && matchesSessionTypeFilter(talk, selectedIds)
			const matchesRefKey = selectedIds.includes(talk[refKey])

			return (matchesSessionType || matchesRefKey) && (!previousResults.length || previousResults.includes(talk.id))
		})
		.map(talk => talk.id) || []
}

/**
 * @typedef {Object} Choice
 * @property {string} name
 * @property {number} value
 * @property {boolean} selected
 * @typedef {Object} Filter
 * @property {{refKey: string, data: Array<Choice>}} tracks
 * @property {{refKey: string, data: Array<Choice>}} rooms
 * @property {{refKey: string, data: Array<Choice>}} types
 *
 * @param {Filter} filter
 * @param {*} data
 * @returns
 */
export function filteredSessions (filter, data) {
	let filteredResults = []

	for (const [key, value] of Object.entries(filter)) {
		const refKey = value.refKey
		const selectedIds = value.data.flatMap(item => item.selected ? item.value : [])

		if (selectedIds.length) {
			filteredResults = filterTalk(data, refKey, selectedIds, filteredResults)
		}
	}

	return filteredResults
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

export function normalizeLocaleCode (code) {
	if (!code) return ''
	return code.toString().trim().toLowerCase().replace(/_/g, '-')
}

export function localePrimary (code) {
	const normalized = normalizeLocaleCode(code)
	return normalized.split('-')[0] || normalized
}

export function localesMatch (filterValue, sessionValue) {
	const a = normalizeLocaleCode(filterValue)
	const b = normalizeLocaleCode(sessionValue)
	if (!a || !b) return false
	if (a === b) return true
	return localePrimary(a) === localePrimary(b)
}

export function slugify (text) {
	if (!text) return ''
	return text
		.toString()
		.toLowerCase()
		.trim()
		.replace(/[^\p{L}\p{N}]+/gu, '-')
		.replace(/^-+|-+$/g, '')
}

export function matchesFilterItem (item, val) {
	if (!item || val === undefined || val === null) return false
	const cleanVal = val.toString().trim()
	if (!cleanVal) return false
	const slugVal = slugify(cleanVal)
	const lowerVal = cleanVal.toLowerCase()

	// 1. Check ID or id-prefixed value (e.g. "42", "42-ai")
	if (item.id !== undefined && item.id !== null) {
		const strId = String(item.id)
		if (strId === cleanVal) return true
		if (cleanVal.startsWith(strId + '-') || cleanVal.startsWith(strId + '_')) return true
	}
	if (item.value !== undefined && item.value !== null) {
		const strVal = String(item.value)
		if (strVal === cleanVal) return true
		if (slugify(strVal) === slugVal) return true
	}

	// 2. Check label
	if (item.label) {
		const itemSlug = slugify(item.label)
		if (itemSlug && itemSlug === slugVal) return true
		if (item.label.toString().toLowerCase() === lowerVal) return true
	}

	// 3. Check name (string or localized object)
	if (typeof item.name === 'string') {
		if (slugify(item.name) === slugVal || item.name.toLowerCase() === lowerVal) return true
	} else if (item.name && typeof item.name === 'object') {
		for (const v of Object.values(item.name)) {
			if (typeof v === 'string') {
				if (slugify(v) === slugVal || v.toLowerCase() === lowerVal) return true
			}
		}
	}

	return false
}

export function matchesLanguageItem (item, val) {
	if (!item || val === undefined || val === null) return false
	const cleanVal = val.toString().trim()
	if (!cleanVal) return false
	if (localesMatch(cleanVal, item.value)) return true
	if (item.value && item.value.toLowerCase() === cleanVal.toLowerCase()) return true
	if (item.label) {
		if (slugify(item.label) === slugify(cleanVal) || item.label.toLowerCase() === cleanVal.toLowerCase()) return true
	}
	return false
}

export function getFilterItemSlug (item) {
	if (!item) return ''
	const labelText = item.label || (typeof item.name === 'string' ? item.name : '')
	const slug = slugify(labelText)
	if (slug) return slug
	if (item.id !== undefined && item.id !== null) return String(item.id)
	return item.value !== undefined && item.value !== null ? String(item.value) : ''
}

export function getTypeItemSlug (item) {
	if (!item) return ''
	const slug = slugify(item.label || item.value)
	if (slug) return slug
	return item.value !== undefined && item.value !== null ? String(item.value) : ''
}

export function getLanguageItemSlug (item) {
	if (!item) return ''
	return item.value || slugify(item.label) || ''
}

export function getQueryParamValues (searchParams, key) {
	if (!searchParams) return []
	const raw = searchParams.getAll(key)
	const values = []
	for (const entry of raw) {
		for (const part of entry.split(',')) {
			const trimmed = part.trim()
			if (trimmed) values.push(trimmed)
		}
	}
	return values
}

export const SCHEDULE_FILTER_QUERY_KEYS = ['track', 'room', 'type', 'language', 'day', 'recording']

export function serializeScheduleFiltersToUrl (currentHref, {
	filteredTracks = [],
	filteredRooms = [],
	filteredTypes = [],
	filteredLanguages = [],
	selectedDay = null,
	recordingFilter = 'all',
} = {}) {
	try {
		const url = new URL(currentHref)
		// Clean existing filter keys
		for (const key of SCHEDULE_FILTER_QUERY_KEYS) {
			url.searchParams.delete(key)
		}
		// Tracks
		for (const t of filteredTracks) {
			const slug = getFilterItemSlug(t)
			if (slug) url.searchParams.append('track', slug)
		}
		// Rooms
		for (const r of filteredRooms) {
			const slug = getFilterItemSlug(r)
			if (slug) url.searchParams.append('room', slug)
		}
		// Types
		for (const tp of filteredTypes) {
			const slug = getTypeItemSlug(tp)
			if (slug) url.searchParams.append('type', slug)
		}
		// Languages
		for (const l of filteredLanguages) {
			const slug = getLanguageItemSlug(l)
			if (slug) url.searchParams.append('language', slug)
		}
		// Day
		if (selectedDay) {
			url.searchParams.set('day', selectedDay)
		}
		// Recording
		if (recordingFilter === 'yes' || recordingFilter === 'no') {
			url.searchParams.set('recording', recordingFilter)
		}
		// If a day hash was in url.hash, clear the redundant day hash
		if (url.hash && /^\/?#?\d{4}-\d{2}-\d{2}$/.test(url.hash.replace(/^#/, ''))) {
			url.hash = ''
		}
		return url.pathname + url.search + url.hash
	} catch (error) {
		console.error('Failed to serialize schedule filters to URL', error)
		return currentHref
	}
}

export function parseScheduleFiltersFromUrl (currentHref, {
	allTracks = [],
	allRooms = [],
	allTypes = [],
	allLanguages = [],
	availableDays = [],
} = {}) {
	try {
		const url = new URL(currentHref)
		const trackVals = getQueryParamValues(url.searchParams, 'track')
		const roomVals = getQueryParamValues(url.searchParams, 'room')
		const typeVals = getQueryParamValues(url.searchParams, 'type')
		const langVals = getQueryParamValues(url.searchParams, 'language')
		const dayParam = url.searchParams.get('day')?.trim() || null
		const recordingParam = url.searchParams.get('recording')?.trim() || null

		// Apply to tracks
		for (const t of allTracks) {
			t.selected = trackVals.some(v => matchesFilterItem(t, v))
		}
		// Apply to rooms
		for (const r of allRooms) {
			r.selected = roomVals.some(v => matchesFilterItem(r, v))
		}
		// Apply to types
		for (const tp of allTypes) {
			tp.selected = typeVals.some(v => matchesFilterItem(tp, v))
		}
		// Apply to languages
		for (const l of allLanguages) {
			l.selected = langVals.some(v => matchesLanguageItem(l, v))
		}

		// Day validation
		let validatedDay = null
		if (dayParam && /^\d{4}-\d{2}-\d{2}$/.test(dayParam)) {
			const isValid = !availableDays.length || availableDays.some(d => {
				const str = d?.format ? d.format('YYYY-MM-DD') : String(d)
				return str === dayParam
			})
			if (isValid) {
				validatedDay = dayParam
			}
		}

		// Recording validation
		let validatedRecording = 'all'
		if (recordingParam === 'yes' || recordingParam === 'no' || recordingParam === 'all') {
			validatedRecording = recordingParam
		}

		return {
			selectedDay: validatedDay,
			recordingFilter: validatedRecording,
			hasFilters: trackVals.length > 0 || roomVals.length > 0 || typeVals.length > 0 || langVals.length > 0 || !!validatedDay || validatedRecording !== 'all',
		}
	} catch (error) {
		console.error('Failed to parse schedule filters from URL', error)
		return {
			selectedDay: null,
			recordingFilter: 'all',
			hasFilters: false,
		}
	}
}

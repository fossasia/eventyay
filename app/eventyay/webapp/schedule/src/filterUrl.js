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

export const MAX_FILTER_VALUES = 200
export const MAX_FILTER_PARAM_LENGTH = 300

function hasExactFilterMatch (item, cleanVal, slugVal, lowerVal) {
	const itemId = item.id != null ? item.id : item.value
	if (itemId != null && String(itemId) === cleanVal) return true
	if (item.value !== undefined && item.value !== null && String(item.value) === cleanVal) return true
	if (item.label) {
		const strLabel = item.label.toString()
		if (strLabel === cleanVal || strLabel.toLowerCase() === lowerVal) return true
		if (slugify(strLabel) === slugVal) return true
	}
	if (typeof item.name === 'string') {
		if (item.name === cleanVal || item.name.toLowerCase() === lowerVal || slugify(item.name) === slugVal) return true
	}
	return false
}

export function matchesFilterItem (item, val, allItems = []) {
	if (!item || val === undefined || val === null) return false
	const cleanVal = val.toString().trim()
	if (!cleanVal) return false
	const slugVal = slugify(cleanVal)
	const lowerVal = cleanVal.toLowerCase()

	// 1. Check exact match on this item
	if (hasExactFilterMatch(item, cleanVal, slugVal, lowerVal)) {
		if (Array.isArray(allItems) && allItems.length > 1) {
			const rawExactThis = (item.value != null && String(item.value) === cleanVal) || (item.label && item.label.toString() === cleanVal)
			const rawExactOther = allItems.some(other => other !== item && ((other.value != null && String(other.value) === cleanVal) || (other.label && other.label.toString() === cleanVal)))
			if (!rawExactThis && rawExactOther) return false
		}
		return true
	}

	// 2. Check localized name object
	const nameObj = (item.name && typeof item.name === 'object') ? item.name : (item.raw && typeof item.raw === 'object' ? item.raw : null)
	if (nameObj) {
		for (const v of Object.values(nameObj)) {
			if (typeof v === 'string') {
				if (v === cleanVal || slugify(v) === slugVal || v.toLowerCase() === lowerVal) return true
			}
		}
	}

	// 3. Fallback: ID prefix (e.g. "42-ai" or "1-workshop" for duplicate slugs)
	// Do NOT accept ID prefix if any item in allItems had an exact match for cleanVal
	if (Array.isArray(allItems) && allItems.some(other => hasExactFilterMatch(other, cleanVal, slugVal, lowerVal))) {
		return false
	}

	const itemId = item.id != null ? item.id : item.value
	if (itemId != null) {
		const strId = String(itemId)
		if (cleanVal.startsWith(strId + '-') || cleanVal.startsWith(strId + '_')) return true
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

export function getFilterItemSlug (item, allItems = []) {
	if (!item) return ''
	const labelText = item.label || (typeof item.name === 'string' ? item.name : '')
	const slug = slugify(labelText)
	if (slug) {
		const itemId = item.id != null ? item.id : item.value
		if (Array.isArray(allItems) && allItems.length > 1 && itemId != null) {
			const duplicate = allItems.some(other => {
				if (other === item) return false
				const otherId = other.id != null ? other.id : other.value
				return otherId != null && otherId !== itemId && slugify(other.label || (typeof other.name === 'string' ? other.name : '')) === slug
			})
			if (duplicate) return `${itemId}-${slug}`
		}
		return slug
	}
	if (item.id !== undefined && item.id !== null) return String(item.id)
	return item.value !== undefined && item.value !== null ? String(item.value) : ''
}

export function getTypeItemSlug (item, allItems = []) {
	if (!item) return ''
	const rawText = item.label || item.value || ''
	const slug = slugify(rawText)
	if (slug) {
		const itemId = item.id != null ? item.id : item.value
		if (Array.isArray(allItems) && allItems.length > 1) {
			const duplicate = allItems.some(other => {
				if (other === item) return false
				const otherId = other.id != null ? other.id : other.value
				const otherSlug = slugify(other.label || other.value || '')
				return otherId !== itemId && otherSlug === slug
			})
			if (duplicate) {
				if (item.id != null) return `${item.id}-${slug}`
				return String(item.value || rawText)
			}
		}
		return slug
	}
	return item.value !== undefined && item.value !== null ? String(item.value) : ''
}

export function getLanguageItemSlug (item) {
	if (!item) return ''
	return item.value || slugify(item.label) || ''
}

export function getQueryParamValues (searchParams, key, maxValues = MAX_FILTER_VALUES, maxLength = MAX_FILTER_PARAM_LENGTH) {
	if (!searchParams) return []
	const raw = searchParams.getAll(key)
	const values = []
	let selectionCount = 0
	for (const entry of raw) {
		if (selectionCount >= maxValues) break
		const trimmedEntry = entry.trim()
		if (!trimmedEntry || trimmedEntry.length > maxLength) continue

		if (entry.includes(',')) {
			values.push(trimmedEntry)
			const parts = entry.split(',').map(p => p.trim()).filter(p => p && p.length <= maxLength && p !== trimmedEntry)
			for (const part of parts) {
				if (selectionCount >= maxValues) break
				values.push(part)
				selectionCount++
			}
		} else {
			values.push(trimmedEntry)
			selectionCount++
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
	allTracks = [],
	allRooms = [],
	allTypes = [],
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
		for (const t of filteredTracks.slice(0, MAX_FILTER_VALUES)) {
			const slug = getFilterItemSlug(t, allTracks)
			if (slug) url.searchParams.append('track', slug.slice(0, MAX_FILTER_PARAM_LENGTH))
		}
		// Rooms
		for (const r of filteredRooms.slice(0, MAX_FILTER_VALUES)) {
			const slug = getFilterItemSlug(r, allRooms)
			if (slug) url.searchParams.append('room', slug.slice(0, MAX_FILTER_PARAM_LENGTH))
		}
		// Types
		for (const tp of filteredTypes.slice(0, MAX_FILTER_VALUES)) {
			const slug = getTypeItemSlug(tp, allTypes)
			if (slug) url.searchParams.append('type', slug.slice(0, MAX_FILTER_PARAM_LENGTH))
		}
		// Languages
		for (const l of filteredLanguages.slice(0, MAX_FILTER_VALUES)) {
			const slug = getLanguageItemSlug(l)
			if (slug) url.searchParams.append('language', slug.slice(0, MAX_FILTER_PARAM_LENGTH))
		}
		// Day
		if (selectedDay) {
			url.searchParams.set('day', selectedDay)
		}
		// Recording
		if (recordingFilter === 'yes' || recordingFilter === 'no') {
			url.searchParams.set('recording', recordingFilter)
		}
		// Clear date hash only when a day query parameter is written
		if (selectedDay && url.hash && /^\/?#?\d{4}-\d{2}-\d{2}$/.test(url.hash.replace(/^#/, ''))) {
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
		if (trackVals.length) {
			for (const t of allTracks) {
				t.selected = trackVals.some(v => matchesFilterItem(t, v, allTracks))
			}
		} else {
			for (const t of allTracks) t.selected = false
		}
		// Apply to rooms
		if (roomVals.length) {
			for (const r of allRooms) {
				r.selected = roomVals.some(v => matchesFilterItem(r, v, allRooms))
			}
		} else {
			for (const r of allRooms) r.selected = false
		}
		// Apply to types
		if (typeVals.length) {
			for (const tp of allTypes) {
				tp.selected = typeVals.some(v => matchesFilterItem(tp, v, allTypes))
			}
		} else {
			for (const tp of allTypes) tp.selected = false
		}
		// Apply to languages
		if (langVals.length) {
			for (const l of allLanguages) {
				l.selected = langVals.some(v => matchesLanguageItem(l, v))
			}
		} else {
			for (const l of allLanguages) l.selected = false
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

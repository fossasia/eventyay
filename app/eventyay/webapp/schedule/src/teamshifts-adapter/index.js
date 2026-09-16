/**
 * TeamShifts adapter for the public schedule web component.
 *
 * Provides capability flags and utility functions so the Session.vue
 * component can render shift role cards without polluting the standard
 * talk-rendering logic.
 */

export const SHIFT_STATUS_COLORS = {
	full: '#28a745',
	empty: '#dc3545',
	partial: '#c9920a',
}

export function isShiftSchedule (scheduleData) {
	const data = scheduleData?.value ?? scheduleData
	return data?.mode === 'shifts' || data?.schedule?.mode === 'shifts'
}

/**
 * Resolve mode from the schedule data payload.
 *
 * @param {Object|null} scheduleData
 * @returns {'talks'|'shifts'}
 */
export function resolveMode (scheduleData) {
	return isShiftSchedule(scheduleData) ? 'shifts' : 'talks'
}

/**
 * Get capability flags for the given mode.
 *
 * @param {'talks'|'shifts'} mode
 * @returns {{ showRoles: boolean, showSpeakers: boolean, showTracks: boolean, showClaimUI: boolean }}
 */
export function getCapabilities (mode) {
	if (mode === 'shifts') {
		return {
			showRoles: true,
			showSpeakers: false,
			showTracks: false,
			showClaimUI: true,
		}
	}
	return {
		showRoles: false,
		showSpeakers: true,
		showTracks: true,
		showClaimUI: false,
	}
}

/**
 * Determine if a session is a shift (has roles array).
 *
 * @param {{ roles?: Array|null }} session
 * @returns {boolean}
 */
export function isShiftSession (session) {
	return Array.isArray(session?.roles) && session.roles.length > 0
}

export function getAssignedList (role) {
	if (!role) return []
	if (Array.isArray(role.assigned)) return role.assigned
	if (Array.isArray(role.assigned_names)) {
		return role.assigned_names.map((name, i) => ({ id: i, name }))
	}
	return []
}

export const ASSIGNEE_PREVIEW_LIMIT = 2

export function previewAssignees (role) {
	return getAssignedList(role).slice(0, ASSIGNEE_PREVIEW_LIMIT)
}

export function hiddenAssigneeCount (role) {
	return Math.max(0, getAssignedList(role).length - ASSIGNEE_PREVIEW_LIMIT)
}

export function getCapacityStatus (role) {
	const assigned = getAssignedList(role)
	const capacity = Number(role?.capacity)
	if (Number.isFinite(capacity) && capacity > 0 && assigned.length >= capacity) return 'full'
	if (assigned.length > 0) return 'partial'
	return 'empty'
}

export function getShiftTrackColor (roles) {
	if (!Array.isArray(roles) || !roles.length) {
		return 'var(--pretalx-clr-primary)'
	}
	let allFull = true
	let anyEmpty = false
	for (const role of roles) {
		const capacity = Number(role.capacity) || 0
		if (capacity <= 0) continue
		const assigned = getAssignedList(role).length
		if (assigned === 0) {
			anyEmpty = true
			break
		}
		if (assigned < capacity) {
			allFull = false
		}
	}
	if (anyEmpty) return SHIFT_STATUS_COLORS.empty
	if (allFull) return SHIFT_STATUS_COLORS.full
	return SHIFT_STATUS_COLORS.partial
}

export function getCurrentUserId (scheduleData) {
	const data = scheduleData?.value ?? scheduleData
	return data?.schedule?.current_user_id ?? data?.current_user_id ?? null
}

export function getCurrentUserName (scheduleData) {
	const data = scheduleData?.value ?? scheduleData
	return data?.schedule?.current_user_name || data?.current_user_name || ''
}

export function getShiftId (session) {
	if (session?.talkId != null) return session.talkId
	const raw = session?.id
	const parsed = Number.parseInt(raw, 10)
	return Number.isNaN(parsed) ? raw : parsed
}

export function claimUrl (eventUrl, session) {
	const base = (eventUrl || '').replace(/\/?$/, '/')
	return `${base}teamshifts/shifts/${getShiftId(session)}/claim/`
}

export function withdrawUrl (eventUrl, session) {
	const base = (eventUrl || '').replace(/\/?$/, '/')
	return `${base}teamshifts/shifts/${getShiftId(session)}/withdraw/`
}

/**
 * Compute overlap-aware grid row placement for a shift session.
 *
 * When multiple shifts occupy the same room and overlap in time, they are
 * stacked sequentially (each starting where the previous one ends) rather
 * than rendered on top of each other. This logic only applies to shift
 * schedules — talk schedules never have overlapping sessions in the same room.
 *
 * @param {Object} session - The session to position
 * @param {Array} allSessions - All sessions in the grid
 * @returns {{ startName: string, endName: string|null }|null}
 *   Returns adjusted start/end slice names if stacking is needed, null otherwise.
 */
export function computeShiftOverlapPlacement (session, allSessions) {
	if (!session.start || !session.end) return null

	const overlapping = allSessions.filter(s => {
		if (s.id === session.id) return true
		if (!s.room || !s.start || !s.end) return false
		if (s.room !== session.room) return false
		return s.start.isBefore(session.end) && s.end.isAfter(session.start)
	}).sort((a, b) => {
		const diff = a.start.diff(b.start)
		return diff !== 0 ? diff : a.id - b.id
	})

	if (overlapping.length <= 1) return null

	const myIndex = overlapping.findIndex(s => s.id === session.id)
	if (myIndex === 0) {
		return { startName: null, endName: null }
	}
	const prev = overlapping[myIndex - 1]
	return { startName: prev.end, endName: null }
}

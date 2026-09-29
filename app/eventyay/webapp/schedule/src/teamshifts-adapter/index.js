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

function roomId (room) {
	return room?.id ?? room
}

export function computeRoomMaxOverlap (room, allSessions) {
	const rid = roomId(room)
	const events = []
	for (const s of allSessions) {
		if (roomId(s.room) !== rid || !s.start || !s.end) continue
		events.push({ time: s.start, delta: 1 })
		events.push({ time: s.end, delta: -1 })
	}
	events.sort((a, b) => {
		const diff = a.time.diff(b.time)
		return diff !== 0 ? diff : a.delta - b.delta
	})
	let active = 0
	let max = 1
	for (const e of events) {
		active += e.delta
		if (active > max) max = active
	}
	return max
}

function assignRoomTracks (room, allSessions) {
	const rid = roomId(room)
	const roomSessions = allSessions
		.filter(s => roomId(s.room) === rid && s.start && s.end)
		.sort((a, b) => {
			const diff = a.start.diff(b.start)
			if (diff !== 0) return diff
			return String(a.id) < String(b.id) ? -1 : String(a.id) > String(b.id) ? 1 : 0
		})
	const trackEnds = []
	const trackMap = new Map()
	for (const s of roomSessions) {
		let assigned = -1
		for (let t = 0; t < trackEnds.length; t++) {
			if (!s.start.isBefore(trackEnds[t])) {
				assigned = t
				break
			}
		}
		if (assigned === -1) {
			assigned = trackEnds.length
			trackEnds.push(s.end)
		} else {
			trackEnds[assigned] = s.end
		}
		trackMap.set(s.id, assigned)
	}
	return trackMap
}

export function computeShiftColumnLayout (rooms, sessions) {
	const layout = new Map()
	let col = 2
	for (const room of rooms) {
		const rid = roomId(room)
		const span = computeRoomMaxOverlap(room, sessions)
		layout.set(rid, { colStart: col, colSpan: span })
		col += span
	}
	return layout
}

export function buildShiftGridTemplateColumns (rooms, sessions, minColWidth, timeColWidth) {
	const w = minColWidth || '320px'
	const t = timeColWidth || '78px'
	const roomCols = rooms.map(room => {
		const span = computeRoomMaxOverlap(room, sessions)
		return Array(span).fill(`minmax(${w}, 1fr)`).join(' ')
	}).join(' ')
	return `${t} ${roomCols} auto`
}

export function computeShiftOverlapPlacement (session, allSessions, columnLayout) {
	if (!session.start || !session.end || !session.room) return null

	const rid = roomId(session.room)
	const roomLayout = columnLayout ? columnLayout.get(rid) : null
	if (!roomLayout || roomLayout.colSpan <= 1) return null

	const trackMap = assignRoomTracks(session.room, allSessions)
	const track = trackMap.get(session.id)
	if (track == null) return null

	const subCol = roomLayout.colStart + track
	return {
		gridRow: `${getSliceName(session.start)} / ${getSliceName(session.end)}`,
		gridColumn: `${subCol} / ${subCol + 1}`,
	}
}

function getSliceName (date) {
	return `slice-${date.format('MM-DD-HH-mm')}`
}

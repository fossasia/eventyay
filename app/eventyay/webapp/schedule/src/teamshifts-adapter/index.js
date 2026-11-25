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

export function sortedAssignees (role) {
	return [...getAssignedList(role)].sort((a, b) =>
		String(a?.name ?? '').localeCompare(String(b?.name ?? ''), undefined, { sensitivity: 'base', numeric: true })
	)
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

/**
 * Whether the volunteer wants a confirmation email when they claim or drop a shift.
 * Defaults to true when the backend does not send a saved choice.
 */
export function getShiftActionEmails (scheduleData) {
	const data = scheduleData?.value ?? scheduleData
	return (data?.schedule?.shift_action_emails ?? data?.shift_action_emails) !== false
}

export function setShiftActionEmails (scheduleData, value) {
	const data = scheduleData?.value ?? scheduleData
	const target = data?.schedule ?? data
	if (target) target.shift_action_emails = Boolean(value)
}

/**
 * Request body for the claim and withdraw endpoints.
 */
export function roleActionPayload (role, sendEmail) {
	return { role_id: role.id, send_email: Boolean(sendEmail) }
}

export function scheduleApiUrl (eventUrl) {
	const base = (eventUrl || '').replace(/\/?$/, '/')
	return `${base}teamshifts/shifts/api/`
}

/**
 * Whether a claim or drop already took effect, judging by the shift's current roles.
 * A request can fail after the server applied the change (for example on a timeout),
 * so the dialog checks this before showing an error.
 */
export function roleActionApplied (action, roles, roleId, userId) {
	const role = (roles || []).find(r => r.id === roleId)
	const assigned = getAssignedList(role).some(user => user.id === userId)
	return action === 'drop' ? !assigned : assigned
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

export function getCanManageShifts (scheduleData) {
	const data = scheduleData?.value ?? scheduleData
	return data?.schedule?.can_manage_shifts ?? data?.can_manage_shifts ?? false
}

export function getEventRoles (scheduleData) {
	const data = scheduleData?.value ?? scheduleData
	return data?.schedule?.roles ?? data?.roles ?? []
}

export function manageUrl (eventUrl, session) {
	const base = (eventUrl || '').replace(/\/?$/, '/')
	return `${base}teamshifts/shifts/${getShiftId(session)}/manage/`
}

export function assignmentsUrl (eventUrl) {
	const base = (eventUrl || '').replace(/\/?$/, '/')
	return `${base}teamshifts/shifts/assignments/`
}

export function membersUrl (eventUrl) {
	const base = (eventUrl || '').replace(/\/?$/, '/')
	return `${base}teamshifts/shifts/members/`
}

/**
 * Returns the reason a TeamShifts request failed, or '' if the response has none.
 * The API sends some errors as JSON ({detail} or {error}) and others as a plain-text body.
 */
export async function getErrorMessage (response) {
	// 5xx bodies (JSON or a plain-text DEBUG traceback) describe server failures, not
	// something the user can fix, so the dialog keeps its generic message.
	if (!response || response.status >= 500) return ''
	const text = (await response.text().catch(() => '')).trim()
	let message
	try {
		const data = JSON.parse(text)
		message = [data?.detail, data?.error].find(value => typeof value === 'string' && value.trim())?.trim()
	} catch {
		// HTML pages are not meant to be shown in a dialog.
		message = text.startsWith('<') ? '' : text
	}
	return message && message.length <= 300 ? message : ''
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
		const trackMap = assignRoomTracks(room, sessions)
		layout.set(rid, { colStart: col, colSpan: span, trackMap })
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

export function computeShiftPlacements (session, allSessions, columnLayout) {
	if (!session.start || !session.end || !session.room) return null

	const rid = roomId(session.room)
	const roomLayout = columnLayout ? columnLayout.get(rid) : null
	if (!roomLayout || roomLayout.colSpan <= 1) return null

	const trackMap = (roomLayout && roomLayout.trackMap) || assignRoomTracks(session.room, allSessions)
	const track = trackMap.get(session.id)
	if (track == null) return null

	const startMs = session.start.valueOf()
	const endMs = session.end.valueOf()
	const others = allSessions.filter(other =>
		other.id !== session.id && roomId(other.room) === rid && other.start && other.end &&
		other.start.valueOf() < endMs && startMs < other.end.valueOf() &&
		trackMap.get(other.id) != null)

	if (!others.length) {
		return [{
			gridRow: `${getSliceName(session.start)} / ${getSliceName(session.end)}`,
			gridColumn: `${roomLayout.colStart} / ${roomLayout.colStart + roomLayout.colSpan}`,
			continuation: false,
			continuationBefore: false,
			continuationAfter: false,
			segmentStart: session.start,
			segmentEnd: session.end,
		}]
	}

	const cuts = new Map([[startMs, session.start], [endMs, session.end]])
	for (const other of others) {
		for (const edge of [other.start, other.end]) {
			const ms = edge.valueOf()
			if (ms > startMs && ms < endMs) cuts.set(ms, edge)
		}
	}
	const points = [...cuts.entries()].sort((a, b) => a[0] - b[0])

	const segments = []
	for (let i = 0; i < points.length - 1; i++) {
		const [fromMs, from] = points[i]
		const [toMs, to] = points[i + 1]
		const tracks = others
			.filter(other => other.start.valueOf() < toMs && fromMs < other.end.valueOf())
			.map(other => trackMap.get(other.id))
			.concat(track)
			.sort((a, b) => a - b)
		const position = tracks.indexOf(track)
		const first = position === 0 ? 0 : track
		const last = position === tracks.length - 1 ? roomLayout.colSpan - 1 : tracks[position + 1] - 1
		const prev = segments[segments.length - 1]
		if (prev && prev.first === first && prev.last === last) {
			prev.end = to
			prev.endMs = toMs
		} else {
			segments.push({ first, last, start: from, end: to, startMs: fromMs, endMs: toMs })
		}
	}

	let main = 0
	segments.forEach((seg, i) => {
		if (seg.endMs - seg.startMs > segments[main].endMs - segments[main].startMs) main = i
	})
	return segments.map((seg, i) => ({
		gridRow: `${getSliceName(seg.start)} / ${getSliceName(seg.end)}`,
		gridColumn: `${roomLayout.colStart + seg.first} / ${roomLayout.colStart + seg.last + 1}`,
		continuation: i !== main,
		continuationBefore: i > 0,
		continuationAfter: i < segments.length - 1,
		segmentStart: seg.start,
		segmentEnd: seg.end,
	}))
}

export function placementGridItems (base, session, placements) {
	return placements.map((placement, i) => ({
		key: `${base}-${i}`,
		session,
		style: { 'grid-row': placement.gridRow, 'grid-column': placement.gridColumn },
		props: {
			continuation: placement.continuation,
			continuationBefore: placement.continuationBefore,
			continuationAfter: placement.continuationAfter,
		},
	}))
}

export function computeShiftOverlapPlacement (session, allSessions, columnLayout) {
	if (!session.start || !session.end || !session.room) return null

	const rid = roomId(session.room)
	const roomLayout = columnLayout ? columnLayout.get(rid) : null
	if (!roomLayout || roomLayout.colSpan <= 1) return null

	const trackMap = (roomLayout && roomLayout.trackMap) || assignRoomTracks(session.room, allSessions)
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

export const SHIFT_STATUS_COLORS = {
	full: '#28a745',
	empty: '#dc3545',
	partial: '#c9920a',
}

export function isShiftSchedule (scheduleData) {
	const data = scheduleData?.value ?? scheduleData
	return data?.mode === 'shifts' || data?.schedule?.mode === 'shifts'
}

export function resolveMode (scheduleData) {
	return isShiftSchedule(scheduleData) ? 'shifts' : 'talks'
}

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
	let totalCapacity = 0
	let totalAssigned = 0
	for (const role of roles) {
		totalCapacity += role.capacity || 0
		totalAssigned += getAssignedList(role).length
	}
	if (totalCapacity <= 0) return 'var(--pretalx-clr-primary)'
	if (totalAssigned >= totalCapacity) return SHIFT_STATUS_COLORS.full
	if (totalAssigned === 0) return SHIFT_STATUS_COLORS.empty
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

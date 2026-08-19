export function isShiftSchedule (scheduleData) {
	return scheduleData?.mode === 'shifts' || scheduleData?.schedule?.mode === 'shifts'
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

export function getCapacityStatus (role) {
	const assigned = getAssignedList(role)
	const capacity = Number(role?.capacity)
	if (Number.isFinite(capacity) && capacity > 0 && assigned.length >= capacity) return 'full'
	if (assigned.length > 0) return 'partial'
	return 'empty'
}

export function getCurrentUserId (scheduleData) {
	return scheduleData?.schedule?.current_user_id ?? scheduleData?.current_user_id ?? null
}

export function getCurrentUserName (scheduleData) {
	return scheduleData?.schedule?.current_user_name || scheduleData?.current_user_name || ''
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

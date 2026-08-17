export function resolveMode (scheduleData) {
	if (scheduleData && scheduleData.mode === 'shifts') return 'shifts'
	return 'talks'
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
	return Array.isArray(session.roles) && session.roles.length > 0
}

export function getCapacityStatus (role) {
	if (!role || !role.capacity) return 'open'
	if (role.assigned_count >= role.capacity) return 'full'
	if (role.assigned_count > 0) return 'partial'
	return 'open'
}

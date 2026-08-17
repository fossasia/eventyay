/**
 * TeamShifts adapter for the public schedule web component.
 *
 * Provides capability flags and utility functions so the Session.vue
 * component can render shift role cards without polluting the standard
 * talk-rendering logic.
 */

/**
 * Resolve mode from the schedule data payload.
 * If the schedule data contains a `mode` field set to 'shifts', the
 * widget is displaying a shift schedule.
 *
 * @param {Object|null} scheduleData
 * @returns {'talks'|'shifts'}
 */
export function resolveMode (scheduleData) {
	if (scheduleData && scheduleData.mode === 'shifts') return 'shifts'
	return 'talks'
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
	return Array.isArray(session.roles) && session.roles.length > 0
}

/**
 * Get capacity status class for a shift role.
 *
 * @param {{ capacity: number, assigned_count: number }} role
 * @returns {'open'|'partial'|'full'}
 */
export function getCapacityStatus (role) {
	if (!role || !role.capacity) return 'open'
	if (role.assigned_count >= role.capacity) return 'full'
	if (role.assigned_count > 0) return 'partial'
	return 'open'
}

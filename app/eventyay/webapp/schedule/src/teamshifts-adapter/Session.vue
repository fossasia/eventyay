<template lang="pug">
div.c-linear-schedule-session.is-shift-session(
	:class="{'has-date': showDate, 'short-session': isShortSession, 'grid-very-short': isGridVeryShort, 'schedule-pending-session': isSchedulePending}",
	:style="style")
	.time-box
		.start.schedule-pending(v-if="isSchedulePending")
			svg.schedule-pending-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2", stroke-linecap="round", stroke-linejoin="round", aria-hidden="true")
				rect(x="3", y="4", width="18", height="18", rx="2", ry="2")
				line(x1="16", y1="2", x2="16", y2="6")
				line(x1="8", y1="2", x2="8", y2="6")
				line(x1="3", y1="10", x2="21", y2="10")
			.schedule-pending-label
				span.schedule-pending-text {{ schedulePendingText }}
		template(v-else)
			.start(:class="{'has-ampm': effectiveHasAmPm}")
				.date(v-if="showDate")
					.weekday {{ weekdayLabel }}
					.day-month {{ dayMonthLabel }}
				.clock
					.time {{ startTime.time }}
					.ampm(v-if="startTime.ampm") {{ startTime.ampm }}
				.duration {{ getPrettyDuration(session.start, session.end) }}
		.buffer(v-if="!isSchedulePending")
	.info
		.title-row
			.title(:class="{'title-clamped': isShortSession}") {{ getLocalizedString(session.title) }}
			.organizer-actions(v-if="canManageShifts")
				button.organizer-action-btn(type="button", @pointerdown.stop, @click.stop="openEditDialog", :title="$t('Edit shift')", :aria-label="$t('Edit shift')")
					svg.organizer-action-icon(viewBox="0 0 24 24", aria-hidden="true")
						path(fill="currentColor", d="M6.58 20.57 l1.22 -1.22 l-3.15 -3.15 l-1.22 1.22 v1.43 h1.71 v1.71 h1.43 z M13.58 8.14 q0 -0.29 -0.29 -0.29 q-0.13 0 -0.23 0.09 l-7.26 7.26 q-0.09 0.09 -0.09 0.23 q0 0.29 0.29 0.29 q0.13 0 0.23 -0.09 l7.26 -7.26 q0.09 -0.09 0.09 -0.23 z M12.86 5.57 l5.57 5.57 l-11.14 11.14 h-5.57 v-5.57 z M22 6.86 q0 0.71 -0.5 1.21 l-2.22 2.22 l-5.57 -5.57 l2.22 -2.21 q0.48 -0.51 1.21 -0.51 q0.71 0 1.22 0.51 l3.15 3.13 q0.5 0.52 0.5 1.22 z")
				button.organizer-action-btn(type="button", @pointerdown.stop, @click.stop="openDeleteConfirm", :title="$t('Delete shift')", :aria-label="$t('Delete shift')")
					svg.organizer-action-icon(viewBox="0 0 24 24", aria-hidden="true")
						path(fill="currentColor", d="M9.43 18.43 v-9.43 q0 -0.19 -0.12 -0.31 t-0.31 -0.12 h-0.86 q-0.19 0 -0.31 0.12 t-0.12 0.31 v9.43 q0 0.19 0.12 0.31 t0.31 0.12 h0.86 q0.19 0 0.31 -0.12 t0.12 -0.31 z M12.86 18.43 v-9.43 q0 -0.19 -0.12 -0.31 t-0.31 -0.12 h-0.86 q-0.19 0 -0.31 0.12 t-0.12 0.31 v9.43 q0 0.19 0.12 0.31 t0.31 0.12 h0.86 q0.19 0 0.31 -0.12 t0.12 -0.31 z M16.29 18.43 v-9.43 q0 -0.19 -0.12 -0.31 t-0.31 -0.12 h-0.86 q-0.19 0 -0.31 0.12 t-0.12 0.31 v9.43 q0 0.19 0.12 0.31 t0.31 0.12 h0.86 q0.19 0 0.31 -0.12 t0.12 -0.31 z M9 5.14 h6 l-0.64 -1.57 q-0.09 -0.12 -0.23 -0.15 h-4.25 q-0.13 0.03 -0.23 0.15 z M21.43 5.57 v0.86 q0 0.19 -0.12 0.31 t-0.31 0.12 h-1.29 v12.7 q0 1.11 -0.63 1.92 t-1.51 0.81 h-11.14 q-0.88 0 -1.51 -0.78 t-0.63 -1.9 v-12.75 h-1.29 q-0.19 0 -0.31 -0.12 t-0.12 -0.31 v-0.86 q0 -0.19 0.12 -0.31 t0.31 -0.12 h4.14 l0.94 -2.24 q0.2 -0.5 0.72 -0.84 t1.06 -0.35 h4.29 q0.54 0 1.06 0.35 t0.72 0.84 l0.94 2.24 h4.14 q0.19 0 0.31 0.12 t0.12 0.31 z")
		.roles-list(v-if="session.roles && session.roles.length")
			.role-item(v-for="(role, index) in session.roles", :key="role.id ?? index")
				.role-content
					.role-name-group
						span.role-name
							| {{ roleName(role) }}
							span.role-restricted-tag(v-if="role.is_restricted") {{ $t('Restricted') }}
						span.role-divider
						span.role-badge(:class="'badge-' + getCapacityStatus(role)") {{ capacityLabel(role) }}
					.role-assignees
						ul.role-assignee-list(v-if="assignedList(role).length")
							li.role-assignee(v-for="(user, i) in sortedAssignees(role)", :key="user.id || i")
								span.role-assignee-name {{ user.name }}
						span.text-muted(v-else) {{ $t('None') }}
				.shift-actions
					template(v-if="canManageShifts")
						button.btn.btn-sm.btn-danger(v-if="isMyRole(role)", type="button", :disabled="claimBusy", @click.stop="openConfirm('drop', role)") {{ $t('Drop') }}
						button.btn.btn-sm.btn-primary(type="button", :disabled="assignBusy", @click.stop="openAssignDialog(role)") {{ $t('Sign Up') }}
					template(v-else-if="isMyRole(role)")
						button.btn.btn-sm.btn-danger(type="button", :disabled="claimBusy", @click.stop="openConfirm('drop', role)") {{ $t('Drop') }}
					template(v-else-if="canClaimRole(role)")
						button.btn.btn-sm.btn-primary(type="button", :disabled="claimBusy", @click.stop="openConfirm('claim', role)") {{ $t('Sign Up') }}
					template(v-else-if="role.is_restricted")
						span.text-muted {{ $t('Restricted') }}
					template(v-else-if="isRoleFull(role)")
						span.text-muted {{ $t('Full') }}
		.bottom-info
			.room(v-if="showRoom && session.room", :title="getLocalizedString(session.room.name)") {{ getLocalizedString(session.room.name) }}
	shift-confirm-dialog(
		ref="shiftConfirm",
		:title="confirmTitle",
		:lead="confirmLead",
		:details="confirmDetails",
		:confirm-label="confirmLabel",
		:confirm-class="confirmButtonClass",
		:email-label="confirmEmailLabel",
		v-model:sendEmail="sendEmail",
		:error="confirmError",
		:busy="claimBusy",
		@confirm="confirmRoleAction",
		@cancel="closeConfirm")
	shift-edit-dialog(
		v-if="canManageShifts",
		ref="shiftEdit",
		:rooms="scheduleRooms",
		:roles="eventRoles",
		:timezone="effectiveTimezone",
		:error="editError",
		:busy="editBusy",
		@save="saveEdit",
		@cancel="closeEditDialog")
	assign-volunteer-dialog(
		v-if="canManageShifts",
		ref="assignDialog",
		:session="session",
		:role-id="assignRoleId",
		:members="members",
		:error="assignError",
		:busy="assignBusy",
		@assign="assignMember",
		@unassign="unassignMember",
		@cancel="closeAssignDialog")
</template>

<script>
import ShiftConfirmDialog from './ShiftConfirmDialog.vue'
import ShiftEditDialog from './ShiftEditDialog.vue'
import AssignVolunteerDialog from './AssignVolunteerDialog.vue'
import { getLocalizedString, getPrettyDuration, getSessionTime, getCsrfToken } from '../utils'
import { logOperational } from '../operationalLog.js'
import {
	getCapacityStatus,
	getAssignedList,
	sortedAssignees,
	getCurrentUserId,
	getCurrentUserName,
	getCanManageShifts,
	getEventRoles,
	getShiftTrackColor,
	getShiftActionEmails,
	setShiftActionEmails,
	roleActionPayload,
	roleActionApplied,
	scheduleApiUrl,
	getShiftId,
	claimUrl,
	withdrawUrl,
	manageUrl,
	assignmentsUrl,
	membersUrl,
	getErrorMessage,
} from './index'

export default {
	name: 'TeamshiftsSession',
	components: {
		ShiftConfirmDialog,
		ShiftEditDialog,
		AssignVolunteerDialog,
	},
	props: {
		now: Object,
		session: Object,
		showRoom: {
			type: Boolean,
			default: true,
		},
		showDate: {
			type: Boolean,
			default: false,
		},
		hasAmPm: {
			type: Boolean,
			default: false,
		},
		locale: String,
		timezone: String,
	},
	inject: {
		eventUrl: { default: null },
		scheduleData: { default: null },
		translationMessages: { default: () => ({}) },
	},
	data () {
		return {
			getPrettyDuration,
			getLocalizedString,
			getSessionTime,
			getCapacityStatus,
			getAssignedList,
			sortedAssignees,
			claimBusy: false,
			confirmAction: null,
			confirmRole: null,
			confirmError: '',
			pendingUnassign: null,
			editBusy: false,
			editError: '',
			assignBusy: false,
			assignError: '',
			assignRoleId: null,
			members: [],
			sendEmail: true,
		}
	},
	computed: {
		effectiveTimezone () {
			return this.timezone ?? this.scheduleData?.timezone
		},
		effectiveHasAmPm () {
			if (this.timezone != null) return this.hasAmPm
			return this.scheduleData?.hasAmPm ?? this.hasAmPm
		},
		style () {
			return {
				'--track-color': getShiftTrackColor(this.session?.roles),
			}
		},
		isSchedulePending () {
			return Boolean(this.session.schedule_pending || !this.session.start)
		},
		schedulePendingText () {
			const m = this.translationMessages || {}
			return m.schedule_pending_secondary || this.$t('To be announced')
		},
		startTime () {
			if (this.isSchedulePending) {
				return { time: this.schedulePendingText }
			}
			return getSessionTime(this.session, this.effectiveTimezone, this.locale, this.effectiveHasAmPm)
		},
		weekdayLabel () {
			if (!this.session.start) return ''
			return this.session.start.clone().tz(this.effectiveTimezone).locale(this.locale || 'en').format('ddd')
		},
		dayMonthLabel () {
			if (!this.session.start) return ''
			return this.session.start.clone().tz(this.effectiveTimezone).locale(this.locale || 'en').format('D MMM')
		},
		sessionDurationMinutes () {
			if (this.session.duration) return Number(this.session.duration)
			if (this.session.start && this.session.end?.diff) {
				return Math.round(this.session.end.diff(this.session.start, 'minutes', true))
			}
			return 0
		},
		isShortSession () {
			const minutes = this.sessionDurationMinutes
			return minutes > 0 && minutes <= 15
		},
		isGridVeryShort () {
			const minutes = this.sessionDurationMinutes
			return minutes > 0 && minutes <= 10
		},
		currentUserId () {
			return getCurrentUserId(this.scheduleData)
		},
		currentUserName () {
			return getCurrentUserName(this.scheduleData)
		},
		canManageShifts () {
			return getCanManageShifts(this.scheduleData)
		},
		eventRoles () {
			return getEventRoles(this.scheduleData)
		},
		scheduleRooms () {
			const data = this.scheduleData?.value ?? this.scheduleData
			return data?.schedule?.rooms ?? data?.rooms ?? []
		},
		myAssignedRoleId () {
			if (!this.currentUserId || !this.session?.roles) return null
			for (const role of this.session.roles) {
				if (getAssignedList(role).some(user => user.id === this.currentUserId)) return role.id
			}
			return null
		},
		hasOverlappingAssignment () {
			if (!this.currentUserId || !this.session?.start || !this.session?.end) return false
			const data = this.scheduleData?.value ?? this.scheduleData
			const allSessions = data?.sessions || []
			for (const other of allSessions) {
				if (!other.id || other.id === this.session.id) continue
				if (!other.start || !other.end || !other.roles) continue
				if (!other.start.isBefore(this.session.end) || !other.end.isAfter(this.session.start)) continue
				for (const role of other.roles) {
					if (getAssignedList(role).some(user => user.id === this.currentUserId)) return true
				}
			}
			return false
		},
		shiftTimeLabel () {
			if (!this.session.start) return ''
			const tz = this.effectiveTimezone
			const locale = this.locale || 'en'
			const date = this.session.start.clone().tz(tz).locale(locale).format('ddd, D MMM YYYY')
			const startClock = getSessionTime(this.session, tz, locale, this.effectiveHasAmPm)
			const startStr = startClock.ampm ? `${startClock.time} ${startClock.ampm}` : startClock.time
			if (!this.session.end) return `${date}, ${startStr}`
			const end = this.session.end.clone().tz(tz).locale(locale)
			const endStr = this.effectiveHasAmPm ? `${end.format('h:mm')} ${end.format('A')}` : end.format('LT')
			return `${date}, ${startStr} – ${endStr}`
		},
		shiftLocationLabel () {
			return getLocalizedString(this.session.room?.name) || '—'
		},
		confirmTitle () {
			if (this.confirmAction === 'drop') return this.$t('Drop shift role')
			if (this.confirmAction === 'delete') return this.$t('Delete shift')
			if (this.confirmAction === 'unassign') return this.$t('Unassign volunteer')
			return this.$t('Claim shift role')
		},
		confirmLead () {
			if (this.confirmAction === 'drop') {
				return this.$t('Are you sure you want to drop this role? The slot will open again for other team members.')
			}
			if (this.confirmAction === 'delete') {
				return this.$t('Are you sure you want to delete this shift? This cannot be undone.')
			}
			if (this.confirmAction === 'unassign') {
				return this.$t('Are you sure you want to unassign this volunteer from the role?')
			}
			return this.$t('Are you sure you want to claim this role for this shift?')
		},
		confirmLabel () {
			if (this.confirmAction === 'drop') return this.$t('Drop')
			if (this.confirmAction === 'delete') return this.$t('Delete')
			if (this.confirmAction === 'unassign') return this.$t('Unassign')
			return this.$t('Confirm')
		},
		confirmButtonClass () {
			return ['drop', 'delete', 'unassign'].includes(this.confirmAction) ? 'btn-danger' : 'btn-primary'
		},
		confirmEmailLabel () {
			if (this.confirmAction === 'drop') return this.$t('Email me a confirmation of this drop')
			if (this.confirmAction === 'claim') return this.$t('Email me a confirmation of this sign-up')
			return ''
		},
		confirmDetails () {
			const role = this.confirmRole
			const rows = [
				{ label: this.$t('Shift'), value: getLocalizedString(this.session.title) },
			]
			if (role) {
				rows.push({ label: this.$t('Role'), value: this.roleName(role) })
			}
			rows.push(
				{ label: this.$t('Time'), value: this.shiftTimeLabel },
				{ label: this.$t('Location'), value: this.shiftLocationLabel },
			)
			if (!role) return rows
			if (this.confirmAction === 'drop') {
				const mine = getAssignedList(role).find(user => user.id === this.currentUserId)
				const selfAssigned = mine ? mine.self_assigned !== false && !mine.assigned_by_name : true
				rows.push({
					label: this.$t('Status'),
					value: selfAssigned ? this.$t('Self assigned') : `${this.$t('Organizer assigned')}${mine?.assigned_by_name ? ` by ${mine.assigned_by_name}` : ''}`,
				})
				rows.push({
					label: this.$t('Name'),
					value: mine?.name || this.currentUserName || '—',
				})
			} else if (this.confirmAction === 'unassign') {
				const target = getAssignedList(role).find(user => user.id === this.pendingUnassign?.userId)
				rows.push({ label: this.$t('Name'), value: target?.name || '—' })
			} else if (this.confirmAction === 'claim' && this.currentUserName) {
				rows.push({ label: this.$t('Name'), value: this.currentUserName })
			}
			return rows
		},
	},
	methods: {
		assignedList (role) {
			return getAssignedList(role)
		},
		capacityLabel (role) {
			return this.$t('{{assigned}}/{{capacity}} filled', { assigned: getAssignedList(role).length, capacity: role.capacity })
		},
		roleName (role) {
			return getLocalizedString(role.name)
		},
		isMyRole (role) {
			return getAssignedList(role).some(user => user.id === this.currentUserId)
		},
		isRoleFull (role) {
			const capacity = Number(role?.capacity)
			if (!Number.isFinite(capacity)) return false
			if (capacity <= 0) return true
			return getAssignedList(role).length >= capacity
		},
		canClaimRole (role) {
			if (!this.currentUserId) return false
			if (role.is_restricted) return false
			if (this.isRoleFull(role)) return false
			if (this.myAssignedRoleId) return false
			if (this.hasOverlappingAssignment) return false
			return true
		},
		async postRoleAction (url, role, action) {
			this.claimBusy = true
			this.confirmError = ''
			try {
				const headers = {
					'Content-Type': 'application/json',
					Accept: 'application/json',
					'X-Requested-With': 'XMLHttpRequest',
				}
				const csrf = getCsrfToken()
				if (csrf) headers['X-CSRFToken'] = csrf
				const response = await fetch(url, {
					method: 'POST',
					headers,
					credentials: 'same-origin',
					body: JSON.stringify(roleActionPayload(role, this.sendEmail)),
				})
				const data = await response.json().catch(() => ({}))
				if (!response.ok) {
					logOperational({action: 'schedule.save', outcome: 'failure', backend: 'teamshifts', error_code: 'http_error', status: response.status})
					if (await this.recoverFromFailedAction(action, role)) return
					this.confirmError = data.error || this.$t('Could not update this shift.')
					return
				}
				setShiftActionEmails(this.scheduleData, data.shift_action_emails ?? this.sendEmail)
				if (Array.isArray(data.roles)) {
					this.session.roles.splice(0, this.session.roles.length, ...data.roles)
				} else {
					window.location.reload()
					return
				}
				this.closeConfirm()
			} catch {
				logOperational({action: 'schedule.save', outcome: 'failure', backend: 'teamshifts', error_code: 'network_error'})
				if (await this.recoverFromFailedAction(action, role)) return
				this.confirmError = this.$t('Could not update this shift.')
			} finally {
				this.claimBusy = false
			}
		},
		async recoverFromFailedAction (action, role) {
			// The request may have failed after the server applied the change. Re-read the
			// shift so the buttons match the server, and treat an applied change as done.
			try {
				const response = await fetch(scheduleApiUrl(this.eventUrl), {
					headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
					credentials: 'same-origin',
				})
				if (!response.ok) return false
				const data = await response.json()
				const shiftId = String(getShiftId(this.session))
				const talk = (data.talks || []).find(t => String(t.id) === shiftId)
				if (!talk || !Array.isArray(talk.roles)) return false
				this.session.roles.splice(0, this.session.roles.length, ...talk.roles)
				if (!roleActionApplied(action, talk.roles, role.id, this.currentUserId)) return false
				this.closeConfirm()
				return true
			} catch {
				return false
			}
		},
		openConfirm (action, role) {
			this.confirmAction = action
			this.confirmRole = role
			this.confirmError = ''
			this.sendEmail = getShiftActionEmails(this.scheduleData)
			this.$nextTick(() => this.$refs.shiftConfirm?.show())
		},
		closeConfirm () {
			this.$refs.shiftConfirm?.close()
			this.confirmAction = null
			this.confirmRole = null
			this.confirmError = ''
			this.pendingUnassign = null
		},
		confirmRoleAction () {
			if (this.confirmAction === 'delete') return this.deleteShift()
			if (this.confirmAction === 'unassign') return this.performUnassign()
			const role = this.confirmRole
			if (!role) return
			const url = this.confirmAction === 'drop'
				? withdrawUrl(this.eventUrl, this.session)
				: claimUrl(this.eventUrl, this.session)
			return this.postRoleAction(url, role, this.confirmAction)
		},
		openEditDialog () {
			this.editError = ''
			this.$nextTick(() => this.$refs.shiftEdit?.show(this.session))
		},
		closeEditDialog () {
			this.$refs.shiftEdit?.close()
			this.editError = ''
		},
		async saveEdit (payload) {
			if (new Date(payload.end) <= new Date(payload.start)) {
				this.editError = this.$t('End date must be after start date.')
				return
			}
			this.editBusy = true
			this.editError = ''
			try {
				const headers = {
					'Content-Type': 'application/json',
					Accept: 'application/json',
					'X-Requested-With': 'XMLHttpRequest',
				}
				const csrf = getCsrfToken()
				if (csrf) headers['X-CSRFToken'] = csrf
				const response = await fetch(manageUrl(this.eventUrl, this.session), {
					method: 'PATCH',
					headers,
					credentials: 'same-origin',
					body: JSON.stringify(payload),
				})
				if (!response.ok) {
					logOperational({action: 'schedule.save', outcome: 'failure', backend: 'teamshifts', error_code: 'http_error', status: response.status})
					this.editError = await getErrorMessage(response) || this.$t('Could not update this shift.')
					return
				}
				window.location.reload()
			} catch {
				logOperational({action: 'schedule.save', outcome: 'failure', backend: 'teamshifts', error_code: 'network_error'})
				this.editError = this.$t('Could not update this shift.')
			} finally {
				this.editBusy = false
			}
		},
		openDeleteConfirm () {
			this.confirmAction = 'delete'
			this.confirmRole = null
			this.confirmError = ''
			this.$nextTick(() => this.$refs.shiftConfirm?.show())
		},
		async deleteShift () {
			this.claimBusy = true
			this.confirmError = ''
			try {
				const headers = {
					Accept: 'application/json',
					'X-Requested-With': 'XMLHttpRequest',
				}
				const csrf = getCsrfToken()
				if (csrf) headers['X-CSRFToken'] = csrf
				const response = await fetch(manageUrl(this.eventUrl, this.session), {
					method: 'DELETE',
					headers,
					credentials: 'same-origin',
				})
				if (!response.ok) {
					logOperational({action: 'schedule.save', outcome: 'failure', backend: 'teamshifts', error_code: 'http_error', status: response.status})
					this.confirmError = await getErrorMessage(response) || this.$t('Could not delete this shift.')
					return
				}
				window.location.reload()
			} catch {
				logOperational({action: 'schedule.save', outcome: 'failure', backend: 'teamshifts', error_code: 'network_error'})
				this.confirmError = this.$t('Could not delete this shift.')
			} finally {
				this.claimBusy = false
			}
		},
		openAssignDialog (role) {
			this.assignRoleId = role.id
			this.assignError = ''
			this.members = []
			this.$nextTick(() => this.$refs.assignDialog?.show())
			this.loadMembers()
		},
		closeAssignDialog () {
			this.$refs.assignDialog?.close()
			this.assignError = ''
			this.assignRoleId = null
		},
		async loadMembers () {
			try {
				const response = await fetch(membersUrl(this.eventUrl), {
					headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
					credentials: 'same-origin',
				})
				const data = await response.json().catch(() => ({}))
				if (!response.ok || !Array.isArray(data.members)) {
					logOperational({action: 'schedule.fetch', outcome: 'failure', backend: 'teamshifts', error_code: response.ok ? 'invalid_payload' : 'http_error', status: response.status})
					this.assignError = this.$t('Could not load team members.')
					return
				}
				this.members = data.members
			} catch {
				logOperational({action: 'schedule.fetch', outcome: 'failure', backend: 'teamshifts', error_code: 'network_error'})
				this.assignError = this.$t('Could not load team members.')
			}
		},
		async assignMember ({ roleId, userId }) {
			this.assignBusy = true
			this.assignError = ''
			try {
				const headers = {
					'Content-Type': 'application/json',
					Accept: 'application/json',
					'X-Requested-With': 'XMLHttpRequest',
				}
				const csrf = getCsrfToken()
				if (csrf) headers['X-CSRFToken'] = csrf
				const response = await fetch(assignmentsUrl(this.eventUrl), {
					method: 'POST',
					headers,
					credentials: 'same-origin',
					body: JSON.stringify({ shift_id: getShiftId(this.session), user_id: userId, role_id: roleId }),
				})
				const data = await response.json().catch(() => ({}))
				if (!response.ok) {
					logOperational({action: 'schedule.save', outcome: 'failure', backend: 'teamshifts', error_code: 'http_error', status: response.status})
					this.assignError = data.detail || this.$t('Could not assign this volunteer.')
					return
				}
				if (Array.isArray(data.roles)) {
					this.session.roles.splice(0, this.session.roles.length, ...data.roles)
				}
			} catch {
				logOperational({action: 'schedule.save', outcome: 'failure', backend: 'teamshifts', error_code: 'network_error'})
				this.assignError = this.$t('Could not assign this volunteer.')
			} finally {
				this.assignBusy = false
			}
		},
		unassignMember ({ roleId, userId }) {
			this.pendingUnassign = { roleId, userId }
			this.confirmAction = 'unassign'
			this.confirmRole = (this.session.roles || []).find(r => r.id === roleId) || null
			this.confirmError = ''
			this.$nextTick(() => this.$refs.shiftConfirm?.show())
		},
		async performUnassign () {
			if (!this.pendingUnassign) return
			const { roleId, userId } = this.pendingUnassign
			this.claimBusy = true
			this.confirmError = ''
			try {
				const headers = {
					Accept: 'application/json',
					'X-Requested-With': 'XMLHttpRequest',
				}
				const csrf = getCsrfToken()
				if (csrf) headers['X-CSRFToken'] = csrf
				const url = `${assignmentsUrl(this.eventUrl)}?shift_id=${getShiftId(this.session)}&user_id=${userId}&role_id=${roleId}`
				const response = await fetch(url, { method: 'DELETE', headers, credentials: 'same-origin' })
				const data = await response.json().catch(() => ({}))
				if (!response.ok) {
					logOperational({action: 'schedule.save', outcome: 'failure', backend: 'teamshifts', error_code: 'http_error', status: response.status})
					this.confirmError = data.detail || this.$t('Could not unassign this volunteer.')
					return
				}
				if (Array.isArray(data.roles)) {
					this.session.roles.splice(0, this.session.roles.length, ...data.roles)
				}
				this.closeConfirm()
			} catch {
				logOperational({action: 'schedule.save', outcome: 'failure', backend: 'teamshifts', error_code: 'network_error'})
				this.confirmError = this.$t('Could not unassign this volunteer.')
			} finally {
				this.claimBusy = false
			}
		},
	},
}
</script>

<style lang="stylus">
.organizer-action-btn
	display: inline-flex
	align-items: center
	flex-shrink: 0
	padding: 0
	border: none
	background: transparent
	color: #2185d0
	cursor: pointer
	&:hover
		color: #1a6fb5
.organizer-action-icon
	width: 14px
	height: 14px
.c-linear-schedule-session.is-shift-session
	z-index: 10
	display: flex
	align-items: stretch
	min-width: 0
	min-height: auto
	margin: 8px 0
	margin-right: 8px
	color: rgb(13 15 16)
	position: relative
	font-size: 14px
	cursor: default
	text-decoration: none
	.time-box
		width: 64px
		flex-shrink: 0
		box-sizing: border-box
		background-color: var(--track-color)
		padding: 10px 4px 6px 4px
		border-radius: 6px 0 0 6px
		display: flex
		flex-direction: column
		align-items: center
		.start
			color: $clr-primary-text-dark
			display: flex
			flex-direction: column
			align-items: center
			text-align: center
			width: 100%
			&.has-ampm
				align-self: stretch
			.date
				display: inline-flex
				flex-direction: column
				align-items: center
				justify-content: center
				background-color: rgba(255, 255, 255, 0.18)
				color: rgba(255, 255, 255, 0.95)
				border-radius: 6px
				padding: 4px 6px
				margin-bottom: 6px
				max-width: 100%
				box-sizing: border-box
				.weekday
					font-size: 10px
					font-weight: 700
					text-transform: uppercase
					letter-spacing: 0.5px
					line-height: 1
				.day-month
					font-size: 11px
					font-weight: 600
					text-transform: uppercase
					letter-spacing: 0.3px
					line-height: 1
					margin-top: 2px
			.clock
				display: flex
				flex-direction: column
				align-items: center
				max-width: 100%
			.time
				font-size: 14px
				font-weight: 700
				line-height: 1.2
				white-space: nowrap
				font-variant-numeric: tabular-nums
			.ampm
				font-weight: 400
				font-size: 10px
				margin-top: 1px
				opacity: 0.85
				text-transform: uppercase
				white-space: nowrap
			.duration
				font-weight: 400
				font-size: 11px
				color: rgba(255, 255, 255, 0.7)
				margin-top: 4px
				white-space: nowrap
		.buffer
			flex: auto
	&.has-date
		.time-box
			width: 88px
	.info
		position: relative
		flex: auto
		display: flex
		flex-direction: column
		padding: 8px
		border: border-separator()
		border-left: none
		border-radius: 0 6px 6px 0
		background-color: $clr-white
		min-width: 0
		.title-row
			display: flex
			align-items: flex-start
			justify-content: space-between
			gap: 8px
			margin-bottom: 4px
		.title
			font-size: 16px
			font-weight: 500
		.organizer-actions
			display: flex
			flex-shrink: 0
			gap: 28px
		.bottom-info
			flex: auto
			display: flex
			align-items: flex-end
			gap: 4px
			min-width: 0
			.room
				flex: 1
				min-width: 0
				text-align: right
				color: $clr-secondary-text-light
				white-space: nowrap
				overflow: hidden
				text-overflow: ellipsis
	.roles-list
		display: flex
		flex-direction: column
		gap: 6px
		margin-top: 6px
		.role-item
			border-top: 1px solid rgba(0, 0, 0, 0.12)
			padding-top: 6px
			display: flex
			align-items: center
			gap: 8px
			.role-content
				flex: 1 1 auto
				min-width: 0
				.role-name-group
					display: flex
					align-items: center
					gap: 0
					font-size: 13px
					font-weight: 600
					.role-name
						white-space: nowrap
						overflow: hidden
						text-overflow: ellipsis
					.role-restricted-tag
						margin-left: 6px
						font-size: 10px
						font-weight: 700
						text-transform: uppercase
						letter-spacing: 0.02em
						padding: 1px 5px
						border-radius: 3px
						background-color: #6c757d
						color: #fff
					.role-divider
						display: inline-block
						width: 1px
						height: 14px
						background-color: rgba(0, 0, 0, 0.25)
						margin: 0 8px
						flex-shrink: 0
					.role-badge
						display: inline-block
						font-size: 11px
						font-weight: 600
						line-height: 1.3
						padding: 3px 8px
						border-radius: 999px
						border: 1.5px solid
						white-space: nowrap
						box-sizing: border-box
						&.badge-full
							border-color: #28a745
							color: #28a745
						&.badge-empty
							border-color: #dc3545
							color: #dc3545
						&.badge-partial
							border-color: #c9920a
							color: #c9920a
				.role-assignees
					margin-top: 6px
					.role-assignee-list
						list-style: none
						margin: 0
						padding: 0
						display: flex
						flex-wrap: wrap
						gap: 4px 6px
					.role-assignee
						list-style: none
						margin: 0
						padding: 3px 9px
						max-width: 100%
						font-size: 12px
						line-height: 1.3
						color: $clr-secondary-text-light
						background-color: $clr-grey-100
						border-radius: 999px
						overflow-wrap: anywhere
						&::marker
							content: none
			.shift-actions
				display: flex
				align-items: center
				flex-shrink: 0
				gap: 6px
				.btn
					display: inline-block
					padding: 2px 8px
					font-size: 12px
					line-height: 1.4
					border-radius: 4px
					border: 1px solid transparent
					cursor: pointer
					&:disabled
						opacity: 0.65
						cursor: default
				.btn-primary
					background: #2185d0
					border-color: #2185d0
					color: #fff
				.btn-danger
					background: #d9534f
					border-color: #d9534f
					color: #fff
				.text-muted
					font-size: 11px
					color: #888
	&:hover
		.info
			border: 1px solid var(--track-color)
			border-left: none
			.title
				color: var(--pretalx-clr-primary)

@media (max-width: 900px)
	.c-linear-schedule-session.is-shift-session
		min-width: 0

.density-compact .c-linear-schedule-session.is-shift-session
	margin: 4px 4px
	font-size: 12px
	.time-box
		width: 56px
		padding: 6px 4px 4px 4px
	.info
		padding: 4px
		.title
			font-size: 13px

.density-comfortable .c-linear-schedule-session.is-shift-session
	margin: 12px 8px
	font-size: 16px
	.time-box
		width: 72px
		padding: 14px 6px 8px 6px
	.info
		padding: 12px
		.title
			font-size: 18px
</style>

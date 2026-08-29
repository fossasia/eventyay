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
				.time {{ startTime.time }}
				.ampm(v-if="startTime.ampm") {{ startTime.ampm }}
				.duration {{ getPrettyDuration(session.start, session.end) }}
		.buffer(v-if="!isSchedulePending")
	.info
		.title(:class="{'title-clamped': isShortSession}") {{ getLocalizedString(session.title) }}
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
						template(v-if="assignedList(role).length")
							span.role-assignee(v-for="(user, i) in previewAssignees(role)", :key="user.id || i")
								svg.role-user-icon(viewBox="0 0 24 24", aria-hidden="true")
									path(fill="currentColor", d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z")
								span.role-assignee-name {{ user.name }}
							.role-assignees-more-wrap(v-if="hiddenAssigneeCount(role)")
								button.role-assignees-more(
									type="button",
									:aria-expanded="openAssigneesRoleId != null ? 'true' : 'false'",
									@click.stop="toggleAssigneesPopover(role, $event)") +{{ hiddenAssigneeCount(role) }} {{ $t('more') }}
						span.text-muted(v-if="!assignedList(role).length") {{ $t('None') }}
				.shift-actions
					template(v-if="isMyRole(role)")
						button.btn.btn-sm.btn-danger(type="button", :disabled="claimBusy", @click.stop="openConfirm('drop', role)") {{ $t('Drop') }}
					template(v-else-if="canClaimRole(role)")
						button.btn.btn-sm.btn-primary(type="button", :disabled="claimBusy", @click.stop="openConfirm('claim', role)") {{ $t('Sign Up') }}
					template(v-else-if="role.is_restricted")
						span.text-muted {{ $t('Restricted') }}
					template(v-else-if="isRoleFull(role)")
						span.text-muted {{ $t('Full') }}
		.bottom-info
			.room(v-if="showRoom && session.room", :title="getLocalizedString(session.room.name)") {{ getLocalizedString(session.room.name) }}
	assignees-popover(
		:open="openAssigneesRoleId != null",
		:title="assigneesPopoverTitle",
		:assignees="assigneesPopoverList",
		:top="assigneesPopoverPos.top",
		:left="assigneesPopoverPos.left",
		:width="assigneesPopoverPos.width",
		:max-height="assigneesPopoverPos.maxHeight")
	shift-confirm-dialog(
		ref="shiftConfirm",
		:title="confirmTitle",
		:lead="confirmLead",
		:details="confirmDetails",
		:confirm-label="confirmLabel",
		:confirm-class="confirmButtonClass",
		:error="confirmError",
		:busy="claimBusy",
		@confirm="confirmRoleAction",
		@cancel="closeConfirm")
</template>

<script>
import ShiftConfirmDialog from './ShiftConfirmDialog.vue'
import AssigneesPopover from './AssigneesPopover.vue'
import { getLocalizedString, getPrettyDuration, getSessionTime, getCsrfToken } from '../utils'
import {
	getCapacityStatus,
	getAssignedList,
	previewAssignees,
	hiddenAssigneeCount,
	getCurrentUserId,
	getCurrentUserName,
	getShiftTrackColor,
	claimUrl,
	withdrawUrl,
} from './index'

function placeAssigneesPopover (anchorEl) {
	const rect = anchorEl.getBoundingClientRect()
	const width = Math.min(280, Math.max(200, window.innerWidth - 16))
	const maxHeight = Math.min(280, window.innerHeight - 16)
	let left = rect.left
	let top = rect.bottom + 6
	if (left + width > window.innerWidth - 8) left = window.innerWidth - width - 8
	if (left < 8) left = 8
	if (top + 140 > window.innerHeight) {
		top = Math.max(8, rect.top - 6 - Math.min(maxHeight, 200))
	}
	return { top, left, width, maxHeight }
}

export default {
	name: 'TeamshiftsSession',
	components: {
		ShiftConfirmDialog,
		AssigneesPopover,
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
			previewAssignees,
			hiddenAssigneeCount,
			claimBusy: false,
			confirmAction: null,
			confirmRole: null,
			confirmError: '',
			openAssigneesRoleId: null,
			assigneesPopoverList: [],
			assigneesPopoverTitle: 'Assigned',
			assigneesPopoverPos: { top: 0, left: 0, width: 260, maxHeight: 280 },
		}
	},
	mounted () {
		this._onAssigneesDocPointerDown = (event) => {
			if (this.openAssigneesRoleId == null) return
			const path = event.composedPath?.() || []
			const inside = path.some((node) => {
				const el = node
				return el?.classList?.contains?.('role-assignees-popover') || el?.classList?.contains?.('role-assignees-more')
			})
			if (inside) return
			this.closeAssigneesPopover()
		}
		this._onScroll = () => {
			if (this.openAssigneesRoleId != null) this.closeAssigneesPopover()
		}
		document.addEventListener('pointerdown', this._onAssigneesDocPointerDown, true)
		window.addEventListener('scroll', this._onScroll, true)
	},
	beforeUnmount () {
		document.removeEventListener('pointerdown', this._onAssigneesDocPointerDown, true)
		window.removeEventListener('scroll', this._onScroll, true)
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
			return m.schedule_pending_secondary || this.$t('Coming soon')
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
			return this.confirmAction === 'drop' ? this.$t('Drop shift role') : this.$t('Claim shift role')
		},
		confirmLead () {
			if (this.confirmAction === 'drop') {
				return this.$t('Are you sure you want to drop this role? The slot will open again for other team members.')
			}
			return this.$t('Are you sure you want to claim this role for this shift?')
		},
		confirmLabel () {
			return this.confirmAction === 'drop' ? this.$t('Drop') : this.$t('Confirm')
		},
		confirmButtonClass () {
			return this.confirmAction === 'drop' ? 'btn-danger' : 'btn-primary'
		},
		confirmDetails () {
			const role = this.confirmRole
			if (!role) return []
			const rows = [
				{ label: this.$t('Shift'), value: getLocalizedString(this.session.title) },
				{ label: this.$t('Role'), value: this.roleName(role) },
				{ label: this.$t('Time'), value: this.shiftTimeLabel },
				{ label: this.$t('Location'), value: this.shiftLocationLabel },
			]
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
			} else if (this.currentUserName) {
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
			return this.$t('{{assigned}}/{{capacity}} needed', { assigned: getAssignedList(role).length, capacity: role.capacity })
		},
		closeAssigneesPopover () {
			this.openAssigneesRoleId = null
			this.assigneesPopoverList = []
		},
		toggleAssigneesPopover (role, event) {
			const roleId = role.id ?? role.name
			if (this.openAssigneesRoleId === roleId) {
				this.closeAssigneesPopover()
				return
			}
			const list = getAssignedList(role)
			this.assigneesPopoverList = list
			this.assigneesPopoverTitle = `Assigned (${list.length})`
			this.assigneesPopoverPos = placeAssigneesPopover(event.currentTarget)
			this.openAssigneesRoleId = roleId
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
		async postRoleAction (url, role) {
			this.claimBusy = true
			this.confirmError = ''
			this.closeAssigneesPopover()
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
					body: JSON.stringify({ role_id: role.id }),
				})
				const data = await response.json().catch(() => ({}))
				if (!response.ok) {
					this.confirmError = data.error || this.$t('Could not update this shift.')
					return
				}
				if (Array.isArray(data.roles)) {
					this.session.roles.splice(0, this.session.roles.length, ...data.roles)
				} else {
					window.location.reload()
					return
				}
				this.closeConfirm()
			} catch {
				this.confirmError = this.$t('Could not update this shift.')
			} finally {
				this.claimBusy = false
			}
		},
		openConfirm (action, role) {
			this.confirmAction = action
			this.confirmRole = role
			this.confirmError = ''
			this.$nextTick(() => this.$refs.shiftConfirm?.show())
		},
		closeConfirm () {
			this.$refs.shiftConfirm?.close()
			this.confirmAction = null
			this.confirmRole = null
			this.confirmError = ''
		},
		confirmRoleAction () {
			const role = this.confirmRole
			if (!role) return
			const url = this.confirmAction === 'drop'
				? withdrawUrl(this.eventUrl, this.session)
				: claimUrl(this.eventUrl, this.session)
			return this.postRoleAction(url, role)
		},
	},
}
</script>

<style lang="stylus">
.c-linear-schedule-session.is-shift-session
	z-index: 10
	display: flex
	align-items: stretch
	min-width: 300px
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
			.time
				font-size: 14px
				font-weight: 700
				line-height: 1.2
			.ampm
				font-weight: 400
				font-size: 10px
				margin-top: 1px
				opacity: 0.85
				text-transform: uppercase
			.duration
				font-weight: 400
				font-size: 11px
				color: rgba(255, 255, 255, 0.7)
				margin-top: 4px
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
		.title
			font-size: 16px
			font-weight: 500
			margin-bottom: 4px
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
					position: relative
					display: flex
					flex-wrap: wrap
					align-items: center
					gap: 6px 12px
					font-size: 12px
					color: #6c757d
					margin-top: 4px
					.role-assignee
						display: inline-flex
						align-items: center
						gap: 6px
						min-width: 0
					.role-assignee-name
						min-width: 0
					.role-user-icon
						width: 11px
						height: 11px
						flex-shrink: 0
					.role-assignees-more-wrap
						position: relative
					.role-assignees-more
						border: none
						background: transparent
						color: #2185d0
						font-size: 12px
						font-weight: 600
						line-height: 1.3
						padding: 0
						cursor: pointer
						&:hover
							text-decoration: underline
			.shift-actions
				display: flex
				align-items: center
				flex-shrink: 0
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

@media (max-width: 600px)
	.c-linear-schedule-session.is-shift-session
		min-width: 0
		.time-box
			width: 54px
			padding: 8px 6px 6px 2px
			.start
				align-items: flex-start
				text-align: left
				.time, .duration
					width: 100%
					text-align: left
		.info
			padding: 6px
			.title
				font-size: 14px

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

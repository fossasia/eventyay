<template lang="pug">
.c-linear-schedule-session(:style="style", @pointerdown.stop="onPointerDown", :class="classes")
	.time-box
		.start(:class="{'has-ampm': startTime?.ampm}", v-if="startTime")
			.time {{ startTime.time }}
			.ampm(v-if="startTime.ampm") {{ startTime.ampm }}
		.duration {{ durationPretty }}
	.info
		.title-row(style="display: flex; justify-content: space-between; align-items: flex-start;")
			.title(:class="{'title-clamped': isShortSession}") {{ getLocalizedString(session.title) }}
			.card-actions(v-if="caps.showRoles && caps.canEdit && !isBreak && session.room")
				button.btn.btn-link.p-0.mr-2(type="button", @pointerdown.stop, @click.stop="$emit('editSession', session)", :aria-label="$t('Edit')", :title="$t('Edit')")
					i.fa.fa-pencil(aria-hidden="true")
				button.btn.btn-link.p-0.text-danger(type="button", @pointerdown.stop, @click.stop="$emit('deleteSession', session)", :aria-label="$t('Delete')", :title="$t('Delete')")
					i.fa.fa-trash(aria-hidden="true")
		
		template(v-if="caps.showRoles")
			.roles-list(v-if="session.roles && session.roles.length")
				.role-item(v-for="role in session.roles", :key="role.id")
					.role-header
						span.role-name
							| {{ getLocalizedString(role.name) }}
							span.role-restricted-tag(v-if="role.is_restricted", :title="$t('Volunteers cannot self-claim this role; requires manual assignment.')") {{ $t('Restricted') }}
						span.role-badge(:class="getCapacityClass(role)") {{ role.assigned.length }}/{{ role.capacity }} {{ $t('assigned') }}
					.role-assignees
						span(v-for="(user, i) in role.assigned", :key="user.id")
							i.fa.fa-user.mr-1
							| {{ user.name }}{{ i < role.assigned.length - 1 ? ', ' : '' }}
						span.text-muted(v-if="!role.assigned.length") {{ $t('None') }}
			
			template(v-if="caps.showClaimUI")
				.shift-manage.mt-2(v-if="!isBreak")
					template(v-if="isMyClaimed")
						span.role-badge.badge-full.mr-2 {{ $t('Signed up') }}
						form.ts-inline-form(:action="withdrawUrl", method="post")
							input(type="hidden", name="csrfmiddlewaretoken", :value="csrfToken")
							button.btn.btn-sm.btn-danger(type="submit", @click.stop, @pointerdown.stop) {{ $t('Drop shift') }}
					template(v-else-if="hasClaimableSlot")
						form.ts-inline-form(:action="claimUrl", method="post")
							input(type="hidden", name="csrfmiddlewaretoken", :value="csrfToken")
							button.btn.btn-sm.btn-primary(type="submit", @click.stop, @pointerdown.stop) {{ $t('Sign Up') }}
					template(v-else)
						span.text-muted(style="font-size:11px") {{ $t('Full / Restricted') }}
			
			.shift-manage.mt-2.text-right(v-else-if="!isBreak")
				button.btn.btn-sm.btn-outline-primary(type="button", @pointerdown.stop, @click.stop="$emit('assignMembers', session)") {{ session.roles?.some(r => r.assigned.length < r.capacity) ? $t('Assign Members') : $t('Manage') }}
		
		template(v-else)
			.speakers(v-if="hasSpeakersWithNames", :class="{'speakers-clamped': isShortSession}") {{ speakerNames }}
			.pending-line(v-if="session.state === 'pending'")
				i.fa.fa-exclamation-circle
				span {{ $t('Pending proposal state') }}
			.bottom-info(v-if="!isBreak && (session.track || session.do_not_record)")
				.track(v-if="session.track") {{ getLocalizedString(session.track.name) }}
				.do_not_record.no-print(v-if="session.do_not_record", :title="$t('This session will not be recorded.')", :aria-label="$t('This session will not be recorded.')")
					svg(viewBox="0 0 116.59076 116.59076", width="24px", height="24px", fill="none", xmlns="http://www.w3.org/2000/svg", aria-hidden="true")
						g(transform="translate(-9.3465481,-5.441411)")
							rect(style="fill:#000000;fill-opacity;stroke:none;stroke-width:11.2589;stroke-linecap:round;stroke-dasharray:none;stroke-opacity:1;paint-order:markers stroke fill", width="52.753284", height="39.619537", x="35.496307", y="43.927021", rx="5.5179553", ry="7.573648")
							path(style="fill:#000000;fill-opacity:1;stroke:none;stroke-width:18.7997;stroke-linecap:round;stroke-dasharray:none;stroke-opacity:1;paint-order:markers stroke fill", d="M 99.787546,47.04792 V 80.425654 L 77.727407,63.736793 Z")
							path(style="fill:none;stroke:#b23e65;stroke-width:12;stroke-linecap:round;stroke-dasharray:none;stroke-opacity:1;paint-order:markers stroke fill", d="m 35.553146,95.825578 64.177559,-64.17757 m 16.294055,32.08879 A 48.382828,48.382828 0 0 1 67.641925,112.11961 48.382828,48.382828 0 0 1 19.259099,63.736798 48.382828,48.382828 0 0 1 67.641925,15.353968 48.382828,48.382828 0 0 1 116.02476,63.736798 Z")
	.warning.no-print(v-if="warnings?.length")
		.warning-icon.text-danger
			span(v-if="warnings.length > 1") {{ warnings.length }}
			i.fa.fa-exclamation-triangle
</template>

<script lang="ts" setup>
import { computed } from 'vue'
import moment, { Moment } from 'moment-timezone'
import { getLocalizedString } from '~/utils'
import { getCapabilities, resolveMode, resolveSessionKind, getClaimedShiftIds, getCsrfToken, getClaimBaseUrl } from '~/teamshifts-adapter'
import type { Capabilities } from '~/teamshifts-adapter/types'
import type { RoleAssignment } from '~/schemas'

interface Speaker {
  name: string
  code?: string
  [key: string]: string | undefined
}

interface Track {
  name: string | Record<string, string>
  color?: string
  id?: number | string
  [key: string]: string | number | Record<string, string> | undefined
}

interface Session {
  id: number | string
  title: string | Record<string, string>
  speakers?: Speaker[]
  state?: string
  track?: Track
  start?: Moment
  end?: Moment
  code?: string | null
  duration: number
  abstract?: string
  room?: string | number
  do_not_record?: boolean
  roles?: RoleAssignment[]
  [key: string]: string | number | boolean | Record<string, string> | Speaker[] | Track | Moment | RoleAssignment[] | null | undefined
}

interface Warning {
  message: string
  type?: string
  [key: string]: string | undefined
}

const props = defineProps<{
  session: Session
  warnings?: Warning[]
  isDragged?: boolean
  isDragClone?: boolean
  overrideStart?: Moment | null
}>()

const emit = defineEmits<{
  (e: 'startDragging', payload: { session: Session; event: PointerEvent }): void
  (e: 'editSession', payload: Session): void
  (e: 'deleteSession', payload: Session): void
  (e: 'assignMembers', payload: Session): void
}>()
const isBreak = computed(() => resolveSessionKind(mode, props.session) === 'break')

const mode = resolveMode()
const caps: Capabilities = getCapabilities(mode)
const claimedShiftIds = computed(() => caps.showClaimUI ? getClaimedShiftIds() : new Set<number>())
const isMyClaimed = computed(() => claimedShiftIds.value.has(Number(props.session.id)))

const hasClaimableSlot = computed(() => {
  if (!props.session.roles?.length) return false
  return props.session.roles.some(
    (r) => !r.is_restricted && r.assigned.length < r.capacity
  )
})

const claimUrl = computed(() => {
  const base = getClaimBaseUrl()
  return base ? `${base}${props.session.id}/claim/` : ''
})

const withdrawUrl = computed(() => {
  const base = getClaimBaseUrl()
  return base ? `${base}${props.session.id}/withdraw/` : ''
})

const csrfToken = computed(() => caps.showClaimUI ? getCsrfToken() : '')

const getCapacityClass = (role: RoleAssignment) => {
  if (role.assigned.length >= role.capacity) return 'badge-full'
  if (role.assigned.length === 0) return 'badge-empty'
  return 'badge-partial'
}
const hasSpeakersWithNames = computed(() => {
  return props.session.speakers && props.session.speakers.some(speaker => speaker.name)
})

const speakerNames = computed(() => {
  if (!props.session.speakers) return ''
  return props.session.speakers
    .filter(speaker => speaker.name) // Only include speakers with names
    .map(speaker => speaker.name)
    .join(', ')
})

const classes = computed(() => {
  const cls: string[] = []

  if (isBreak.value) {
    cls.push('isbreak')
  } else {
    cls.push('istalk')

    if (props.session.state === 'pending') {
      cls.push('pending')
    } else if (
      props.session.state &&
      props.session.state !== 'confirmed' &&
      props.session.state !== 'accepted'
    ) {
      cls.push('unconfirmed')
    } else if (props.session.state !== 'confirmed') {
      // covers null / undefined / empty state
      cls.push('unconfirmed')
    }
  }

  if (props.isDragged) cls.push('dragging')
  if (props.isDragClone) cls.push('clone')
  if (isShortSession.value) cls.push('short-session')

  return cls
})


const style = computed(() => {
  let trackColor = props.session.track?.color || 'var(--color-primary)'
  
  if (caps.showRoles && props.session.roles && props.session.roles.length > 0) {
    let totalCapacity = 0
    let totalAssigned = 0
    for (const role of props.session.roles) {
      totalCapacity += role.capacity
      totalAssigned += role.assigned?.length || 0
    }
    if (totalCapacity > 0) {
      if (totalAssigned >= totalCapacity) {
        trackColor = '#28a745'
      } else if (totalAssigned === 0) {
        trackColor = '#dc3545'
      } else {
        trackColor = '#ffc107'
      }
    }
  }

  return {
    '--track-color': trackColor
  }
})

const startTime = computed< { time: string; ampm?: string } | undefined>(() => {
  const time: Moment | undefined = props.overrideStart || props.session.start
  if (!time) return undefined

  if (moment.localeData().longDateFormat('LT').endsWith(' A')) {
    return {
      time: time.format('h:mm'),
      ampm: time.format('A'),
    }
  } else {
    return { time: time.format('LT') }
  }
})

const durationMinutes = computed<number>(() => {
  if (!props.session.start || !props.session.end) return props.session.duration
  return moment(props.session.end).diff(props.session.start, 'minutes')
})

const isShortSession = computed<boolean>(() => {
  const minutes = durationMinutes.value
  return minutes > 0 && minutes <= 15
})

const durationPretty = computed<string | undefined>(() => {
  const minutes = durationMinutes.value
  if (!minutes) return undefined

  if (minutes <= 60) {
    return `${minutes}min`
  }
  const hours = Math.floor(minutes / 60)
  const leftoverMinutes = minutes % 60
  if (leftoverMinutes) {
    return `${hours}h${leftoverMinutes}min`
  }
  return `${hours}h`
})

function onPointerDown(event: PointerEvent): void {
  if (!event.isPrimary || event.button !== 0) return
  emit('startDragging', { session: props.session, event })
}
</script>

<style lang="stylus">
sessionTextClamp(lines)
	min-width: 0
	display: -webkit-box
	-webkit-line-clamp: lines
	line-clamp: lines
	-webkit-box-orient: vertical
	overflow: hidden
	overflow-wrap: break-word
	overflow-wrap: anywhere
	word-break: break-word
	text-overflow: ellipsis

sessionTextExpand()
	display: block
	-webkit-line-clamp: unset
	line-clamp: unset
	-webkit-box-orient: unset
	overflow: hidden
	white-space: normal
	overflow-wrap: break-word
	overflow-wrap: anywhere
	word-break: break-word
	text-overflow: clip

.c-linear-schedule-session
	display: flex
	min-width: 300px
	min-height: 96px
	margin: 8px
	overflow: hidden
	color: $clr-primary-text-light
	position: relative
	cursor: pointer
	&.clone
		z-index: 200
	&.dragging
		filter: opacity(0.3)
		cursor: inherit
	&.isbreak
		background-color: $clr-grey-200
		border-radius: 6px
		.time-box
			background-color: $clr-grey-500
			.start
				color: $clr-primary-text-dark
			.duration
				color: $clr-secondary-text-dark
		.info
			justify-content: center
			align-items: center
			.title
				font-size: 20px
				color: $clr-secondary-text-light
				align: center
	&.istalk
		.time-box
			background-color: var(--track-color)
			.start
				color: $clr-primary-text-dark
			.duration
				color: $clr-secondary-text-dark
		.info
			border: 1px solid $clr-dividers-light
			border-left: none
			border-radius: 0 6px 6px 0
			background-color: $clr-white
			.title
				font-size: 16px
				margin-bottom: 4px
		&:hover
			.info
				border: 1px solid var(--track-color)
				border-left: none
				.title
					color: var(--color-primary)
	&.pending, &.unconfirmed
		.time-box
			opacity: 0.5
		.info
			background-image: repeating-linear-gradient(-38deg, $clr-grey-100, $clr-grey-100 10px, $clr-white 10px, $clr-white 20px)
		&:hover
			.info
				border: 1px solid var(--track-color)
				border-left: none
				.title
					color: var(--color-primary)
	&.pending
		.info
			border-style: dashed dashed dashed none
	.time-box
		width: 69px
		box-sizing: border-box
		padding: 12px 16px 8px 12px
		border-radius: 6px 0 0 6px
		display: flex
		flex-direction: column
		align-items: center
		.start
			font-size: 16px
			font-weight: 600
			margin-bottom: 8px
			display: flex
			flex-direction: column
			align-items: flex-end
			&.has-ampm
				align-self: stretch
			.ampm
				font-weight: 400
				font-size: 13px
	.info
		flex: auto
		display: flex
		flex-direction: column
		padding: 8px
		min-width: 0
		.title
			font-weight: 500
			&.title-clamped
				sessionTextClamp(2)
		.speakers
			color: $clr-secondary-text-light
			&.speakers-clamped
				sessionTextClamp(1)
		.bottom-info
			flex: auto
			display: flex
			align-items: flex-end
			gap: 4px
			min-width: 0
			.track
				flex: 1
				min-width: 0
				color: var(--track-color)
				ellipsis()
			.do_not_record
				flex: none
				display: flex
				align-items: center
				line-height: 0
	.pending-line
		color: $clr-warning
		.fa
			margin-right: 4px
	.warning
		position: absolute
		top: 0
		right: 0
		padding: 4px
		margin: 4px
		color: #b23e65
		font-size: 16px
		.warning-icon span
			padding-right: 4px

	@media (hover: hover) and (pointer: fine)
		&:hover:not(.dragging, .clone)
			.title.title-clamped, .speakers.speakers-clamped
				sessionTextExpand()

	.roles-list
		display: flex
		flex-direction: column
		gap: 6px
		margin-top: 6px
		.role-item
			border-top: 1px solid $clr-dividers-light
			padding-top: 6px
			.role-header
				display: flex
				justify-content: space-between
				align-items: center
				font-size: 13px
				font-weight: 600
				.role-restricted-tag
					margin-left: 6px
					font-size: 10px
					font-weight: 700
					text-transform: uppercase
					letter-spacing: 0.02em
					padding: 1px 5px
					border-radius: 3px
					background-color: #6c757d
					color: $clr-white
				.role-badge
					font-size: 11px
					padding: 2px 6px
					border-radius: 12px
					border: 1px solid
					&.badge-full
						border-color: #28a745
						color: #28a745
					&.badge-empty
						border-color: #dc3545
						color: #dc3545
					&.badge-partial
						border-color: #ffc107
						color: #ffc107
			.role-assignees
				font-size: 12px
				color: $clr-secondary-text-light
				margin-top: 2px
				i.fa
					font-size: 10px
	.shift-manage
		font-size: 12px
		.btn
			padding: 2px 8px
			font-size: 12px
	.ts-inline-form
		display: inline

@media print
	.c-linear-schedule-session.isbreak
		border: 2px solid $clr-grey-300 !important
	.c-linear-schedule-session.istalk .time-box
		border: 2px solid var(--track-color) !important
	.c-linear-schedule-session.istalk .info
		border-right: 2px solid var(--track-color) !important
		border-top: 2px solid var(--track-color) !important
		border-bottom: 2px solid var(--track-color) !important


</style>

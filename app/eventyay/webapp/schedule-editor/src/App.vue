<template lang="pug">
.pretalx-schedule(:class="[draggedSession ? 'is-dragging' : '', !caps.canDrag ? 'is-public-shifts' : '']", @pointerup="caps.canDrag ? stopDragging($event) : null")
	teleport(to="body")
		.dragged-session-avatar(
			v-if="draggedSession && isPointerDragging",
			ref="dragAvatarEl"
		)
			session(
				:session="draggedSession",
				:isDragClone="true"
			)
	teleport(to="#schedule-timezone-mount", v-if="isMounted && schedule")
		.schedule-timezone-selector(ref="timezoneDropdownRef")
			button.timezone-btn(
				type="button",
				@click="showTimezoneMenu = !showTimezoneMenu",
				:title="currentTimezone",
				:aria-expanded="showTimezoneMenu ? 'true' : 'false'"
			)
				i.fa.fa-globe(aria-hidden="true")
				span.timezone-btn-text {{ displayTimezoneShort }}
				i.fa.fa-caret-down(aria-hidden="true")
			.timezone-dropdown-menu(v-if="showTimezoneMenu", @click.stop)
				.tz-section-label {{ $t('Pinned') }}
				.tz-option(
					v-for="opt in pinnedTimezones",
					:key="opt.id",
					:class="{ active: currentTimezone === opt.id }",
					@click="selectTimezone(opt.id)"
				)
					span.tz-option-name {{ opt.label }}
					i.fa.fa-check(v-if="currentTimezone === opt.id", aria-hidden="true")
				.tz-divider
				.tz-section-label {{ $t('Other Timezones') }}
				.tz-search-wrapper
					i.fa.fa-search(aria-hidden="true")
					input.tz-search-input(
						type="text",
						v-model="timezoneSearchQuery",
						:placeholder="$t('Search timezones…')",
						@click.stop
					)
				.tz-options-scroll
					.tz-option(
						v-for="opt in filteredOtherTimezones",
						:key="opt.id",
						:class="{ active: currentTimezone === opt.id }",
						@click="selectTimezone(opt.id)"
					)
						span.tz-option-name {{ opt.label }}
						i.fa.fa-check(v-if="currentTimezone === opt.id", aria-hidden="true")
	teleport(to="#schedule-fullscreen-mount", v-if="isMounted && schedule")
		button#schedule-fullscreen-btn.btn.btn-sm(
			type="button",
			@click="toggleFullscreen",
			:class="{'btn-primary': isFullscreen, 'btn-outline-secondary': !isFullscreen}",
			:title="isFullscreen ? $t('Exit fullscreen') : $t('Fullscreen')",
			:aria-label="isFullscreen ? $t('Exit fullscreen') : $t('Fullscreen')"
		)
			i.fa(:class="isFullscreen ? 'fa-compress' : 'fa-arrows-alt'", aria-hidden="true")
			span.ml-1.d-none.d-sm-inline {{ isFullscreen ? $t('Exit fullscreen') : $t('Fullscreen') }}
	template(v-if="schedule")
		#main-wrapper
			#unassigned.no-print(v-if="caps.canDrag", :class="{'is-sidebar-collapsed': isSidebarCollapsed, 'is-collapsed': isUnassignedCollapsed, 'is-unassign-target': isUnassigning && canDropToDismissOrUnassign, 'is-break-target': isUnassigning && canDropToDismissOrUnassign && !draggedSession?.code}", @pointerenter="onUnassignedEnter", @pointerleave="onUnassignedLeave")
				.unassigned-mobile-header(@click="isUnassignedCollapsed = !isUnassignedCollapsed")
					span.unassigned-title
						i.fa.fa-list
						span {{ translations.unassignedTitle }} ({{ unscheduled.length }})
						span.drop-hint(v-if="canDropToDismissOrUnassign", :class="{'is-break-hint': !draggedSession?.code}")  - {{ !draggedSession?.code ? $t('Drop here to dismiss') : $t('Drop here to unassign') }}
					span.unassigned-collapse-icon
						i.fa(:class="isUnassignedCollapsed ? 'fa-chevron-down' : 'fa-chevron-up'")
				.unassigned-body
					p.unschedule-hint(v-if="unscheduleHint", role="status") {{ unscheduleHint }}
					.unassigned-drop-zone(v-if="canDropToDismissOrUnassign", :class="{'is-hovered': isUnassigning, 'is-break-drop': !draggedSession?.code}")
						.drop-zone-main
							.drop-zone-icon-wrap
								i.fa(:class="!draggedSession?.code ? 'fa-trash' : 'fa-inbox'")
							.drop-zone-content
								span.drop-zone-title {{ !draggedSession?.code ? $t('Drop here to dismiss break') : translations.unassignDropTitle }}
								span.drop-zone-subtitle {{ !draggedSession?.code ? $t('Removes break from timetable') : translations.unassignDropSubtitle }}
						.drop-zone-preview(v-if="isUnassigning && draggedSession")
							session.unassigned-preview-pill(
								:session="draggedSession",
								:isDragClone="true"
							)
					.unassigned-header
						.density-controls
							button.density-btn(:class="{active: condensedView}", @click="toggleCondensedView", :title="condensedView ? $t('Normal view') : $t('Condensed view')", :aria-pressed="condensedView.toString()")
								i.fa(:class="condensedView ? 'fa-expand' : 'fa-compress'", aria-hidden="true")
								span.density-btn-text {{ condensedView ? $t('Normal view') : $t('Condensed view') }}
							.select-wrapper.custom-dropdown(ref="customDropdownRef", @click="showTimeDensityMenu = !showTimeDensityMenu", :class="{'active': showTimeDensityMenu}")
								span.time-density-display {{ timeDensityMinutes }} {{ $t('min') }}
								i.fa.fa-chevron-down(aria-hidden="true")
								.time-density-menu.vue-dropdown(v-if="showTimeDensityMenu")
									.density-option(v-for="mins in [5, 10, 15, 30, 60]", @click.stop="timeDensityMinutes = mins; onTimeDensityChange(); showTimeDensityMenu = false", :class="{active: timeDensityMinutes === mins}") {{ mins }} {{ $t('min') }}
						.search-row
							.search-input-wrapper
								i.fa.fa-search(aria-hidden="true")
								input.search-input(
									type="text"
									v-model="unassignedFilterString"
									:placeholder="translations.searchSessions"
									:aria-label="translations.searchSessions"
								)
								button.clear-search-btn(
									v-if="unassignedFilterString"
									type="button"
									@click="unassignedFilterString = ''"
									:title="$t('Clear search')"
									:aria-label="$t('Clear search')"
								)
									i.fa.fa-times(aria-hidden="true")
							button#unassigned-sort(
								type="button"
								@click="showUnassignedSortMenu = !showUnassignedSortMenu"
								:class="{'active': showUnassignedSortMenu}"
								:title="$t('Sort')"
								:aria-label="$t('Sort')"
							)
								i.fa.fa-sort-amount-desc(aria-hidden="true")
							#unassigned-sort-menu(v-if="showUnassignedSortMenu")
								.sort-method(v-for="method of unassignedSortMethods", :key="method.name", @click="unassignedSort === method.name ? unassignedSortDirection = unassignedSortDirection * -1 : unassignedSort = method.name; showUnassignedSortMenu = false")
									span {{ method.label }}
									i.fa.fa-sort-amount-asc(v-if="unassignedSort === method.name && unassignedSortDirection === 1")
									i.fa.fa-sort-amount-desc(v-if="unassignedSort === method.name && unassignedSortDirection === -1")
						session.new-break.desktop-break(v-if="caps.canCreateBreak", :session="{title: '+ ' + translations.newBreak, code: null}", :isDragged="false", tabindex="0", @startDragging="startNewBreak", @click.stop="showNewBreakHint", @focus="showNewBreakHint", @blur="removeNewBreakHint", @keydown="onNewBreakKeydown", @pointerleave="removeNewBreakHint", :aria-describedby="newBreakTooltip ? 'new-break-hint' : undefined")
						.new-break-hint(v-if="newBreakTooltip", id="new-break-hint", role="tooltip") {{ newBreakTooltip }}
					session(v-for="un in unscheduled", :key="un.id", :session="un", @startDragging="startDragging", :isDragged="draggedSession && un.id === draggedSession.id", @editSession="editorStart($event)", @deleteSession="deleteSessionDirect($event)", @assignMembers="openAssignModal($event)")
					.deleted-room-sessions(v-if="deletedRoomSessions.length")
						h3 {{ caps.showRoles ? $t('Shifts from Unavailable Rooms') : $t('Deleted Room Sessions') }}
						p {{ caps.showRoles ? $t('These shifts were in a room that has been deleted or unscheduled. Drag them into another room to restore them to the schedule.') : $t('These sessions were assigned to a room that has been deleted. Drag them into another room to restore them to the schedule.') }}
						session(v-for="session in deletedRoomSessions", :key="session.id", :session="session", @startDragging="startDragging", :isDragged="draggedSession && session.id === draggedSession.id")
			.sidebar-divider-line(v-if="caps.canDrag", :class="{'is-collapsed': isSidebarCollapsed}")
			button.sidebar-divider-toggle.btn-circle(
				v-if="caps.canDrag",
				type="button",
				:class="{'is-collapsed': isSidebarCollapsed}",
				@click="toggleSidebar",
				:title="isSidebarCollapsed ? $t('Show unscheduled sessions') : $t('Collapse unscheduled sessions')",
				:aria-label="isSidebarCollapsed ? $t('Show unscheduled sessions') : $t('Collapse unscheduled sessions')"
			)
				i.fa(:class="isSidebarCollapsed ? 'fa-bars' : 'fa-chevron-left'", aria-hidden="true")
			#schedule-wrapper
				.schedule-action-toast(v-if="scheduleActionError", role="alert")
					span {{ scheduleActionError }}
					button.action-toast-dismiss(type="button", @click="scheduleActionError = ''", :aria-label="$t('Dismiss')")
						i.fa.fa-times(aria-hidden="true")
				.schedule-controls(:style="actionsControlsStyle")
					.date-selector(v-if="days && days.length", role="tablist", :aria-label="$t('Select date')")
						button.day-btn(
							v-for="day of days",
							:key="day.format('YYYY-MM-DD')",
							type="button",
							role="tab",
							:id="`day-tab-${day.format('YYYY-MM-DD')}`",
							:class="{ active: currentDay && day.isSame(currentDay, 'day') }",
							:aria-selected="currentDay && day.isSame(currentDay, 'day') ? 'true' : 'false'",
							@click="changeDay(day)"
						)
							| {{ day.format(dateFormat) }}
				grid-schedule(:sessions="sessions",
					:density="gridDensity",
					:timeDensityMinutes="timeDensityMinutes",
					:rooms="schedule.rooms",
					:availabilities="availabilities",
					:warnings="warnings",
					:start="days[0]",
					:end="days.at(-1).clone().endOf('day')",
					:currentDay="currentDay",
					:draggedSession="draggedSession",
					:isUnassigning="isUnassigning",
					:allowOverlap="caps.allowOverlap",
					@changeDay="changeDay",
					@startDragging="caps.canDrag ? startDragging($event) : null",
					@rescheduleSession="caps.canDrag ? rescheduleSession($event) : null",
					@createSession="caps.canEdit ? createSession($event) : null",
					@editSession="caps.canEdit ? editorStart($event) : null",
					@deleteSession="caps.canDelete ? deleteSessionDirect($event) : null",
					@assignMembers="caps.canAssignMembers ? openAssignModal($event) : null",
					@unscheduleSession="caps.canDrag ? unscheduleSession($event) : null")
			#session-editor-wrapper(v-if="editorSession && caps.canEdit", @click="editorCancel")
				form#session-editor(@click.stop="", @submit.prevent="editorSave", @keydown.enter="editorSubmit")
					h3.session-editor-title(v-if="editorSession.code")
						a(v-if="caps.showSubmissionLinks && organizerSlug && eventSlug", :href="`${api.getOrgaEventBase()}/submissions/${editorSession.code}/`") {{ getLocalizedString(editorSession.title) }}
						span(v-else) {{ getLocalizedString(editorSession.title) }}
					.session-editor-error(v-if="editorSessionError")
						span {{ editorSessionError }}
						button.session-editor-error-dismiss(type="button", @click="editorSessionError = ''", :aria-label="$t('Dismiss')")
							i.fa.fa-times(aria-hidden="true")
					.data
						.data-row(v-if="editorSession.code && editorSession.speakers && editorSession.speakers.length > 0 && caps.showSpeakers").form-group.row
							label.data-label.col-form-label.col-md-3 {{ $t('Speakers') }}
							.col-md-9.data-value
								span(v-for="speaker, index of editorSession.speakers")
									a(v-if="caps.showSubmissionLinks && organizerSlug && eventSlug && speaker.code", :href="`${api.getOrgaEventBase()}/speakers/${speaker.code}/`") {{ speaker.name || speaker.code }}
									span(v-else) {{ speaker.name }}
									span(v-if="index != editorSession.speakers.length - 1") {{', '}}
								span.text-warning(v-if="editorSession.speakers.some(s => !s.name)")  ({{ $t('some speakers have not shared their names') }})
						.data-row(v-else).form-group.row
							label.data-label.col-form-label.col-md-3 {{ $t('Title') }}
							.col-md-9
								.i18n-form-group
									template(v-for="locale of locales")
										input.form-control(v-model="editorSession.title[locale]", :required="true", :lang="locale", type="text")
						.data-row(v-if="editorSession.track && caps.showTracks").form-group.row
							label.data-label.col-form-label.col-md-3 {{ $t('Track') }}
							.col-md-9.data-value {{ getLocalizedString(editorSession.track.name) }}
						.data-row(v-if="editorSession.code && (editorSession.session_type || editorSession.submission_type)").form-group.row
							label.data-label.col-form-label.col-md-3 {{ $t('Session type') }}
							.col-md-9.data-value {{ getLocalizedString(editorSession.session_type || editorSession.submission_type) }}
						.data-row(v-if="editorSession.room").form-group.row
							label.data-label.col-form-label.col-md-3 {{ $t('Room') }}
							.col-md-9.data-value {{ getLocalizedString(editorSession.room.name) }}
						.data-row.form-group.row
							label.data-label.col-form-label.col-md-3 {{ $t('Duration') }}
							.col-md-9.number.input-group
								input.form-control(v-model="editorSession.duration", type="number", min="1", max="1440", step="1", :required="true")
								.input-group-append
									span.input-group-text {{ $t('minutes') }}
						.data-row(v-if="caps.canEditRoles").form-group.row
							label.data-label.col-form-label.col-md-3 {{ $t('Roles') }}
							.col-md-9
								.role-row(v-for="(r, index) in editorSession.roles" :key="index")
									select.form-control.role-select(v-model="r.id", required)
										option(:value="undefined" disabled) {{ $t('Select a role') }}
										option(v-for="role in schedule?.roles", :key="role.id", :value="role.id") {{ getLocalizedString(role.name) }}
									input.form-control.role-capacity(v-model.number="r.capacity", type="number", min="1", required, :title="$t('Capacity')")
									a.text-danger(href="#", @click.prevent="editorSession.roles.splice(index, 1)")
										i.fa.fa-trash
								a(href="#", @click.prevent="editorSession.roles.push({id: undefined, capacity: 1})")
									i.fa.fa-plus
									|  {{ $t('Add Role') }}


						.data-row.session-warnings.form-group.row(v-if="editorSession.code && warnings[editorSession.code] && warnings[editorSession.code].length")
							label.data-label.col-form-label.col-md-3.session-warnings-label
								i.fa.fa-exclamation-triangle(aria-hidden="true")
								span {{ $t('Warnings') }}
							.col-md-9.data-value
								ul.session-warnings-list
									li(v-for="warning of warnings[editorSession.code]") {{ warning.message }}
					.button-row
						input(type="submit")
						bunt-button#btn-delete(v-if="caps.canEditRoles ? editorSession.id : !editorSession.code", @click="editorDelete", :loading="editorSessionWaiting") {{ $t('Delete') }}
						bunt-button#btn-cancel(type="button", @click="editorCancel") {{ $t('Cancel') }}
						bunt-button#btn-save(@click="editorSave", :loading="editorSessionWaiting") {{ $t('Save') }}
			
			#assign-modal-wrapper(v-if="assigningSession && caps.canAssignMembers", @click="closeAssignModal")
				#session-editor(@click.stop="")
					h3.session-editor-title
						span {{ assignMembersHeading }}
						button.modal-close-btn(type="button", @click="closeAssignModal", :aria-label="$t('Close')")
							i.fa.fa-times(aria-hidden="true")
					
					.assign-modal-error(v-if="assignModalError")
						span {{ assignModalError }}
						button.assign-modal-error-dismiss(type="button", @click="assignModalError = ''", :aria-label="$t('Dismiss')")
							i.fa.fa-times(aria-hidden="true")
					
					.data.assign-data
						.assign-role(v-for="role in assigningSession.roles", :key="role.id")
							h4 {{ getLocalizedString(role.name) }} ({{ role.assigned.length }}/{{ role.capacity }} {{ $t('assigned') }})
							
							.assigned-list
								span.member-chip(v-for="user in role.assigned", :key="user.id")
									| {{ user.name }}
									button.member-chip-remove(type="button", @click="unassignMember(role.id, user.id)", :aria-label="$t('Unassign')", :title="$t('Unassign')")
										i.fa.fa-times(aria-hidden="true")
								p.text-muted(v-if="!role.assigned.length") {{ $t('No members assigned yet.') }}
							
							.assign-new.form-group.row
								.col-md-8
									select.form-control(v-model="selectedMemberIds[role.id]")
										option(:value="undefined" disabled) {{ $t('Select a member to assign') }}
										option(v-for="vol in availableMembersByRole[role.id]", :key="vol.id", :value="vol.id") {{ vol.name }}{{ vol.email ? ` (${vol.email})` : '' }}
								.col-md-4
									button.assign-btn(type="button", @click="assignMember(role.id)", :disabled="assigningWaiting") {{ $t('Assign') }}

		confirm-dialog(
			v-if="caps.showRoles",
			ref="confirmDialogRef",
			:title="confirmDialogTitle",
			:lead="confirmDialogLead",
			:confirm-label="confirmDialogLabel",
			:confirm-class="confirmDialogClass",
			:busy="confirmDialogBusy",
			:error="confirmDialogError",
			@confirm="onConfirmDialogConfirm",
			@cancel="onConfirmDialogCancel")

		dialog.break-confirm-dialog(ref="breakConfirmDialogEl", @click="onBreakDialogBackdrop", @cancel.prevent="cancelBreakDelete")
			.dialog-inner(@click.stop="")
				h3 {{ breakConfirmTitle }}
				p {{ breakConfirmLead }}
				p.break-confirm-error(v-if="breakConfirmError") {{ breakConfirmError }}
				.break-confirm-actions
					button.btn.btn-sm.btn-default(type="button", :disabled="breakConfirmBusy", @click="cancelBreakDelete") {{ $t('Cancel') }}
					button.btn.btn-sm.btn-danger(type="button", :disabled="breakConfirmBusy", @click="confirmBreakDelete") {{ $t('Delete') }}

	bunt-progress-circular(v-else, size="huge", :page="true")
</template>

<script lang="ts" setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted, onBeforeMount, nextTick } from 'vue'
import moment, { Moment } from 'moment-timezone'
import GridSchedule from '~/components/GridSchedule.vue'
import TalkSession from '~/components/Session.vue'
import ShiftSession from '~/teamshifts-adapter/Session.vue'
import ConfirmDialog from '~/teamshifts-adapter/ConfirmDialog.vue'
import api from '~/api'
import { resolveMode, getCapabilities } from '~/teamshifts-adapter'
import type { Capabilities } from '~/teamshifts-adapter/types'
import { getLocalizedString } from '~/utils'
import {translate as $t} from '~/lib/i18n'
import type { AvailabilityEntry, RoleAssignment, ScheduleRole } from '~/schemas';

interface Speaker {
  code?: string | null
  name: string
}

interface Track {
  id: string | number
  name: Record<string, string>
}

interface Room {
  id: string | number
  name: Record<string, string>
}

interface Warning {
  message: string
}

interface Talk {
  id: number
  code: string
  title: Record<string, string>
  abstract?: string
  speakers?: string[]
  track?: string | number
  room?: string | number
  duration: number
  start?: string | null
  end?: string | null
  state?: string
  updated?: string
  submission?: Record<string, unknown>
  uncreated?: boolean
  availabilities?: AvailabilityEntry[]
  do_not_record?: boolean
  roles?: RoleAssignment[]
  role?: string | number
  capacity?: number
  session_type?: string | Record<string, string>
  submission_type?: string | Record<string, string>
}

interface EditorRoleEntry {
  id?: number
  capacity: number
}

interface SessionData {
  id: number
  code?: string
  title: Record<string, string> | string
  abstract?: string
  speakers?: Speaker[]
  track?: Track
  duration?: number
  start?: Moment
  end?: Moment
  state?: string
  room?: Room
  deletedRoom?: boolean
  uncreated?: boolean
  availabilities?: AvailabilityEntry[]
  do_not_record?: boolean
  roles?: (RoleAssignment | EditorRoleEntry)[]
  role?: string | number
  capacity?: number
  session_type?: string | Record<string, string>
  submission_type?: string | Record<string, string>
}

interface SortMethod {
  label: string
  name: string
}

interface Schedule {
  version: string
  event_start: string
  event_end: string
  timezone: string
  locales: string[]
  rooms: Room[]
  tracks: Track[]
  speakers: Speaker[]
  talks: Talk[]
  now?: string
  roles?: ScheduleRole[]
}

const props = defineProps<{
  locale: string
}>()

const mode = resolveMode()
const caps: Capabilities = getCapabilities(mode)
const Session = mode === 'shifts' || mode === 'public-shifts' ? ShiftSession : TalkSession

const eventSlug = ref<string | null>(null)
const organizerSlug = ref<string | null>(null)
const scrollParentWidth = ref<number>(Infinity)
const schedule = ref<Schedule | null>(null)
const isUnassignedCollapsed = ref<boolean>(true)
const availabilities = reactive<{ rooms: Record<string, AvailabilityEntry[]>; talks: Record<string, AvailabilityEntry[]> }>({
  rooms: {},
  talks: {},
})
const availableMembersByRole = ref<Record<string, { id: number; name: string; email?: string }[]>>({})
const warnings = reactive<Record<string, Warning[]>>({})
const currentDay = ref<Moment | null>(null)
const draggedSession = ref<SessionData | null>(null)
const editorSession = ref<SessionData | null>(null)
const editorSessionWaiting = ref<boolean>(false)
const editorSessionError = ref<string>('')
const assigningSession = ref<SessionData | null>(null)
const assigningWaiting = ref<boolean>(false)
const assignModalError = ref<string>('')
const selectedMemberIds = ref<Record<string, number | undefined>>({})

const confirmDialogRef = ref<InstanceType<typeof ConfirmDialog> | null>(null)
const confirmDialogTitle = ref('')
const confirmDialogLead = ref('')
const confirmDialogLabel = ref('')
const confirmDialogClass = ref('btn-primary')
const confirmDialogBusy = ref(false)
const confirmDialogError = ref('')
let confirmDialogResolve: ((value: boolean) => void) | null = null
let confirmDialogAction: (() => Promise<void>) | null = null

const breakConfirmDialogEl = ref<HTMLDialogElement | null>(null)
const breakConfirmTitle = ref('')
const breakConfirmLead = ref('')
const breakConfirmError = ref('')
const breakConfirmBusy = ref(false)
let breakConfirmResolve: ((value: boolean) => void) | null = null
let breakDeleteId: number | string | null = null
const pendingBreakCreations = new Map<string, { dismissed: boolean }>()
const pendingBreakDeletions = new Set<string>()
const deletedBreakIds = new Set<string>()

const scheduleActionError = ref<string>('')
let scheduleActionErrorTimer: ReturnType<typeof setTimeout> | null = null

function showScheduleActionError(msg: string) {
  scheduleActionError.value = msg
  if (scheduleActionErrorTimer) clearTimeout(scheduleActionErrorTimer)
  scheduleActionErrorTimer = setTimeout(() => {
    scheduleActionError.value = ''
    scheduleActionErrorTimer = null
  }, 6000)
}

function showBreakConfirmDialog(id: number | string): Promise<boolean> {
  breakDeleteId = id
  breakConfirmTitle.value = $t('Delete break')
  breakConfirmLead.value = $t('Are you sure you want to delete this break?')
  breakConfirmError.value = ''
  breakConfirmBusy.value = false
  return new Promise((resolve) => {
    breakConfirmResolve = resolve
    nextTick(() => breakConfirmDialogEl.value?.showModal?.())
  })
}

async function confirmBreakDelete() {
  if (breakDeleteId == null) return
  const idToDelete = breakDeleteId
  const strId = String(idToDelete)
  const numericId = Number(idToDelete)

  if (pendingBreakCreations.has(strId)) {
    pendingBreakCreations.get(strId)!.dismissed = true
  }

  breakConfirmBusy.value = true
  breakConfirmError.value = ''

  try {
    if (numericId && !isNaN(numericId)) {
      await api.deleteTalk({ id: numericId })
      deletedBreakIds.add(strId)
      deletedBreakIds.add(String(numericId))
    }
    if (schedule.value) {
      schedule.value.talks = schedule.value.talks.filter(
        (s) => String(s.id) !== strId && (isNaN(numericId) || Number(s.id) !== numericId)
      )
    }
    breakConfirmDialogEl.value?.close()
    breakConfirmResolve?.(true)
    breakConfirmResolve = null
    breakDeleteId = null
  } catch (error) {
    console.error('Failed to delete break', { id: numericId, error })
    breakConfirmError.value = $t('Failed to delete break. Please try again.')
    breakConfirmResolve?.(false)
    breakConfirmResolve = null
  } finally {
    breakConfirmBusy.value = false
  }
}

function cancelBreakDelete() {
  breakConfirmDialogEl.value?.close()
  breakConfirmResolve?.(false)
  breakConfirmResolve = null
  breakDeleteId = null
}

function onBreakDialogBackdrop(event: MouseEvent) {
  if (event.target === breakConfirmDialogEl.value) cancelBreakDelete()
}

function showConfirmDialog(opts: { title: string; lead: string; confirmLabel: string; confirmClass?: string; onConfirm?: () => Promise<void> }): Promise<boolean> {
  confirmDialogTitle.value = opts.title
  confirmDialogLead.value = opts.lead
  confirmDialogLabel.value = opts.confirmLabel
  confirmDialogClass.value = opts.confirmClass || 'btn-primary'
  confirmDialogBusy.value = false
  confirmDialogError.value = ''
  confirmDialogAction = opts.onConfirm || null
  return new Promise((resolve) => {
    confirmDialogResolve = resolve
    nextTick(() => confirmDialogRef.value?.show())
  })
}

async function onConfirmDialogConfirm() {
  if (confirmDialogAction) {
    confirmDialogBusy.value = true
    confirmDialogError.value = ''
    try {
      await confirmDialogAction()
      confirmDialogRef.value?.close()
      confirmDialogResolve?.(true)
    } catch (error) {
      confirmDialogError.value = (error as Error).message || $t('An error occurred. Please try again.')
      confirmDialogResolve?.(false)
    } finally {
      confirmDialogBusy.value = false
      confirmDialogResolve = null
      confirmDialogAction = null
    }
  } else {
    confirmDialogRef.value?.close()
    confirmDialogResolve?.(true)
    confirmDialogResolve = null
    confirmDialogAction = null
  }
}

function onConfirmDialogCancel() {
  confirmDialogResolve?.(false)
  confirmDialogResolve = null
  confirmDialogAction = null
}
const isUnassigning = ref<boolean>(false)
const canDropToDismissOrUnassign = computed<boolean>(() => {
  return Boolean(
    draggedSession.value &&
    draggedSession.value.start &&
    draggedSession.value.id
  )
})
const isPointerDragging = ref<boolean>(false)
const dragAvatarEl = ref<HTMLElement | null>(null)
// The ghost is moved by writing transform directly. A reactive style would re-render the whole editor on every pointer event.
let dragPointerX = 0
let dragPointerY = 0
let dragOffsetX = 50
let dragOffsetY = 30
let dragAvatarWidth = 280
let dragOriginX = 0
let dragOriginY = 0
let dragAvatarFrame: number | null = null

function positionDragAvatar() {
  const el = dragAvatarEl.value
  if (!el) return
  el.style.transform = `translate3d(${dragPointerX - dragOffsetX}px, ${dragPointerY - dragOffsetY}px, 0) scale(1.02)`
}

function scheduleDragAvatar() {
  if (dragAvatarFrame !== null) return
  dragAvatarFrame = requestAnimationFrame(() => {
    dragAvatarFrame = null
    positionDragAvatar()
  })
}

function resetDragAvatar() {
  if (dragAvatarFrame !== null) {
    cancelAnimationFrame(dragAvatarFrame)
    dragAvatarFrame = null
  }
}

watch(isPointerDragging, (active) => {
  if (!active) return
  nextTick(() => {
    const el = dragAvatarEl.value
    if (!el) return
    el.style.width = `${dragAvatarWidth}px`
    el.style.visibility = 'visible'
    positionDragAvatar()
  })
})

let cachedUnassignedRect: DOMRect | null = null
let unassignedResizeObserver: ResizeObserver | null = null
watch(draggedSession, (val) => {
  if (!val) {
    cachedUnassignedRect = null
  }
})

function isUnassignedListClosed(): boolean {
  return isMobile.value ? isUnassignedCollapsed.value : isSidebarCollapsed.value
}

function checkIsOverUnassigned(x: number, y: number): boolean {
  if (typeof document === 'undefined') return false
  if (isUnassignedListClosed()) return false
  if (!cachedUnassignedRect) {
    const el = document.getElementById('unassigned')
    cachedUnassignedRect = el ? el.getBoundingClientRect() : null
  }
  const rect = cachedUnassignedRect
  if (!rect) return false
  if (isMobile.value) {
    return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom + 10
  }
  return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom
}

function onGlobalPointerMove(e: PointerEvent) {
  if (!draggedSession.value) return
  dragPointerX = e.clientX
  dragPointerY = e.clientY
  const dist = Math.abs(e.clientX - dragOriginX) + Math.abs(e.clientY - dragOriginY)
  if (dist >= 4 && !isPointerDragging.value) {
    isPointerDragging.value = true
  }
  if (isPointerDragging.value) scheduleDragAvatar()
  const overUnassigned = checkIsOverUnassigned(e.clientX, e.clientY)
  if (overUnassigned !== isUnassigning.value) isUnassigning.value = overUnassigned
}

function onGlobalPointerUp(e: PointerEvent) {
  if (draggedSession.value) {
    stopDragging(e)
  }
}

const isMounted = ref<boolean>(false)
const unscheduleHint = ref<string>('')
let unscheduleHintTimer: ReturnType<typeof setTimeout> | null = null
const locales = ref<string[]>(['en'])
const unassignedFilterString = ref<string>('')
const unassignedSort = ref<string>('title')
const unassignedSortDirection = ref<number>(1)
const showUnassignedSortMenu = ref<boolean>(false)
const newBreakTooltip = ref<string>('')
const eventTimezone = ref<string | null>(null)
const since = ref<string | undefined>(undefined)
const showTimeDensityMenu = ref<boolean>(false)
const customDropdownRef = ref<HTMLElement | null>(null)

const isSidebarCollapsed = ref<boolean>(false)

function toggleSidebar(): void {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
}

watch([isSidebarCollapsed, isUnassignedCollapsed], () => {
  cachedUnassignedRect = null
})

const isFullscreen = ref<boolean>(false)

function getScheduleContainer(): HTMLElement | null {
  return typeof document !== 'undefined' ? document.querySelector('.schedule-editor-container') : null
}

async function toggleFullscreen(): Promise<void> {
  const container = getScheduleContainer()
  if (!container) return
  if (document.fullscreenElement || (document as any).webkitFullscreenElement || isFullscreen.value) {
    await exitFullscreen()
  } else {
    try {
      if (container.requestFullscreen) {
        await container.requestFullscreen()
      } else if ((container as any).webkitRequestFullscreen) {
        await (container as any).webkitRequestFullscreen()
      } else {
        container.classList.add('is-fullscreen')
        isFullscreen.value = true
      }
    } catch (e) {
      container.classList.add('is-fullscreen')
      isFullscreen.value = true
    }
  }
}

async function exitFullscreen(): Promise<void> {
  const container = getScheduleContainer()
  try {
    if (document.fullscreenElement || (document as any).webkitFullscreenElement) {
      if (document.exitFullscreen) {
        await document.exitFullscreen()
      } else if ((document as any).webkitExitFullscreen) {
        await (document as any).webkitExitFullscreen()
      }
    }
  } catch (e) {}
  if (container) {
    container.classList.remove('is-fullscreen')
  }
  isFullscreen.value = false
}

const onFullscreenChange = () => {
  const isDocFs = !!(document.fullscreenElement || (document as any).webkitFullscreenElement)
  isFullscreen.value = isDocFs
  const container = getScheduleContainer()
  if (container) {
    if (isDocFs) {
      container.classList.add('is-fullscreen')
    } else {
      container.classList.remove('is-fullscreen')
    }
  }
}

const onEscapeKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && isFullscreen.value) {
    exitFullscreen()
  }
}

const currentTimezone = ref<string>('')
const timezoneSearchQuery = ref<string>('')
const showTimezoneMenu = ref<boolean>(false)
const timezoneDropdownRef = ref<HTMLElement | null>(null)

const userLocalTimezone = computed<string>(() => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || moment.tz.guess() || 'UTC'
  } catch (e) {
    return 'UTC'
  }
})

const displayTimezoneShort = computed<string>(() => {
  if (!currentTimezone.value) return ''
  return currentTimezone.value.replace(/^.*\//, '').replace(/_/g, ' ')
})

const pinnedTimezones = computed<{ id: string; label: string }[]>(() => {
  const list: { id: string; label: string }[] = []
  const seen = new Set<string>()

  const add = (id: string, suffix: string) => {
    if (!id || seen.has(id)) return
    seen.add(id)
    list.push({ id, label: `${id} (${suffix})` })
  }

  const eventTz = schedule.value?.timezone || 'UTC'
  add(eventTz, 'event')
  add(userLocalTimezone.value, 'local')
  add('UTC', 'UTC')
  return list
})

const allIanaTimezones = computed<string[]>(() => {
  if (typeof Intl !== 'undefined' && typeof (Intl as any).supportedValuesOf === 'function') {
    return (Intl as any).supportedValuesOf('timeZone') || []
  }
  return typeof moment.tz?.names === 'function' ? moment.tz.names() : []
})

const filteredOtherTimezones = computed<{ id: string; label: string }[]>(() => {
  const pinnedIds = new Set(pinnedTimezones.value.map((p) => p.id))
  const q = timezoneSearchQuery.value.trim().toLowerCase()
  return allIanaTimezones.value
    .filter((tz) => !pinnedIds.has(tz) && (!q || tz.toLowerCase().includes(q)))
    .map((tz) => ({ id: tz, label: tz }))
})

function selectTimezone(tz: string): void {
  if (!tz) return
  currentTimezone.value = tz
  moment.tz.setDefault(tz)
  try {
    localStorage.setItem(`schedule_editor_${eventSlug.value || 'default'}_timezone`, tz)
  } catch (e) {}
  showTimezoneMenu.value = false
  if (days.value && days.value.length > 0) {
    const prevDateStr = currentDay.value ? currentDay.value.format('YYYY-MM-DD') : ''
    const matchDay = days.value.find((d) => d.format('YYYY-MM-DD') === prevDateStr)
    currentDay.value = matchDay || days.value[0]
  }
}

const condensedView = ref<boolean>(localStorage.getItem('schedule-editor-condensed') === '1')
const timeDensityMinutes = ref<number>(Number(localStorage.getItem('schedule-time-density-minutes') || 30))

const gridDensity = computed<'compact' | 'default' | 'comfortable'>(() => {
  return condensedView.value ? 'compact' : 'default'
})

function toggleCondensedView (): void {
  condensedView.value = !condensedView.value
  localStorage.setItem('schedule-editor-condensed', condensedView.value ? '1' : '0')
}

function onTimeDensityChange (): void {
  localStorage.setItem('schedule-time-density-minutes', String(timeDensityMinutes.value))
}


const translations = computed(() => ({
  searchSessions: caps.showRoles ? $t('Search shifts') : $t('Search sessions'),
  unassignedTitle: caps.showRoles ? $t('Unassigned Shifts') : $t('Unassigned Sessions'),
  unassignDropTitle: caps.showRoles ? $t('Drop here to unassign shift') : $t('Drop here to unassign session'),
  unassignDropSubtitle: caps.showRoles ? $t('Returns shift to unassigned list') : $t('Returns session to unscheduled list'),
  newBreak: $t('New break'),
}))

const assignMembersHeading = computed(() => {
  if (!assigningSession.value) return $t('Assign Members')
  return $t('Assign Members for {{title}}', {title: getLocalizedString(assigningSession.value.title)})
})

function lookupKey(value?: string | number | null | { id?: string | number }): string {
  if (value && typeof value === 'object' && 'id' in value) {
    return value.id == null ? '' : String(value.id)
  }
  return value == null ? '' : String(value)
}

const roomsLookup = computed<Record<string, Room>>(() => {
  if (!schedule.value) return {}
  return schedule.value.rooms.reduce((acc, room) => {
    acc[lookupKey(room.id)] = room
    return acc
  }, {} as Record<string, Room>)
})

const tracksLookup = computed<Record<string, Track>>(() => {
  if (!schedule.value) return {}
  return schedule.value.tracks.reduce((acc, track) => {
    acc[lookupKey(track.id)] = track
    return acc
  }, {} as Record<string, Track>)
})

const speakersLookup = computed<Record<string, Speaker>>(() => {
  if (!schedule.value) return {}
  return schedule.value.speakers.reduce((acc, speaker) => {
    if (speaker.code) {
      acc[speaker.code] = speaker
    }
    return acc
  }, {} as Record<string, Speaker>)
})

function resolveSessionSpeakers(speakers?: string[]): Speaker[] {
  if (!speakers?.length) return []
  return speakers
    .map((speakerCode) => speakersLookup.value[speakerCode])
    .filter((speaker): speaker is Speaker => Boolean(speaker))
}

const unassignedSortMethods = computed<SortMethod[]>(() => {
  const sortMethods: SortMethod[] = [
    { label: $t('Title'), name: 'title' },
  ]
  if (caps.showSpeakers) {
    sortMethods.push({ label: $t('Speakers'), name: 'speakers' })
  }
  if (schedule.value && schedule.value.tracks.length > 1 && caps.showTracks) {
    sortMethods.push({ label: $t('Track'), name: 'track' })
  }
  sortMethods.push({ label: $t('Duration'), name: 'duration' })
  return sortMethods
})

const unscheduled = computed<SessionData[]>(() => {
  if (!schedule.value) return []
  let sessions: SessionData[] = []
  const isShifts = mode === 'shifts' || mode === 'public-shifts'
  for (const session of schedule.value.talks.filter((s) => isShifts ? !s.room : !s.start)) {
    sessions.push({
      id: session.id,
      code: session.code,
      title: session.title,
      abstract: session.abstract,
      speakers: resolveSessionSpeakers(session.speakers),
      track: tracksLookup.value[lookupKey(session.track)],
      duration: session.duration,
      state: session.state,
      session_type: session.session_type || session.submission_type,
      submission_type: session.submission_type || session.session_type,
      do_not_record: session.do_not_record,
      roles: session.roles ?? [],
    } as SessionData)
  }
  if (unassignedFilterString.value.length) {
    sessions = sessions.filter((s) => {
      const title = typeof s.title === 'string' ? s.title : getLocalizedString(s.title)
      const speakers = s.speakers?.map((sp) => sp.name).join(', ') || ''
      const filterLower = unassignedFilterString.value.toLowerCase()
      return title.toLowerCase().includes(filterLower) || speakers.toLowerCase().includes(filterLower)
    })
  }
  sessions = sessions.sort((a, b) => {
    if (unassignedSort.value == 'title') {
      return (
        getLocalizedString(typeof a.title === 'string' ? { en: a.title } : a.title)
          .toUpperCase()
          .localeCompare(
            getLocalizedString(typeof b.title === 'string' ? { en: b.title } : b.title).toUpperCase(),
          ) * unassignedSortDirection.value
      )
    } else if (unassignedSort.value == 'speakers') {
      const aSpeakers = a.speakers?.map((s) => s.name).join(', ') || ''
      const bSpeakers = b.speakers?.map((s) => s.name).join(', ') || ''
      return aSpeakers.toUpperCase().localeCompare(bSpeakers.toUpperCase()) * unassignedSortDirection.value
    } else if (unassignedSort.value == 'track') {
      const aTrack = a.track ? getLocalizedString(a.track.name) : ''
      const bTrack = b.track ? getLocalizedString(b.track.name) : ''
      return aTrack.toUpperCase().localeCompare(bTrack.toUpperCase()) * unassignedSortDirection.value
    } else if (unassignedSort.value == 'duration') {
      return ((a.duration ?? 0) - (b.duration ?? 0)) * unassignedSortDirection.value
    }
    return 0
  })
  return sessions
})

const deletedRoomSessions = computed<SessionData[]>(() => {
  const tz = currentTimezone.value
  if (!schedule.value) return []
  const isShifts = mode === 'shifts' || mode === 'public-shifts'
  return schedule.value.talks
    .filter(
      (session) =>
        session.code &&
        session.start &&
        (isShifts
          ? (session.room && !roomsLookup.value[lookupKey(session.room)])
          : (!session.room || !roomsLookup.value[lookupKey(session.room)])),
    )
    .map((session) => ({
      id: session.id,
      code: session.code,
      title: session.title,
      abstract: session.abstract,
      start: tz ? moment.tz(session.start, tz) : moment(session.start),
      end: tz ? moment.tz(session.end, tz) : moment(session.end),
      duration: session.end ? moment(session.end).diff(moment(session.start), 'minutes') : session.duration,
      speakers: isShifts ? [] : resolveSessionSpeakers(session.speakers),
      track: isShifts ? undefined : tracksLookup.value[lookupKey(session.track)],
      session_type: session.session_type || session.submission_type,
      submission_type: session.submission_type || session.session_type,
      state: session.state,
      deletedRoom: true,
      do_not_record: session.do_not_record,
      roles: isShifts ? (session.roles ?? []) : undefined,
    }))
})

const sessions = computed<SessionData[]>(() => {
  const tz = currentTimezone.value
  if (!schedule.value) return []
  const dayStart = days.value[0]
  const dayEnd = days.value.at(-1)?.clone().endOf('day')
  if (!dayStart || !dayEnd) return []

  const filteredSessions = schedule.value.talks.filter(
    (s) =>
      s.start &&
      s.room &&
      roomsLookup.value[lookupKey(s.room)] &&
      (tz ? moment.tz(s.start, tz) : moment(s.start)).isSameOrAfter(dayStart) &&
      (tz ? moment.tz(s.start, tz) : moment(s.start)).isSameOrBefore(dayEnd),
  )

  const sessionList: SessionData[] = filteredSessions.map((session) => ({
    id: session.id,
    code: session.code,
    title: session.title,
    abstract: session.abstract,
    start: tz ? moment.tz(session.start, tz) : moment(session.start),
    end: tz ? moment.tz(session.end, tz) : moment(session.end),
    duration: moment(session.end).diff(moment(session.start), 'minutes'),
    speakers: resolveSessionSpeakers(session.speakers),
    track: tracksLookup.value[lookupKey(session.track)],
    session_type: session.session_type || session.submission_type,
    submission_type: session.submission_type || session.session_type,
    state: session.state,
    room: roomsLookup.value[lookupKey(session.room)],
    do_not_record: session.do_not_record,
    roles: session.roles || [],
  }))

  sessionList.sort((a, b) => a.start!.diff(b.start!))
  return sessionList
})

const days = computed<Moment[]>(() => {
  const tz = currentTimezone.value
  if (!schedule.value) return []
  let firstDay = (tz ? moment.tz(schedule.value.event_start, tz) : moment(schedule.value.event_start)).startOf('day')
  let lastDay = (tz ? moment.tz(schedule.value.event_end, tz) : moment(schedule.value.event_end)).startOf('day')

  const startedTalks = schedule.value.talks
    .map((talk) => talk.start)
    .filter((start): start is string => typeof start === 'string')
    .map((start) => (tz ? moment.tz(start, tz) : moment(start)))
    .filter((start) => start.isValid())

  const endedTalks = schedule.value.talks
    .map((talk) => talk.end)
    .filter((end): end is string => typeof end === 'string')
    .map((end) => (tz ? moment.tz(end, tz) : moment(end)))
    .filter((end) => end.isValid())

  const talkDates = [...startedTalks, ...endedTalks]

  if (talkDates.length) {
    let earliestTalkDay = talkDates[0].clone().startOf('day')
    let latestTalkDay = talkDates[0].clone().startOf('day')

    for (const talkDay of talkDates.slice(1)) {
      const normalizedTalkDay = talkDay.clone().startOf('day')
      if (normalizedTalkDay.isBefore(earliestTalkDay)) {
        earliestTalkDay = normalizedTalkDay
      }
      if (normalizedTalkDay.isAfter(latestTalkDay)) {
        latestTalkDay = normalizedTalkDay
      }
    }

    if (earliestTalkDay.isBefore(firstDay)) {
      firstDay = earliestTalkDay
    }
    if (latestTalkDay.isAfter(lastDay)) {
      lastDay = latestTalkDay
    }
  }

  const daysArray: Moment[] = [firstDay]
  while (!daysArray.at(-1)!.isSame(lastDay, 'day')) {
    daysArray.push(daysArray.at(-1)!.clone().add(1, 'days'))
  }
  return daysArray
})

const dateFormat = computed<string>(() => {
  return 'ddd D MMM'
})

async function fetchSchedule(options?: { since?: string; warnings?: boolean }): Promise<Schedule> {
  const sched = await api.fetchTalks(options) as unknown as Schedule
  return sched
}

function writeWarning(code: string, list: Warning[] | undefined): void {
  if (list?.length) warnings[code] = list
  else delete warnings[code]
}

function replaceWarnings(next: Record<string, Warning[]> | undefined | null): void {
  if (!next) return
  for (const code of Object.keys(warnings)) {
    if (!next[code]?.length) delete warnings[code]
  }
  for (const [code, list] of Object.entries(next)) writeWarning(code, list)
}

async function fetchAdditionalScheduleData(): Promise<void> {
  Object.assign(availabilities, await api.fetchAvailabilities() as unknown)
  replaceWarnings(await api.fetchWarnings() as Record<string, Warning[]> | undefined)
}

function changeDay(day: Moment): void {
  const targetDay = day.clone().tz(eventTimezone.value ?? 'UTC').startOf('day')
  if (currentDay.value && targetDay.isSame(currentDay.value, 'day')) return
  currentDay.value = targetDay
  window.location.hash = day.format('YYYY-MM-DD')
}

watch(currentDay, (newDay) => {
  if (!newDay) return
  nextTick(() => {
    const tabEl = document.getElementById(`day-tab-${newDay.format('YYYY-MM-DD')}`)
    tabEl?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' })
  })
})

async function saveTalk(session: Talk): Promise<void> {
  const response: any = await api.saveTalk(session as any)
  if (response && schedule.value) {
    if (session.code && Array.isArray(response.warnings)) {
      writeWarning(session.code, response.warnings)
    }
    const talk = schedule.value.talks.find((s) => String(s.id) === String(session.id))
    if (talk) {
      Object.assign(talk, {
        start: response.start,
        end: response.end,
        room: response.room,
        updated: response.updated,
      })
      schedule.value.talks = [...schedule.value.talks]
    }
  }
}

interface RescheduleEvent {
  session: SessionData
  start: string | Moment
  end: string | Moment
  room: Room
}

async function rescheduleSession(e: RescheduleEvent): Promise<void> {
  if (!schedule.value) return
  const movedSession = schedule.value.talks.find((s) => String(s.id) === String(e.session.id) || (Number(s.id) && Number(s.id) === Number(e.session.id)))
  stopDragging()
  if (!movedSession) return
  movedSession.start = e.start as string
  movedSession.end = e.end as string
  movedSession.room = e.room.id
  await saveTalk(movedSession)
  if (movedSession.code) {
    api.fetchWarnings()
      .then((w) => replaceWarnings(w))
      .catch((error) => {
        console.error('Failed to refresh schedule warnings after reschedule', { sessionId: movedSession.id, error })
      })
  }
}

interface CreateSessionEvent {
  session: Talk
}

async function createSession(e: CreateSessionEvent): Promise<void> {
  stopDragging()
  const roomId = typeof e.session.room === 'object' && e.session.room !== null ? (e.session.room as any).id : e.session.room
  const startStr = typeof e.session.start === 'object' && e.session.start !== null && 'format' in e.session.start
    ? (e.session.start as any).format()
    : String(e.session.start)
  const endStr = typeof e.session.end === 'object' && e.session.end !== null && 'format' in e.session.end
    ? (e.session.end as any).format()
    : String(e.session.end)

  const tempId = `temp-${Date.now()}`
  pendingBreakCreations.set(tempId, { dismissed: false })
  const optimisticSession: any = {
    ...e.session,
    id: tempId,
    room: roomId,
    start: startStr,
    end: endStr,
  }
  delete optimisticSession.uncreated

  if (schedule.value) {
    schedule.value.talks = [...schedule.value.talks, optimisticSession]
  }

  try {
    const response: any = await api.createTalk(e.session as any)
    const pending = pendingBreakCreations.get(tempId)
    pendingBreakCreations.delete(tempId)

    if (pending?.dismissed) {
      if (schedule.value) {
        schedule.value.talks = schedule.value.talks.filter((s) => String(s.id) !== tempId && String(s.id) !== String(response.id))
      }
      const realId = Number(response.id)
      if (realId && !isNaN(realId)) {
        pendingBreakDeletions.add(String(realId))
        try {
          await api.deleteTalk({ id: realId })
          deletedBreakIds.add(String(realId))
          if (schedule.value) {
            schedule.value.talks = schedule.value.talks.filter((s) => String(s.id) !== String(realId))
          }
        } catch (err) {
          console.error('Failed to delete cancelled break', err)
          const restoredSession = {
            ...optimisticSession,
            ...response,
            id: response.id,
            room: response.room ?? roomId,
            start: response.start ?? startStr,
            end: response.end ?? endStr,
          }
          if (schedule.value) {
            schedule.value.talks = [...schedule.value.talks, restoredSession]
          }
          showScheduleActionError($t('Failed to delete break. Please try again.'))
        } finally {
          pendingBreakDeletions.delete(String(realId))
        }
      }
      return
    }

    if (e.session.code && Array.isArray(response.warnings)) {
      writeWarning(e.session.code, response.warnings)
    }
    const realSession = {
      ...optimisticSession,
      ...response,
      id: response.id,
      room: response.room ?? roomId,
      start: response.start ?? startStr,
      end: response.end ?? endStr,
    }
    delete realSession.uncreated
    if (schedule.value) {
      const idx = schedule.value.talks.findIndex((s) => String(s.id) === tempId)
      if (idx !== -1) {
        schedule.value.talks[idx] = realSession
        schedule.value.talks = [...schedule.value.talks]
      }
    }
    if (e.session.code) {
      fetchAdditionalScheduleData().catch((error) => {
        console.error('Failed to refresh additional schedule data after create', error)
      })
    }
  } catch (error) {
    pendingBreakCreations.delete(tempId)
    if (schedule.value) {
      schedule.value.talks = schedule.value.talks.filter((s) => String(s.id) !== tempId)
    }
    console.error('Failed to create session', error)
  }
}

function editorStart(session: SessionData | Talk): void {
  editorSessionError.value = ''
  const newEditorSession = { ...session } as SessionData
  if (newEditorSession.title && typeof newEditorSession.title === 'object') {
    newEditorSession.title = { ...newEditorSession.title }
  }
  if (caps.canEditRoles) {
    if (!newEditorSession.roles || newEditorSession.roles.length === 0) {
      newEditorSession.roles = [{ id: undefined, capacity: 1 }]
    } else {
      newEditorSession.roles = newEditorSession.roles.map((r) => ({ ...r }))
    }
  }
  editorSession.value = newEditorSession
  void nextTick(() => {
    const form = document.getElementById('session-editor') as HTMLFormElement | null
    if (form) {
      const input = form.querySelector<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>(
        'input:not([type="submit"]):not([type="hidden"]), select, textarea'
      )
      if (input) {
        input.focus()
        if (input instanceof HTMLInputElement && input.type === 'text') {
          input.select?.()
        }
      }
    }
  })
}

function editorSubmit(event: KeyboardEvent): void {
  if (event.isComposing || event.keyCode === 229) return

  const target = event.target as HTMLElement | null
  if (
    target instanceof HTMLButtonElement ||
    target?.closest('button') ||
    target instanceof HTMLTextAreaElement
  ) return

  const form = target?.closest('form') ?? (document.getElementById('session-editor') as HTMLFormElement | null)
  if (form && !form.checkValidity()) {
    form.reportValidity()
    return
  }
  event.preventDefault()
  event.stopPropagation()
  void editorSave()
}

async function editorSave(): Promise<void> {
  if (!editorSession.value || editorSessionWaiting.value) return

  editorSessionWaiting.value = true
  if (editorSession.value.start) {
    const startMoment = moment(editorSession.value.start)
    editorSession.value.end = startMoment.clone().add(editorSession.value.duration ?? 0, 'minutes')
  }
  
  const talk: Talk = {
    id: editorSession.value.id,
    code: editorSession.value.code,
    title: typeof editorSession.value.title === 'string' 
      ? { en: editorSession.value.title } 
      : editorSession.value.title,
    duration: editorSession.value.duration ?? 0,
    start: typeof editorSession.value.start === 'string' ? editorSession.value.start : editorSession.value.start?.toISOString(),
    end: typeof editorSession.value.end === 'string' ? editorSession.value.end : editorSession.value.end?.toISOString(),
    room: typeof editorSession.value.room === 'object' && editorSession.value.room !== null ? (editorSession.value.room as any).id : editorSession.value.room,
    speakers: editorSession.value.speakers?.map(s => 
      typeof s === 'string' ? s : s.name
    ) || [],
    track: editorSession.value.track?.id,
    abstract: editorSession.value.abstract,
    state: editorSession.value.state
  }

  if (caps.canEditRoles) {
    talk.roles = editorSession.value.roles?.filter((r) => r.id !== undefined)
  }

  try {
    await saveTalk(talk)

    const sessionInSchedule = schedule.value?.talks.find((s) => s.id === editorSession.value?.id)
    if (sessionInSchedule && editorSession.value) {
      sessionInSchedule.end = typeof editorSession.value.end === 'string' ? editorSession.value.end : editorSession.value.end?.toISOString()
      if (!('submission' in sessionInSchedule)) {
        sessionInSchedule.title = editorSession.value.title as Record<string, string>
      }
    }
    editorSession.value = null

    try {
      if (caps.showRoles) {
        schedule.value = await fetchSchedule()
      }
      await fetchAdditionalScheduleData()
    } catch {
      // fetchSchedule already records schedule.fetch via api.http
    }
  } catch {
    editorSessionError.value = $t('Failed to save. Please try again.')
  } finally {
    editorSessionWaiting.value = false
  }
}

function editorCancel(): void {
  editorSession.value = null
  editorSessionError.value = ''
}

async function editorDelete(): Promise<void> {
  if (!editorSession.value) return
  let deleted: boolean
  if (mode === 'shifts' || mode === 'public-shifts') {
    deleted = await deleteShiftById(editorSession.value.id)
  } else {
    if (editorSession.value.code) return
    deleted = await deleteTalkBreakById(editorSession.value.id)
  }
  if (deleted) {
    editorSession.value = null
  }
}

async function deleteSessionDirect(session: SessionData | Talk): Promise<void> {
  if (mode === 'shifts' || mode === 'public-shifts') {
    await deleteShiftById(session.id)
  } else {
    if (session.code) return
    await deleteTalkBreakById(session.id)
  }
}

async function deleteShiftById(id: number): Promise<boolean> {
  return showConfirmDialog({
    title: $t('Delete shift'),
    lead: $t('Are you sure you want to delete this shift? This action cannot be undone.'),
    confirmLabel: $t('Delete'),
    confirmClass: 'btn-danger',
    onConfirm: async () => {
      await api.deleteTalk({ id })
      if (schedule.value) {
        schedule.value.talks = schedule.value.talks.filter((s) => s.id !== id)
      }
      await fetchAdditionalScheduleData()
    },
  })
}

async function deleteTalkBreakById(id: number | string): Promise<boolean> {
  return showBreakConfirmDialog(id)
}

async function openAssignModal(session: SessionData | Talk): Promise<void> {
  assignModalError.value = ''
  assigningSession.value = { ...session } as SessionData
  if (assigningSession.value.roles && assigningSession.value.roles.length > 0) {
    for (const role of assigningSession.value.roles) {
      selectedMemberIds.value[String(role.id)] = undefined
    }
    await Promise.all(assigningSession.value.roles.map((role) => loadMembers(role.id)))
  }
}

function closeAssignModal(): void {
  assigningSession.value = null
  assignModalError.value = ''
  selectedMemberIds.value = {}
  availableMembersByRole.value = {}
}

async function loadMembers(roleId: number): Promise<void> {
  try {
    const response = await api.fetchMembers(roleId)
    availableMembersByRole.value[String(roleId)] = response.members ?? []
  } catch {
    assignModalError.value = $t('Failed to load members. Please try again.')
  }
}

async function assignMember(roleId: number): Promise<void> {
  const selectedMemberId = selectedMemberIds.value[String(roleId)]
  if (!assigningSession.value || !selectedMemberId) return
  
  assigningWaiting.value = true
  try {
    await api.assignMember(Number(assigningSession.value.id), roleId, selectedMemberId)
    
    const sched = await fetchSchedule({ warnings: true })
    if (schedule.value) {
      schedule.value.talks = sched.talks
      if (sched.roles) schedule.value.roles = sched.roles
      const updatedSession = sched.talks.find(t => t.id === assigningSession.value?.id)
      if (updatedSession) {
        assigningSession.value = { ...updatedSession } as SessionData
      }
    }
    await fetchAdditionalScheduleData()
    await loadMembers(roleId)
    selectedMemberIds.value[String(roleId)] = undefined
  } catch (error) {
    if (error instanceof Error && error.message) {
      try {
        const parsedError = JSON.parse(
          error.message.replace(/^HTTP error \d+: /, '')
        )
        assignModalError.value =
          typeof parsedError.detail === 'string'
            ? parsedError.detail
            : $t('Failed to assign member. Please try again.')
      } catch {
        assignModalError.value = $t('Failed to assign member. Please try again.')
      }
    } else {
      assignModalError.value = $t('Failed to assign member. Please try again.')
    }
  } finally {
    assigningWaiting.value = false
  }
}

async function unassignMember(roleId: number, userId: number): Promise<void> {
  if (!assigningSession.value) return
  const confirmed = await showConfirmDialog({
    title: $t('Unassign member'),
    lead: $t('Are you sure you want to unassign this member?'),
    confirmLabel: $t('Unassign'),
    confirmClass: 'btn-danger',
  })
  if (!confirmed) return
  
  assigningWaiting.value = true
  try {
    await api.unassignMember(Number(assigningSession.value.id), roleId, userId)
    
    const sched = await fetchSchedule({ warnings: true })
    if (schedule.value) {
      schedule.value.talks = sched.talks
      if (sched.roles) schedule.value.roles = sched.roles
      const updatedSession = sched.talks.find(t => t.id === assigningSession.value?.id)
      if (updatedSession) {
        assigningSession.value = { ...updatedSession } as SessionData
      }
    }
    await fetchAdditionalScheduleData()
  } catch (error) {
    if (error instanceof Error) {
      try {
        const parsedError = JSON.parse(
          error.message.replace(/^HTTP error \d+: /, '')
        )
        assignModalError.value =
          typeof parsedError.detail === 'string'
            ? parsedError.detail
            : $t('Failed to unassign member. Please try again.')
      } catch {
        assignModalError.value = $t('Failed to unassign member. Please try again.')
      }
    } else {
      assignModalError.value = $t('Failed to unassign member. Please try again.')
    }
  } finally {
    assigningWaiting.value = false
  }
}

function showNewBreakHint() {
  newBreakTooltip.value = $t('Drag the box to the schedule to create a new break')
}

function removeNewBreakHint() {
  newBreakTooltip.value = ''
}

function onNewBreakKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    removeNewBreakHint()
  }
}

function onUnassignedEnter() {
  if (isUnassignedListClosed()) return
  isUnassigning.value = true
}

function isScheduledTalkDrag(): boolean {
  const session = draggedSession.value
  if (!session || mode !== 'talks') return false
  return Boolean(session.code && session.start && !session.deletedRoom)
}

function showUnscheduleHint() {
  unscheduleHint.value = $t('Click the cross on the session to remove it from the schedule')
  isUnassignedCollapsed.value = false
  if (unscheduleHintTimer) clearTimeout(unscheduleHintTimer)
  unscheduleHintTimer = setTimeout(() => {
    unscheduleHint.value = ''
    unscheduleHintTimer = null
  }, 5000)
}

function onUnassignedLeave() {
  isUnassigning.value = false
  removeNewBreakHint()
}

interface DragStartEvent {
  event: PointerEvent
  session: Partial<SessionData & Talk>
}

function startNewBreak({ event }: DragStartEvent) {
  const title = locales.value.reduce((obj: Record<string, string>, locale) => {
    obj[locale] = $t('New break')
    return obj
  }, {})
  startDragging({ event, session: { title, duration: 5, uncreated: true } })
}

function startDragging({ event, session }: DragStartEvent) {
  isUnassigning.value = false
  if (availabilities && availabilities.talks[session.id! ?? 0] && availabilities.talks[session.id! ?? 0].length !== 0) {
    session.availabilities = availabilities.talks[session.id! ?? 0]
  }
  draggedSession.value = session as SessionData
  dragOriginX = event.clientX
  dragOriginY = event.clientY
  dragPointerX = event.clientX
  dragPointerY = event.clientY
  isPointerDragging.value = false

  const targetEl = (event.target as HTMLElement)?.closest('.c-linear-schedule-session') as HTMLElement | null
  if (targetEl) {
    const rect = targetEl.getBoundingClientRect()
    dragOffsetX = Math.max(10, Math.min(rect.width - 10, event.clientX - rect.left))
    dragOffsetY = Math.max(10, Math.min(rect.height - 10, event.clientY - rect.top))
    dragAvatarWidth = Math.max(220, Math.min(320, rect.width))
  } else {
    dragOffsetX = 50
    dragOffsetY = 30
    dragAvatarWidth = 260
  }
}

async function unscheduleSession(session: { id: number | string; code?: string | null }): Promise<void> {
  if (!schedule.value || !session.code || mode !== 'talks') return
  const movedSession = schedule.value.talks.find((s) => Number(s.id) === Number(session.id))
  if (!movedSession?.code || !movedSession.start) return
  const previous = {
    start: movedSession.start,
    end: movedSession.end,
    room: movedSession.room,
  }
  movedSession.start = null
  movedSession.end = null
  movedSession.room = undefined
  try {
    await saveTalk(movedSession)
  } catch (error) {
    movedSession.start = previous.start
    movedSession.end = previous.end
    movedSession.room = previous.room
    console.error('Failed to remove session from schedule', { sessionId: movedSession.id, error })
    return
  }
  api.fetchWarnings()
    .then((w) => replaceWarnings(w))
    .catch((error) => {
      console.error('Failed to refresh schedule warnings after removing session', { sessionId: movedSession.id, error })
    })
}

async function stopDragging(event?: PointerEvent): Promise<void> {
  const session = draggedSession.value
  const wasOverLeft = !isUnassignedListClosed() && (isUnassigning.value || Boolean(event && checkIsOverUnassigned(event.clientX, event.clientY)))

  try {
    if (wasOverLeft && session) {
      if (session.code && !session.deletedRoom) {
        const movedSession = schedule.value?.talks.find((s) => Number(s.id) === Number(session.id))
        if (movedSession && (mode === 'shifts' || mode === 'public-shifts')) {
          if (movedSession.room == null) return
          movedSession.room = undefined
          await saveTalk(movedSession)
          api.fetchWarnings()
            .then((w) => replaceWarnings(w))
            .catch((error) => {
              console.error('Failed to refresh schedule warnings after update', { sessionId: movedSession.id, error })
            })
        } else if (session.start) {
          await unscheduleSession(session)
        }
      } else if (session.deletedRoom) {
        const movedSession = schedule.value?.talks.find((s) => Number(s.id) === Number(session.id))
        if (movedSession) {
          if ((mode === 'shifts' || mode === 'public-shifts') && movedSession.room == null) return
          movedSession.room = undefined
          await saveTalk(movedSession)
          api.fetchWarnings()
            .then((w) => replaceWarnings(w))
            .catch((error) => {
              console.error('Failed to refresh schedule warnings after update', { sessionId: movedSession.id, error })
            })
        }
      } else {
        const breakId = session.id
        const strId = String(breakId)
        if (pendingBreakCreations.has(strId)) {
          pendingBreakCreations.get(strId)!.dismissed = true
        }
        const existingBreak = schedule.value?.talks.find((s) => String(s.id) === strId || (Number(s.id) && Number(s.id) === Number(breakId)))
        if (existingBreak) {
          const numericId = Number(existingBreak.id)
          const removedBreak = existingBreak
          if (schedule.value) {
            schedule.value.talks = schedule.value.talks.filter((s) => String(s.id) !== strId && (isNaN(numericId) || Number(s.id) !== numericId))
          }
          pendingBreakDeletions.add(strId)
          if (!isNaN(numericId)) {
            pendingBreakDeletions.add(String(numericId))
          }
          if (numericId && !isNaN(numericId)) {
            api.deleteTalk({ id: numericId })
              .then(() => {
                deletedBreakIds.add(strId)
                if (!isNaN(numericId)) {
                  deletedBreakIds.add(String(numericId))
                }
                if (schedule.value) {
                  schedule.value.talks = schedule.value.talks.filter((s) => String(s.id) !== strId && Number(s.id) !== numericId)
                }
              })
              .catch((error) => {
                console.error('Failed to delete break on unassign', { breakId, error })
                if (schedule.value) {
                  const currentIds = new Set(schedule.value.talks.map((s) => String(s.id)))
                  if (!currentIds.has(String(removedBreak.id))) {
                    schedule.value.talks = [...schedule.value.talks, removedBreak]
                  }
                }
                showScheduleActionError($t('Failed to delete break. Please try again.'))
              })
              .finally(() => {
                pendingBreakDeletions.delete(strId)
                if (!isNaN(numericId)) {
                  pendingBreakDeletions.delete(String(numericId))
                }
              })
          } else {
            pendingBreakDeletions.delete(strId)
          }
        }
      }
    }
  } finally {
    resetDragAvatar()
    draggedSession.value = null
    isPointerDragging.value = false
    isUnassigning.value = false
    cachedUnassignedRect = null
  }
}

function onWindowResize() {
  scrollParentWidth.value = document.body.offsetWidth
  isMobile.value = typeof window !== 'undefined' ? window.innerWidth < 768 : false
}

let pollTimeoutId: ReturnType<typeof setTimeout> | null = null
let isPolling = false
let isUnmounted = false

function triggerImmediatePoll() {
  if (pollTimeoutId) {
    clearTimeout(pollTimeoutId)
    pollTimeoutId = null
  }
  if (!draggedSession.value && !isUnmounted) {
    pollUpdates()
  }
}

const onFocus = () => triggerImmediatePoll()
const onVisibilityChange = () => {
  if (!document.hidden) triggerImmediatePoll()
}

async function pollUpdates() {
  if (pollTimeoutId) {
    clearTimeout(pollTimeoutId)
    pollTimeoutId = null
  }
  if (isUnmounted || !schedule.value || draggedSession.value || isPolling) {
    if (!isUnmounted) {
      pollTimeoutId = window.setTimeout(pollUpdates, 5000)
    }
    return
  }
  isPolling = true
  try {
    const sched = await fetchSchedule({ since: since.value, warnings: true })
    if (isUnmounted) return
    if (sched.version !== schedule.value.version) {
      window.location.reload()
      return
    }
    const updatedTalks = [...schedule.value.talks]
    let hasUpdates = false
    sched.talks.forEach((talk) => {
      const talkIdStr = String(talk.id)
      if (pendingBreakDeletions.has(talkIdStr) || deletedBreakIds.has(talkIdStr)) {
        return
      }
      const oldTalk = updatedTalks.find((t) => String(t.id) === talkIdStr)
      if (!oldTalk) {
        updatedTalks.push(talk)
        hasUpdates = true
      } else if (!oldTalk.updated || moment(talk.updated).isAfter(moment(oldTalk.updated))) {
        Object.assign(oldTalk, talk)
        hasUpdates = true
      }
    })
    if (hasUpdates) {
      schedule.value.talks = updatedTalks
      api.fetchWarnings()
        .then((w) => replaceWarnings(w))
        .catch((error) => {
          console.error('Failed to refresh schedule warnings after poll', error)
        })
    }
    since.value = sched.now || schedule.value.now
  } catch (error) {
    if (!isUnmounted) {
      console.error('Failed to poll schedule updates', error)
    }
  } finally {
    isPolling = false
    if (!isUnmounted) {
      pollTimeoutId = window.setTimeout(pollUpdates, document.hidden ? 30000 : 5000)
    }
  }
}

onBeforeMount(async () => {
  schedule.value = await fetchSchedule()
  since.value = schedule.value.now
  const match = window.location.pathname.match(/\/orga\/event\/([^/]+)\/([^/]+)/);
  organizerSlug.value = match ? match[1] : null;
  eventSlug.value = match ? match[2] : null;
  eventTimezone.value = schedule.value.timezone

  let savedTz: string | null = null
  try {
    savedTz = localStorage.getItem(`schedule_editor_${eventSlug.value || 'default'}_timezone`)
  } catch (e) {}

  currentTimezone.value = savedTz || schedule.value.timezone || 'UTC'
  moment.tz.setDefault(currentTimezone.value)
  locales.value = schedule.value.locales
  currentDay.value = days.value[0]
  pollTimeoutId = window.setTimeout(pollUpdates, 5000)
  await fetchAdditionalScheduleData()
  await new Promise<void>((resolve) => {
    const poll = () => {
      const el = document.querySelector('.pretalx-schedule')
      // @ts-ignore
      if (el && (el.parentElement || el.getRootNode().host)) return resolve()
      setTimeout(poll, 100)
    }
    poll()
  })
})

const onStorageChange = (e: StorageEvent) => {
  if (e.key === 'schedule-time-density-minutes' && e.newValue) {
    timeDensityMinutes.value = Number(e.newValue)
  }
  if (e.key === 'schedule-editor-condensed') {
    condensedView.value = e.newValue === '1'
  }
}

const onWindowClick = (e: MouseEvent) => {
  if (showTimeDensityMenu.value && customDropdownRef.value && !customDropdownRef.value.contains(e.target as Node)) {
    showTimeDensityMenu.value = false
  }
  if (showTimezoneMenu.value && timezoneDropdownRef.value && !timezoneDropdownRef.value.contains(e.target as Node)) {
    showTimezoneMenu.value = false
  }
  const sortMenu = document.getElementById('unassigned-sort-menu')
  const sortBtn = document.getElementById('unassigned-sort')
  if (sortMenu && sortBtn && !sortMenu.contains(e.target as Node) && !sortBtn.contains(e.target as Node)) {
    showUnassignedSortMenu.value = false
  }
}

const preventScrollOnDrag = (e: TouchEvent) => {
  if (draggedSession.value) {
    e.preventDefault()
  }
}

function onWindowKeydown(event: KeyboardEvent): void {
  if (!editorSession.value) return
  if (event.key === 'Escape') {
    editorCancel()
    return
  }
  if (event.key === 'Enter') {
    editorSubmit(event)
  }
}

const isRtl = computed(() => {
  if (typeof document === 'undefined') return false
  return document.documentElement.dir === 'rtl' || document.documentElement.classList.contains('rtl')
})

const isMobile = ref<boolean>(typeof window !== 'undefined' ? window.innerWidth < 768 : false)
const actionsWidth = ref<number>(0)
let actionsObserver: ResizeObserver | null = null

const actionsControlsStyle = computed(() => {
  if (isMobile.value || isFullscreen.value) return { paddingRight: '0px', paddingLeft: '0px' }
  if (!actionsWidth.value) return undefined
  if (isRtl.value) {
    return { paddingLeft: `${actionsWidth.value + 16}px`, paddingRight: '0px' }
  }
  return { paddingRight: `${actionsWidth.value + 16}px`, paddingLeft: '0px' }
})

function updateActionsWidth(): void {
  const actionsEl = document.getElementById('schedule-action-wrapper')
  if (actionsEl) {
    const width = Math.ceil(actionsEl.getBoundingClientRect().width)
    if (width > 0) {
      actionsWidth.value = width
    }
  }
}

onMounted(() => {
  isMounted.value = true
  updateActionsWidth()
  const unassignedEl = document.getElementById('unassigned')
  if (unassignedEl && typeof ResizeObserver !== 'undefined') {
    unassignedResizeObserver = new ResizeObserver(() => {
      cachedUnassignedRect = null
    })
    unassignedResizeObserver.observe(unassignedEl)
  }
  const actionsEl = document.getElementById('schedule-action-wrapper')
  if (actionsEl && typeof ResizeObserver !== 'undefined') {
    actionsObserver = new ResizeObserver(updateActionsWidth)
    actionsObserver.observe(actionsEl)
  }
  if (document.fonts?.ready) {
    document.fonts.ready.then(updateActionsWidth)
  }
  document.addEventListener('touchmove', preventScrollOnDrag, { passive: false })
  document.addEventListener('fullscreenchange', onFullscreenChange)
  document.addEventListener('webkitfullscreenchange', onFullscreenChange)
  window.addEventListener('focus', onFocus)
  document.addEventListener('visibilitychange', onVisibilityChange)
  window.addEventListener('pointermove', onGlobalPointerMove, { passive: true })
  window.addEventListener('pointerup', onGlobalPointerUp)
  window.addEventListener('click', onWindowClick)
  window.addEventListener('resize', onWindowResize)
  window.addEventListener('storage', onStorageChange)
  window.addEventListener('keydown', onWindowKeydown)
  window.addEventListener('keydown', onEscapeKeydown)
  onWindowResize()
})

onUnmounted(() => {
  isUnmounted = true
  resetDragAvatar()
  if (unassignedResizeObserver) {
    unassignedResizeObserver.disconnect()
    unassignedResizeObserver = null
  }
  if (actionsObserver) {
    actionsObserver.disconnect()
    actionsObserver = null
  }
  if (pollTimeoutId) {
    clearTimeout(pollTimeoutId)
    pollTimeoutId = null
  }
  if (unscheduleHintTimer) clearTimeout(unscheduleHintTimer)
  if (scheduleActionErrorTimer) clearTimeout(scheduleActionErrorTimer)
  document.removeEventListener('touchmove', preventScrollOnDrag)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  document.removeEventListener('webkitfullscreenchange', onFullscreenChange)
  window.removeEventListener('focus', onFocus)
  document.removeEventListener('visibilitychange', onVisibilityChange)
  window.removeEventListener('pointermove', onGlobalPointerMove)
  window.removeEventListener('pointerup', onGlobalPointerUp)
  window.removeEventListener('click', onWindowClick)
  window.removeEventListener('resize', onWindowResize)
  window.removeEventListener('storage', onStorageChange)
  window.removeEventListener('keydown', onWindowKeydown)
  window.removeEventListener('keydown', onEscapeKeydown)
})
</script>

<style lang="stylus">
.dragged-session-avatar
	position: fixed
	top: 0
	left: 0
	pointer-events: none
	z-index: 99999
	will-change: transform
	cursor: grabbing
	opacity: 0.94
	visibility: hidden
	transform-origin: 20px 20px
	border-radius: 6px
	box-shadow: 0 14px 28px rgba(0, 0, 0, 0.22), 0 4px 10px rgba(0, 0, 0, 0.14)
	.c-linear-schedule-session
		margin: 0
		min-width: 0
		width: 100%
		cursor: grabbing
		pointer-events: none
		border-radius: 6px

.unassigned-drop-zone
	display: flex
	flex-direction: column
	align-items: stretch
	gap: 8px
	padding: 10px 12px
	margin: 0 0 12px 0
	border-radius: 8px
	border: 2px dashed #d97706
	background: linear-gradient(135deg, rgba(254, 243, 199, 0.95), rgba(253, 230, 138, 0.85))
	color: #92400e
	box-shadow: 0 2px 8px rgba(217, 119, 6, 0.1), 0 1px 2px rgba(0, 0, 0, 0.04)
	user-select: none
	pointer-events: none
	transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1)
	animation: dropZoneSlideDown 0.2s cubic-bezier(0.16, 1, 0.3, 1) both
	position: sticky
	top: 0
	z-index: 40
	.drop-zone-main
		display: flex
		align-items: center
		gap: 10px
		width: 100%
	.drop-zone-icon-wrap
		width: 30px
		height: 30px
		border-radius: 50%
		background: rgba(217, 119, 6, 0.15)
		display: flex
		align-items: center
		justify-content: center
		flex-shrink: 0
		color: #b45309
		font-size: 13px
		transition: transform 0.2s ease, background-color 0.2s ease, color 0.2s ease
	.drop-zone-content
		display: flex
		flex-direction: column
		align-items: flex-start
		text-align: left
		min-width: 0
	.drop-zone-title
		font-size: 12.5px
		font-weight: 600
		line-height: 1.25
		color: #92400e
	.drop-zone-subtitle
		font-size: 11px
		font-weight: 400
		color: #b45309
		opacity: 0.9
		line-height: 1.2
		margin-top: 1px
	.drop-zone-preview
		display: flex
		flex-direction: column
		gap: 6px
		width: 100%
		margin-top: 4px
		animation: dropZonePreviewIn 0.18s cubic-bezier(0.16, 1, 0.3, 1) both
		.unassigned-preview-pill
			width: 100%
			margin: 0
			min-width: 0
			box-sizing: border-box
			opacity: 0.95
			border-radius: 6px
			box-shadow: 0 4px 14px rgba(217, 119, 6, 0.22), 0 1px 3px rgba(0, 0, 0, 0.08)
			border: 1.5px solid rgba(217, 119, 6, 0.5)
			pointer-events: none
	&.is-hovered
		border-color: #b45309
		background: linear-gradient(135deg, #fef3c7, #fde68a)
		box-shadow: 0 6px 18px rgba(217, 119, 6, 0.25), 0 2px 4px rgba(217, 119, 6, 0.12)
		transform: translateY(-1px)
		.drop-zone-icon-wrap
			background: #b45309
			color: #ffffff
			transform: scale(1.08)
	&.is-break-drop
		border-color: #ef4444
		background: linear-gradient(135deg, rgba(254, 242, 242, 0.95), rgba(254, 226, 226, 0.85))
		color: #b91c1c
		box-shadow: 0 2px 8px rgba(239, 68, 68, 0.08), 0 1px 2px rgba(0, 0, 0, 0.04)
		.drop-zone-icon-wrap
			background: rgba(239, 68, 68, 0.12)
			color: #dc2626
		.drop-zone-title
			color: #b91c1c
		.drop-zone-subtitle
			color: #dc2626
		.drop-zone-preview
			.unassigned-preview-pill
				box-shadow: 0 4px 14px rgba(220, 38, 38, 0.18), 0 1px 3px rgba(0, 0, 0, 0.08)
				border: 1.5px solid rgba(220, 38, 38, 0.45)
		&.is-hovered
			border-color: #dc2626
			background: linear-gradient(135deg, #fee2e2, #fecaca)
			box-shadow: 0 6px 18px rgba(220, 38, 38, 0.22), 0 2px 4px rgba(220, 38, 38, 0.1)
			.drop-zone-icon-wrap
				background: #dc2626
				color: #ffffff

.pretalx-schedule
	display: flex
	flex-direction: column
	min-height: 0
	min-width: 0
	flex: 1
	height: 100%
	width: 100%
	font-size: 14px
	margin-left: 0
	font-family: var(--font-family)
	color: var(--color-text)
	h1, h2, h3, h4, h5, h6, legend, button, .btn
		font-family: var(--font-family-title)
	&.is-dragging
		user-select: none
		cursor: grabbing
	#main-wrapper
		display: flex
		flex: 1
		height: 100%
		min-height: 0
		min-width: 0
		position: relative
	&.is-public-shifts
		#main-wrapper
			display: block
		#schedule-wrapper
			width: 100%
			margin-right: 0
	.settings
		margin-left: 18px
		align-self: flex-start
		display: flex
		align-items: center
		position: sticky
		z-index: 100
		left: 18px
		.bunt-select
			max-width: 300px
			padding-right: 8px
		.timezone-label
			cursor: default
			color: $clr-secondary-text-light
	.date-selector
		margin-top: 17px
		display: flex
		align-items: center
		gap: 2px
		flex: 1
		min-width: 0
		height: 36px
		max-height: 36px
		overflow-x: auto
		overflow-y: hidden
		scrollbar-width: none
		padding: 0 4px
		box-sizing: border-box
		&::-webkit-scrollbar
			display: none

		.day-btn
			display: inline-flex
			align-items: center
			justify-content: center
			height: 36px
			padding: 0 14px
			border: none
			border-bottom: 2px solid transparent
			background: transparent
			cursor: pointer
			font-size: 13px
			font-weight: 500
			white-space: nowrap
			flex-shrink: 0
			color: #64748b
			font-family: inherit
			user-select: none
			transition: color 0.15s ease, border-color 0.15s ease, background-color 0.15s ease
			margin-bottom: -1px
			box-sizing: border-box

			&:hover:not(.active)
				color: #1e293b
				background-color: #f8fafc

			&.active
				color: var(--color-primary, #0284c7)
				border-bottom-color: var(--color-primary, #0284c7)
				font-weight: 600
				background-color: transparent

			&:focus-visible
				outline: 2px solid var(--color-primary, #0284c7)
				outline-offset: -2px
	#unassigned
		margin-top: 0
		box-sizing: border-box
		overflow-y: auto
		overflow-x: hidden
		scrollbar-width: thin
		scrollbar-color: #cbd5e1 transparent
		@media (min-width: 768px)
			width: 250px
			flex: none
			padding: 2px 8px 8px 2px
			border: 2px solid transparent
			border-right: 1px solid #e2e8f0
			height: calc(100% - 10px)
			min-height: 0
			transition: width 0.25s cubic-bezier(0.4, 0, 0.2, 1), padding 0.25s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.2s ease, background-color 0.2s ease, border-color 0.2s ease
			.unassigned-body,
			.deleted-room-sessions
				width: 236px
				min-width: 236px
				box-sizing: border-box
			&.is-sidebar-collapsed
				width: 0
				min-width: 0
				padding-left: 0
				padding-right: 0
				border-right-width: 0
				opacity: 0
				visibility: hidden
				pointer-events: none
		&.is-unassign-target
			background-color: rgba(217, 119, 6, 0.04)
			border: 2px dashed #d97706
			border-radius: 6px
			outline: none
			&.is-break-target
				background-color: rgba(239, 68, 68, 0.04)
				border: 2px dashed #ef4444
		&::-webkit-scrollbar
			width: 6px
		&::-webkit-scrollbar-track
			background: transparent
		&::-webkit-scrollbar-thumb
			background-color: #cbd5e1
			border-radius: 4px
			&:hover
				background-color: #94a3b8
		> *
			margin-right: 0
		.unassigned-body
			display: flex
			flex-direction: column
		.c-linear-schedule-session
			min-width: 0
		.c-linear-schedule-session:not(.new-break)
			margin: 0 0 8px 0
			min-height: 72px
			width: 100%
			box-sizing: border-box
			border-radius: 6px
			box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05)
			&:hover:not(.dragging):not(.clone),
			&:focus-within:not(.dragging):not(.clone)
				z-index: 1
			.time-box
				width: 52px
				padding: 8px 4px
				> .duration
					font-size: 12px
					font-weight: 600
			.info
				padding: 6px 8px
				.title
					font-size: 13px
					line-height: 1.3
					font-weight: 600
					margin-bottom: 2px
				.session-type
					font-size: 11px
					font-weight: 600
					text-transform: uppercase
					letter-spacing: 0.04em
					color: $clr-secondary-text-light
					margin-bottom: 2px
					display: block
					min-width: 0
					max-width: 100%
				.speakers
					font-size: 12px
					line-height: 1.25
					margin-bottom: 2px
				.bottom-info
					.track
						font-size: 11px
						line-height: 1.2
		.unassigned-header
			position: sticky
			top: 0
			z-index: 50
			background-color: $clr-white
			padding-bottom: 2px
			display: flex
			flex-direction: column
			width: 100%
			box-sizing: border-box

		.unassigned-header > .density-controls
			display: flex
			align-items: center
			gap: 6px
			width: 100%
			margin-bottom: 6px
			padding: 0
			box-sizing: border-box
			.density-btn
				flex: 1
				height: 30px
				background: #f8fafc
				border: 1px solid #cbd5e1
				border-radius: 6px
				padding: 0 8px
				cursor: pointer
				color: #334155
				display: flex
				align-items: center
				justify-content: center
				gap: 5px
				transition: all 0.15s ease
				font-size: 12px
				font-weight: 500
				box-sizing: border-box
				&:hover
					background-color: #f1f5f9
					border-color: #94a3b8
				&:focus-visible
					outline: 2px solid var(--color-primary, #3b82f6)
					outline-offset: -1px
				&.active
					background-color: #e2e8f0
					color: #0f172a
					border-color: #64748b
				.fa
					font-size: 12px
				.density-btn-text
					margin-left: 0
					white-space: nowrap
			.select-wrapper.custom-dropdown
				position: relative
				height: 30px
				display: flex
				align-items: center
				justify-content: space-between
				gap: 6px
				background-color: #f8fafc
				border: 1px solid #cbd5e1
				border-radius: 6px
				padding: 0 8px
				color: #334155
				cursor: pointer
				font-size: 12px
				font-weight: 500
				min-width: 65px
				box-sizing: border-box
				transition: all 0.15s ease
				&:hover
					background-color: #f1f5f9
					border-color: #94a3b8
				.fa-chevron-down
					font-size: 10px
					color: #64748b
				.time-density-menu, .vue-dropdown
					position: absolute
					top: calc(100% + 4px)
					right: 0
					background-color: white
					border-radius: 6px
					box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)
					border: 1px solid #e2e8f0
					z-index: 1000
					min-width: 105px
					display: flex
					flex-direction: column
					overflow: hidden
					cursor: default
					.density-option
						padding: 6px 10px
						display: flex
						justify-content: space-between
						align-items: center
						color: #374151
						cursor: pointer
						font-size: 12px
						&:hover
							background-color: #f1f5f9
						&.active
							background-color: #e2e8f0
							color: #111
						.fa-check
							font-size: 11px
							color: var(--color-primary, #3b82f6)
		.unassigned-header > .search-row
			position: relative
			padding: 0
			margin: 0 0 6px 0
			width: 100%
			display: flex
			align-items: center
			gap: 6px
			box-sizing: border-box
			.search-input-wrapper
				flex: 1
				height: 30px
				display: flex
				align-items: center
				gap: 6px
				padding: 0 8px
				background: #ffffff
				border: 1px solid #cbd5e1
				border-radius: 6px
				box-sizing: border-box
				transition: border-color 0.15s ease, box-shadow 0.15s ease
				&:focus-within
					border-color: var(--color-primary, #2185d0)
					box-shadow: 0 0 0 2px rgba(33, 133, 208, 0.18)
				.fa-search
					font-size: 12px
					color: #94a3b8
					flex-shrink: 0
				.search-input
					flex: 1
					height: 100%
					border: none
					outline: none
					background: transparent
					font-size: 12px
					color: #1e293b
					padding: 0
					min-width: 0
					box-sizing: border-box
					&::placeholder
						color: #94a3b8
						font-size: 12px
				.clear-search-btn
					border: none
					background: transparent
					color: #94a3b8
					cursor: pointer
					padding: 0
					margin: 0
					display: flex
					align-items: center
					justify-content: center
					font-size: 11px
					transition: color 0.15s ease
					&:hover
						color: #334155
			#unassigned-sort
				width: 30px
				height: 30px
				flex-shrink: 0
				display: flex
				align-items: center
				justify-content: center
				cursor: pointer
				border-radius: 6px
				background: #f8fafc
				border: 1px solid #cbd5e1
				color: #475569
				margin: 0
				box-sizing: border-box
				transition: all 0.15s ease
				&:hover
					background-color: #f1f5f9
					border-color: #94a3b8
					color: #0f172a
				&.active
					background-color: #e2e8f0
					border-color: #64748b
					color: #0f172a
				.fa
					font-size: 12px
		.new-break.c-linear-schedule-session
			min-height: 30px
			height: 30px
			margin: 0 0 6px 0
			width: 100%
			box-sizing: border-box
			border: 1.5px dashed #94a3b8
			border-radius: 6px
			background-color: #f8fafc
			transition: all 0.15s ease
			cursor: grab
			display: flex
			align-items: center
			justify-content: center
			user-select: none
			.time-box
				display: none
			.info
				width: 100%
				height: 100%
				display: flex
				align-items: center
				justify-content: center
				border: none
				background: transparent
				padding: 0
				border-radius: 6px
				.title
					font-size: 12px
					font-weight: 500
					color: #475569
					margin: 0
			&:hover
				border-color: var(--color-primary, #2185d0)
				background-color: #f0f7ff
				.info .title
					color: var(--color-primary, #2185d0)
			&:focus-visible
				outline: 2px solid var(--color-primary, #3b82f6)
				outline-offset: 2px
		.new-break.c-linear-schedule-session.desktop-break
			display: flex
		.new-break-hint
			display: block
			background: rgba(0, 0, 0, 0.75)
			color: white
			font-size: 12px
			line-height: 1.4
			padding: 5px 8px
			border-radius: 6px
			pointer-events: none
			margin: 0 0 6px 0
			width: 100%
			box-sizing: border-box
		.unschedule-hint
			margin: 0 0 6px 0
			padding: 6px 8px
			border-radius: 6px
			background-color: #fff4e5
			color: #7a4b00
			font-size: 12px
			line-height: 1.4
			width: 100%
			box-sizing: border-box
		#unassigned-sort-menu
			color: #1e293b
			display: flex
			flex-direction: column
			background-color: white
			position: absolute
			top: calc(100% + 4px)
			right: 0
			width: 130px
			font-size: 12px
			cursor: pointer
			z-index: 1000
			box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)
			border: 1px solid #e2e8f0
			border-radius: 6px
			overflow: hidden
			.sort-method
				padding: 6px 10px
				display: flex
				justify-content: space-between
				align-items: center
				transition: background-color 0.15s ease
				&:hover
					background-color: #f1f5f9
		.deleted-room-sessions
			margin: 24px 12px 0 8px
			padding-top: 16px
			border-top: 4px solid $clr-danger
			h3
				margin: 0 0 8px
				font-size: 18px
				font-weight: 600
				color: $clr-danger
			p
				margin: 0 8px 8px 0
				font-size: 13px
				line-height: 18px
				color: $clr-secondary-text-light
	.schedule-controls
		display: flex
		align-items: center
		position: sticky
		left: 0
		top: 0
		z-index: 50
		background-color: $clr-white
		width: 100%
		height: 36px
		max-height: 36px
		box-sizing: border-box
		overflow: visible
		border-bottom: 1px solid #e2e8f0
		padding-right: 0
	#schedule-wrapper
		flex: 1
		min-height: 0
		min-width: 0
		width: 100%
		height: 100%
		margin-right: 0
		margin-left: 8px
		box-sizing: border-box
		overflow: auto
		scrollbar-width: thin
		scrollbar-color: #cbd5e1 transparent
		&::-webkit-scrollbar
			width: 6px
			height: 6px
		&::-webkit-scrollbar-track
			background: transparent
		&::-webkit-scrollbar-thumb
			background-color: #cbd5e1
			border-radius: 4px
			&:hover
				background-color: #94a3b8

	#unassigned
		.unassigned-mobile-header
			display: none
			@media (max-width: 767px)
				display: flex
				align-items: center
				justify-content: space-between
				padding: 10px 14px
				background-color: #f8fafc
				border: 1px solid #cbd5e1
				border-radius: 6px
				margin-bottom: 8px
				cursor: pointer
				user-select: none
				.unassigned-title
					display: flex
					align-items: center
					gap: 8px
					font-weight: 600
					font-size: 14px
					color: #1e293b
					.drop-hint
						color: #b45309
						font-weight: 500
						&.is-break-hint
							color: #dc2626
				.unassigned-collapse-icon
					color: #64748b
					font-size: 14px

html[dir="rtl"],
html.rtl
	#unassigned
		padding: 0 0 8px 8px
		border-right: none
		border-left: 1px solid #e2e8f0
	#schedule-wrapper
		padding-left: 0
		margin-right: 8px
	.schedule-controls
		padding-right: 0
		padding-left: 220px

@media (max-width: 767px)
	.pretalx-schedule
		margin-left: 0
		margin-right: 0
		padding: 0 12px
		width: 100%
		height: auto
		box-sizing: border-box
		min-height: calc(100vh - 160px)
		#main-wrapper
			flex-direction: column
			width: 100%
			height: auto
			box-sizing: border-box
		#unassigned,
		#unassigned.is-sidebar-collapsed
			width: 100%
			min-width: 0
			max-width: 100%
			height: auto
			opacity: 1
			visibility: visible
			pointer-events: auto
			margin-top: 0
			margin-bottom: 12px
			background-color: $clr-white
			padding: 8px 0 4px 0
			border: none
			flex: none
			transition: none
			.unassigned-body,
			.deleted-room-sessions
				width: 100%
				min-width: 0
				max-width: 100%
				box-sizing: border-box
			&.is-collapsed
				.unassigned-body,
				.deleted-room-sessions
					display: none
			.unassigned-body
				max-height: 300px
				overflow-y: auto
				padding-bottom: 8px
				border-bottom: 1px solid #e2e8f0
				margin-bottom: 8px
				box-sizing: border-box
			> *
				margin-right: 0
			.c-linear-schedule-session
				margin: 8px 0
				width: 100%
				min-width: 0
				box-sizing: border-box
			.unassigned-header
				width: 100%
				box-sizing: border-box
				> .density-controls
					flex-wrap: nowrap
					align-items: center
					width: 100%
					box-sizing: border-box
					.density-btn
						padding: 4px 8px
						.density-btn-text
							display: none
		.schedule-controls
			padding-right: 0
			padding-left: 0
		#schedule-wrapper
			width: 100%
			margin-right: 0
			padding-left: 0
			padding-right: 0
			box-sizing: border-box
			overflow: auto

html[dir="rtl"],
html.rtl
	@media (max-width: 767px)
		.schedule-controls
			padding-right: 0
			padding-left: 0
		#unassigned
			padding: 8px 0 4px 0
			border-left: none
			border-right: none
		#schedule-wrapper
			padding-left: 0
			padding-right: 0

#session-editor-wrapper, #assign-modal-wrapper
	position: fixed
	z-index: 1000
	top: 0
	left: 0
	width: 100%
	height: 100%
	background-color: rgba(0, 0, 0, 0.5)

	#session-editor
		background-color: $clr-white
		border-radius: 4px
		padding: 32px 40px
		position: absolute
		top: 50%
		left: 50%
		transform: translate(-50%, -50%)
		width: unquote("min(680px, 95vw)")
		max-width: 95vw
		max-height: calc(100vh - 48px)
		overflow-y: auto

		.session-editor-title
			font-size: 22px
			margin-bottom: 16px
			display: flex
			justify-content: space-between
			align-items: center
			.modal-close-btn
				background: none
				border: none
				font-size: 20px
				color: #666
				cursor: pointer
				padding: 4px 8px
				line-height: 1
				border-radius: 4px
				&:hover
					color: #333
					background-color: rgba(0, 0, 0, 0.05)
		.button-row
			display: flex
			width: 100%
			margin-top: 24px

			.bunt-button-content
				font-size: 16px
			#btn-delete
				button-style(color: $clr-danger, text-color: $clr-white)
				font-weight: bold
			#btn-cancel
				font-weight: bold
				margin-left: 8px
				button-style(color: #6c757d)
			#btn-save
				margin-left: auto
				font-weight: bold
				button-style(color: #2185d0)
			[type="submit"]
				display: none
		.data
			display: flex
			flex-direction: column
			font-size: 16px
			.data-row
				.data-value
					padding-top: 8px
					ul
						list-style: none
						padding: 0
			.input-group
				position: relative
				display: flex
				flex-wrap: wrap
				align-items: stretch
				> input
					flex: 1 1 auto
					width: 1%
					min-width: 0
					border-top-right-radius: 0
					border-bottom-right-radius: 0
			.input-group-append
				display: flex
				margin-left: -1px
			.input-group-text
				display: flex
				align-items: center
				padding: 0.375rem 0.75rem
				color: var(--color-text-input)
				white-space: nowrap
				background-color: var(--color-grey-lighter)
				border: 1px solid var(--color-border)
				border-top-right-radius: var(--size-border-radius)
				border-bottom-right-radius: var(--size-border-radius)
			.role-row
				display: flex
				align-items: center
				gap: 10px
				margin-bottom: 10px
				.role-select
					flex: auto
				.role-capacity
					flex: none
					width: 100px
		.warning
			color: #b23e65
		.session-warnings
			.session-warnings-label
				display: flex
				flex-direction: row
				align-items: center
				justify-content: flex-end
				gap: 6px
				white-space: nowrap
				text-align: right
				i
					flex: none
					display: inline-flex
					color: #b23e65
					line-height: 1
					font-size: 14px
			.session-warnings-list
				margin: 0
				padding: 0
				list-style: none
				line-height: 1.4
				li + li
					margin-top: 4px
		.session-editor-error
			display: flex
			align-items: center
			justify-content: space-between
			gap: 8px
			padding: 10px 14px
			margin-bottom: 16px
			background-color: #fdecea
			border: 1px solid #f5c6cb
			border-radius: 4px
			color: #721c24
			font-size: 14px
			.session-editor-error-dismiss
				background: none
				border: none
				color: #721c24
				cursor: pointer
				padding: 2px 6px
				font-size: 14px
				&:hover
					opacity: 0.7
		.assign-data
			.assign-role
				margin-bottom: 24px
			.assign-new
				align-items: center
		.assign-modal-error
			display: flex
			align-items: center
			justify-content: space-between
			gap: 8px
			padding: 10px 14px
			margin-bottom: 16px
			background-color: #fdecea
			border: 1px solid #f5c6cb
			border-radius: 4px
			color: #721c24
			font-size: 14px
			.assign-modal-error-dismiss
				background: none
				border: none
				color: #721c24
				cursor: pointer
				padding: 2px 6px
				font-size: 14px
				&:hover
					opacity: 0.7
		.member-chip
			display: inline-flex
			align-items: center
			gap: 6px
			background-color: $clr-grey-200
			color: $clr-primary-text-light
			border-radius: 14px
			padding: 4px 6px 4px 12px
			margin: 0 6px 6px 0
			font-size: 13px
			line-height: 1.4
			.member-chip-remove
				display: inline-flex
				align-items: center
				justify-content: center
				width: 18px
				height: 18px
				border: none
				border-radius: 50%
				background: none
				color: $clr-danger
				cursor: pointer
				padding: 0
				font-size: 11px
				&:hover
					background-color: rgba(0, 0, 0, 0.08)
		.assign-btn
			width: 100%
			height: 100%
			min-height: 38px
			border: none
			border-radius: 4px
			background-color: #2185d0
			color: $clr-white
			font-weight: bold
			cursor: pointer
			&:hover
				background-color: #1c71b1
			&:disabled
				opacity: 0.6
				cursor: default
.break-confirm-dialog
	border: none
	border-radius: 4px
	padding: 0
	max-width: 400px
	box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2)
	&::backdrop
		background: rgba(0, 0, 0, 0.5)
	.dialog-inner
		padding: 32px 40px
		h3
			margin: 0 0 12px
			font-size: 18px
		p
			margin: 0 0 16px
			color: $clr-grey-700
			line-height: 1.4
		.break-confirm-error
			color: $clr-danger
			margin: 0 0 12px
		.break-confirm-actions
			display: flex
			justify-content: flex-end
			gap: 8px
			.btn
				display: inline-block
				padding: 6px 12px
				font-size: 14px
				line-height: 1.4
				border-radius: 4px
				border: 1px solid transparent
				cursor: pointer
				&:disabled
					opacity: 0.65
					cursor: default
			.btn-default
				background: $clr-white
				border-color: $clr-dividers-light
				color: $clr-grey-900
			.btn-danger
				button-style(color: $clr-danger, text-color: $clr-white)

@keyframes dropZoneSlideDown
	0%
		opacity: 0
		transform: translateY(-8px) scale(0.97)
	100%
		opacity: 1
		transform: translateY(0) scale(1)

@keyframes dropZonePreviewIn
	0%
		opacity: 0
		transform: translateY(-4px) scale(0.98)
	100%
		opacity: 1
		transform: translateY(0) scale(1)

.schedule-action-toast
	display: flex
	align-items: center
	justify-content: space-between
	gap: 12px
	background-color: #fee2e2
	border: 1px solid #ef4444
	color: #991b1b
	padding: 8px 14px
	margin: 8px 16px 0 16px
	border-radius: 6px
	font-size: 13px
	font-weight: 500
	box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08)
	animation: dropZoneSlideDown 0.2s ease-out both
	position: relative
	z-index: 50
	.action-toast-dismiss
		background: none
		border: none
		color: #991b1b
		cursor: pointer
		padding: 2px 6px
		border-radius: 4px
		&:hover
			background-color: rgba(239, 68, 68, 0.15)

.sidebar-divider-line
	position: absolute
	top: 0
	bottom: 0
	left: 250px
	width: 1px
	background-color: #e2e8f0
	z-index: 55
	pointer-events: none
	transition: left 0.25s cubic-bezier(0.4, 0, 0.2, 1), right 0.25s cubic-bezier(0.4, 0, 0.2, 1)
	&.is-collapsed
		left: 0

.sidebar-divider-toggle
	position: absolute
	left: 250px
	top: 50%
	transform: translate(-50%, -50%)
	z-index: 60
	width: 28px
	height: 28px
	min-width: 28px
	border-radius: 50%
	background-color: #ffffff
	border: 1px solid #cbd5e1
	box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1), 0 1px 3px rgba(0, 0, 0, 0.06)
	color: #475569
	display: inline-flex
	align-items: center
	justify-content: center
	cursor: pointer
	padding: 0
	transition: left 0.25s cubic-bezier(0.4, 0, 0.2, 1), right 0.25s cubic-bezier(0.4, 0, 0.2, 1), background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease
	&:hover
		background-color: #f1f5f9
		color: #0f172a
		border-color: #94a3b8
		box-shadow: 0 4px 10px rgba(0, 0, 0, 0.15)
	i
		font-size: 11px
		line-height: 1
	&.is-collapsed
		left: 0
		i.fa-bars
			font-size: 12px

@media (max-width: 767px)
	.sidebar-divider-line,
	.sidebar-divider-toggle
		display: none

.schedule-timezone-selector
	position: relative
	display: inline-block
	.timezone-btn
		display: inline-flex
		align-items: center
		gap: 6px
		height: 31px
		padding: 0 10px
		font-size: 13px
		font-weight: 500
		color: #475569
		background-color: #ffffff
		border: 1px solid #cbd5e1
		border-radius: 4px
		cursor: pointer
		transition: all 0.15s ease-in-out
		white-space: nowrap
		&:hover
			color: #1e293b
			background-color: #f8fafc
			border-color: #94a3b8
		i.fa-globe
			font-size: 13px
			color: #64748b
		i.fa-caret-down
			font-size: 11px
			color: #64748b
	.timezone-dropdown-menu
		position: absolute
		top: calc(100% + 4px)
		right: 0
		width: 260px
		max-width: calc(100vw - 24px)
		max-height: 340px
		background: #ffffff
		border: 1px solid #e2e8f0
		border-radius: 6px
		box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)
		z-index: 1000
		display: flex
		flex-direction: column
		padding: 6px 0
		font-size: 13px
		box-sizing: border-box
		.tz-section-label
			padding: 6px 12px 4px 12px
			font-size: 11px
			font-weight: 600
			text-transform: uppercase
			letter-spacing: 0.05em
			color: #94a3b8
		.tz-divider
			height: 1px
			background-color: #f1f5f9
			margin: 4px 0
		.tz-search-wrapper
			position: relative
			padding: 4px 10px
			box-sizing: border-box
			i.fa-search
				position: absolute
				left: 18px
				top: 50%
				transform: translateY(-50%)
				color: #94a3b8
				font-size: 12px
				pointer-events: none
			.tz-search-input
				width: 100%
				height: 28px
				padding: 0 8px 0 26px
				font-size: 12px
				border: 1px solid #e2e8f0
				border-radius: 4px
				outline: none
				box-sizing: border-box
				&:focus
					border-color: #3b82f6
		.tz-options-scroll
			overflow-y: auto
			max-height: 180px
			scrollbar-width: thin
		.tz-option
			display: flex
			align-items: center
			justify-content: space-between
			padding: 6px 12px
			cursor: pointer
			color: #334155
			transition: background-color 0.1s ease
			&:hover
				background-color: #f1f5f9
				color: #0f172a
			&.active
				background-color: #eff6ff
				color: #2563eb
				font-weight: 600
			.tz-option-name
				overflow: hidden
				text-overflow: ellipsis
				white-space: nowrap
			i.fa-check
				font-size: 12px
				color: #2563eb
				margin-left: 8px

html[dir="rtl"],
html.rtl
	#schedule-wrapper
		padding-left: 0
		margin-right: 8px
	.schedule-timezone-selector
		.timezone-dropdown-menu
			right: auto
			left: 0
	.sidebar-divider-line
		left: auto
		right: 250px
		&.is-collapsed
			left: auto
			right: 0
	.sidebar-divider-toggle
		left: auto
		right: 250px
		transform: translate(50%, -50%)
		i.fa-chevron-left
			transform: rotate(180deg)
		&.is-collapsed
			left: auto
			right: 0
			transform: translate(50%, -50%)
</style>

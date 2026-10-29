<template lang="pug">
.c-reports
	.ui-page-header
		bunt-icon-button(@click="$router.push({name: 'organizer'})", :tooltip="$t('Back to Overview')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
		h1 {{ $t('Online event reports') }}
	scrollbars(y).ui-form-body
		.report-section
			.section-header-with-controls
				.section-title-group
					h3 {{ $t('Online event analytics') }}
					p.section-description {{ $t('View and export analytics for the online event (PDF summary and spreadsheet exports), including room activity, session activity and tracked usage data.') }}
				.date-controls
					button.date-range-button(
						ref="dropdownButton",
						type="button",
						aria-haspopup="dialog",
						:aria-expanded="dropdownOpen ? 'true' : 'false'",
						:class="{open: dropdownOpen}",
						@click="toggleDropdown"
					)
						span.btn-label {{ $t('Date range') }}
						span.btn-divider
						span.btn-value {{ activeRangeDisplayLabel }}
						i.mdi.mdi-chevron-down(aria-hidden="true")

			.report-buttons
				bunt-button(@click="generateSummary", :error="task == 'summary' && error") {{ $t('Summary') }}
				bunt-button(@click="generateRoomviews", :error="task == 'roomviews' && error") {{ $t('Room Activity') }}
				bunt-button(v-if="world && world.pretalx", @click="generateSessionviews", :error="task == 'sessionviews' && error") {{ $t('Session Activity') }}
				bunt-button(@click="generateViews", :error="task == 'views' && error") {{ $t('Raw Tracking') }}

		.report-section
			.section-title-group
				h3 {{ $t('Attendee Reports') }}
				p.section-description {{ $t('Export attendee participation data as a spreadsheet (.xlsx) for the complete event or individual sessions.') }}
			.report-buttons
				bunt-button(@click="run('attendee_list', {})", :error="task == 'attendee_list' && error") {{ $t('All Attendees') }}
				bunt-button(@click="run('attendee_session_list', {})", :error="task == 'attendee_session_list' && error") {{ $t('By Session') }}

		.report-section
			.section-title-group
				h3 {{ $t('Room-Specific Reports') }}
				p.section-description {{ $t('Generate spreadsheet reports (.xlsx) for individual rooms, including available data such as chat history, questions and polls.') }}
			.room-reports-list
				.room-report-item
					bunt-select(v-model="channel", :label="$t('Chat History')", name="channel", :options="channels", option-label="name")
					bunt-button(@click="run('chat_history', {channel})", :disabled="!channel", :error="task == 'chat_history' && error") {{ $t('Generate') }}
				.room-report-item
					bunt-select(v-model="questionRoom", :label="$t('Questions')", name="questionRoom", :options="questionRooms", option-label="name")
					bunt-button(@click="run('question_history', {room: questionRoom})", :disabled="!questionRoom", :error="task == 'question_history' && error") {{ $t('Generate') }}
				.room-report-item
					bunt-select(v-model="pollRoom", :label="$t('Polls')", name="pollRoom", :options="pollRooms", option-label="name")
					bunt-button(@click="run('poll_history', {room: pollRoom})", :disabled="!pollRoom", :error="task == 'poll_history' && error") {{ $t('Generate') }}

	teleport(to="body")
		template(v-if="dropdownOpen")
			.date-range-blocker(@click="cancelDropdown")
			.date-range-popover(ref="dropdownMenu")
				.popover-body
					.presets-column
						button.preset-btn(
							v-if="hasEventDates",
							type="button",
							:class="{active: draftPreset === 'entire_event'}",
							@click="selectPresetById('entire_event')"
						)
							span {{ $t('Entire event') }}

						button.preset-btn(
							v-if="hasEventDates",
							type="button",
							:class="{active: isDayPresetActive}",
							@click="selectIndividualDay"
						)
							span {{ $t('Individual day') }}

						button.preset-btn(
							type="button",
							:class="{active: draftPreset === 'today'}",
							@click="selectPresetById('today')"
						)
							span {{ $t('Today') }}

						button.preset-btn(
							type="button",
							:class="{active: draftPreset === 'yesterday'}",
							@click="selectPresetById('yesterday')"
						)
							span {{ $t('Yesterday') }}

						template(v-if="!hasEventDates")
							button.preset-btn(
								type="button",
								:class="{active: draftPreset === 'last7days'}",
								@click="selectPresetById('last7days')"
							)
								span {{ $t('Last 7 Days') }}
							button.preset-btn(
								type="button",
								:class="{active: draftPreset === 'thisweek'}",
								@click="selectPresetById('thisweek')"
							)
								span {{ $t('This Week') }}

						button.preset-btn(
							type="button",
							:class="{active: draftPreset === 'custom'}",
							@click="selectPresetById('custom')"
						)
							span {{ $t('Custom range') }}
					.inputs-column
						template(v-if="isDayPresetActive")
							.day-selector-pane
								.day-grid-title {{ $t('Select event day') }}
								.day-cards-grid
									button.day-card(
										v-for="day in eventDays",
										:key="day.id",
										type="button",
										:class="{active: draftPreset === day.id}",
										@click="selectDay(day)"
									)
										span.day-card-num {{ $t('Day') }} {{ day.dayIndex }}
										span.day-card-date {{ day.dayDate }}
								.selected-day-details(v-if="currentSelectedDay")
									i.mdi.mdi-calendar-check(aria-hidden="true")
									span {{ currentSelectedDay.label }} (00:00 – 23:59)
								.timezone-note(v-if="eventTimezoneLabel")
									i.mdi.mdi-clock-outline(aria-hidden="true")
									span {{ $t('All times in') }} {{ eventTimezoneLabel }}

						template(v-else-if="draftPreset === 'entire_event'")
							.preset-summary-pane
								.day-grid-title {{ $t('Entire event') }}
								.selected-day-details
									i.mdi.mdi-calendar-range(aria-hidden="true")
									span {{ entireEventDetailsLabel }}
								.timezone-note(v-if="eventTimezoneLabel")
									i.mdi.mdi-clock-outline(aria-hidden="true")
									span {{ $t('All times in') }} {{ eventTimezoneLabel }}

						template(v-else-if="draftPreset === 'custom'")
							.datetime-fields
								.datetime-field
									label
										span {{ $t('Start') }} ({{ eventTimezoneLabel }})
									input.datetime-input(
										v-model="draftStart",
										name="draft_start",
										type="datetime-local",
										@input="onManualDateChange"
									)
								.datetime-field
									label
										span {{ $t('End') }} ({{ eventTimezoneLabel }})
									input.datetime-input(
										v-model="draftEnd",
										name="draft_end",
										type="datetime-local",
										@input="onManualDateChange"
									)
							.timezone-note(v-if="eventTimezoneLabel")
								i.mdi.mdi-clock-outline(aria-hidden="true")
								span {{ $t('All times in') }} {{ eventTimezoneLabel }}

						template(v-else)
							.preset-summary-pane
								.day-grid-title {{ activePresetTitle }}
								.selected-day-details
									i.mdi.mdi-calendar-clock(aria-hidden="true")
									span {{ activePresetDetailsLabel }}
								.timezone-note(v-if="eventTimezoneLabel")
									i.mdi.mdi-clock-outline(aria-hidden="true")
									span {{ $t('All times in') }} {{ eventTimezoneLabel }}
				.popover-footer
					bunt-button.btn-cancel(@click="cancelDropdown") {{ $t('Cancel') }}
					bunt-button.btn-apply(@click="applyDropdown") {{ $t('Apply') }}

	transition(name="prompt")
		prompt.report-result-prompt(v-if="running || result", @close="clear")
			.content
				.status-icon-wrap
					svg.spinner-svg(v-if="running", viewBox="0 0 50 50", xmlns="http://www.w3.org/2000/svg")
						circle.spinner-track(cx="25", cy="25", r="20", fill="none", stroke-width="4")
						circle.spinner-head(cx="25", cy="25", r="20", fill="none", stroke-width="4")
					i.mdi.mdi-check-circle-outline(v-else)
				h1(v-if="running") {{ $t('Preparing report…') }}
				h1(v-else) {{ $t('Report ready') }}
				p.status-desc(v-if="running") {{ $t('If your event is large, this might take multiple minutes.') }}
				bunt-button.btn-download(v-else, @click="open") {{ $t('Download report') }}

</template>
<script>
import { mapState } from 'vuex'
import config from 'config'
import api from 'lib/api'
import moment from 'lib/timetravelMoment'
import Prompt from 'components/Prompt'
import { createPopper } from '@popperjs/core'

export default {
	components: { Prompt },
	data() {
		return {
			popperInstance: null,
			dropdownOpen: false,
			activePreset: null,
			draftPreset: null,
			datetimeStart: '',
			datetimeEnd: '',
			draftStart: '',
			draftEnd: '',
			selectedDayId: 'day_1',
			channel: null,
			questionRoom: null,
			pollRoom: null,
			resultid: null,
			result: null,
			running: false,
			error: false,
			timeout: null,
			task: null,
		}
	},
	computed: {
		...mapState(['world']),
		eventTimezone() {
			const raw = (
				(typeof window !== 'undefined' && window.eventyay?.eventTimezone) ||
				config?.eventTimezone ||
				this.world?.timezone ||
				this.world?.eventTimezone ||
				this.world?.event_timezone ||
				this.$store.state.world?.timezone ||
				this.$store.state.schedule?.meta?.timezone ||
				(typeof window !== 'undefined' && window.eventyay?.scheduleMeta?.timezone) ||
				'UTC'
			)
			if (typeof raw === 'string') return raw
			return raw?.key || raw?.name || String(raw || 'UTC')
		},
		eventTimezoneLabel() {
			return this.eventTimezone.replace(/_/g, ' ')
		},
		eventDateFrom() {
			return (
				this.world?.date_from ||
				(typeof window !== 'undefined' && window.eventyay?.eventDates?.date_from) ||
				config?.eventDates?.date_from ||
				null
			)
		},
		eventDateTo() {
			return (
				this.world?.date_to ||
				(typeof window !== 'undefined' && window.eventyay?.eventDates?.date_to) ||
				config?.eventDates?.date_to ||
				null
			)
		},
		hasEventDates() {
			return this.eventDays.length > 0
		},
		isDayPresetActive() {
			return typeof this.draftPreset === 'string' && this.draftPreset.startsWith('day_')
		},
		currentSelectedDay() {
			return this.eventDays.find(d => d.id === this.draftPreset) || this.eventDays[0] || null
		},
		eventDays() {
			const tz = this.eventTimezone
			const rawFrom = this.eventDateFrom
			const rawTo = this.eventDateTo
			const dateFrom = rawFrom ? moment.tz(rawFrom, tz) : null
			const dateTo = rawTo ? moment.tz(rawTo, tz) : (dateFrom ? dateFrom.clone() : null)

			if (!dateFrom || !dateTo || dateTo.isBefore(dateFrom)) return []

			const startDay = dateFrom.clone().startOf('day')
			const endDay = dateTo.clone().startOf('day')
			const totalDays = endDay.diff(startDay, 'days') + 1
			const maxDays = Math.min(totalDays, 60)
			const days = []

			for (let i = 0; i < maxDays; i++) {
				const dayMoment = startDay.clone().add(i, 'days')
				const dayIndex = i + 1
				days.push({
					id: `day_${dayIndex}`,
					dayIndex,
					dayDate: dayMoment.format('D MMM'),
					label: `${this.$t('Day')} ${dayIndex} — ${dayMoment.format('D MMM')}`,
					start: dayMoment.clone().startOf('day'),
					end: dayMoment.clone().endOf('day'),
				})
			}
			return days
		},
		dateRangeOptions() {
			const tz = this.eventTimezone
			const now = moment().tz(tz)
			const options = []

			const rawFrom = this.eventDateFrom
			const rawTo = this.eventDateTo
			const dateFrom = rawFrom ? moment.tz(rawFrom, tz) : null
			const dateTo = rawTo ? moment.tz(rawTo, tz) : (dateFrom ? dateFrom.clone() : null)

			if (dateFrom && dateTo && dateTo.isSameOrAfter(dateFrom)) {
				const eventStart = dateFrom.clone()
				const eventEnd = (dateTo.hours() === 0 && dateTo.minutes() === 0)
					? dateTo.clone().endOf('day')
					: dateTo.clone()

				options.push({
					id: 'entire_event',
					label: this.$t('Entire event'),
					start: eventStart,
					end: eventEnd,
				})

				options.push(...this.eventDays)

				options.push({
					id: 'today',
					label: this.$t('Today'),
					start: now.clone().startOf('day'),
					end: now.clone().endOf('day'),
				})

				options.push({
					id: 'yesterday',
					label: this.$t('Yesterday'),
					start: now.clone().subtract(1, 'day').startOf('day'),
					end: now.clone().subtract(1, 'day').endOf('day'),
				})
			} else {
				options.push({
					id: 'today',
					label: this.$t('Today'),
					start: now.clone().startOf('day'),
					end: now.clone().endOf('day'),
				})

				options.push({
					id: 'yesterday',
					label: this.$t('Yesterday'),
					start: now.clone().subtract(1, 'day').startOf('day'),
					end: now.clone().subtract(1, 'day').endOf('day'),
				})

				options.push({
					id: 'last7days',
					label: this.$t('Last 7 Days'),
					start: now.clone().subtract(6, 'days').startOf('day'),
					end: now.clone().endOf('day'),
				})

				options.push({
					id: 'thisweek',
					label: this.$t('This Week'),
					start: now.clone().startOf('week'),
					end: now.clone().endOf('week'),
				})
			}

			options.push({
				id: 'custom',
				label: this.$t('Custom range'),
			})

			return options
		},
		activeRangeDisplayLabel() {
			if (this.activePreset === 'custom') {
				if (this.datetimeStart && this.datetimeEnd) {
					const tz = this.eventTimezone
					const startM = moment.tz(this.datetimeStart, tz)
					const endM = moment.tz(this.datetimeEnd, tz)
					if (startM.isValid() && endM.isValid()) {
						return `${startM.format('D MMM')} – ${endM.format('D MMM')}`
					}
				}
				return this.$t('Custom range')
			}
			const option = this.dateRangeOptions.find(o => o.id === this.activePreset)
			return option ? option.label : this.$t('Date range')
		},
		entireEventDetailsLabel() {
			const tz = this.eventTimezone
			const start = this.draftStart ? moment.tz(this.draftStart, tz) : null
			const end = this.draftEnd ? moment.tz(this.draftEnd, tz) : null
			if (start && end && start.isValid() && end.isValid()) {
				const isSameDay = start.isSame(end, 'day')
				if (isSameDay) {
					return `${start.format('D MMM YYYY')} (${start.format('hh:mm A')} – ${end.format('hh:mm A')})`
				}
				const daysCount = this.eventDays.length || (end.clone().startOf('day').diff(start.clone().startOf('day'), 'days') + 1)
				const countLabel = daysCount > 1 ? ` (${daysCount} ${this.$t('Days')})` : ''
				const startFormatted = start.format('D MMM, hh:mm A')
				const endFormatted = end.format('D MMM, hh:mm A')
				return `${startFormatted} – ${endFormatted}${countLabel}`
			}
			return this.$t('Entire event')
		},
		activePresetTitle() {
			const option = this.dateRangeOptions.find(o => o.id === this.draftPreset)
			return option ? option.label : this.$t('Date range')
		},
		activePresetDetailsLabel() {
			const tz = this.eventTimezone
			const start = this.draftStart ? moment.tz(this.draftStart, tz) : null
			const end = this.draftEnd ? moment.tz(this.draftEnd, tz) : null
			if (start && end && start.isValid() && end.isValid()) {
				if (start.isSame(end, 'day')) {
					return `${start.format('D MMM YYYY')} (00:00 – 23:59)`
				}
				return `${start.format('D MMM')} – ${end.format('D MMM')}`
			}
			return ''
		},
		questionRooms() {
			return this.$store.state.rooms.filter((room) => room.modules.some(m => m.type === 'question'))
		},
		pollRooms() {
			return this.$store.state.rooms.filter((room) => room.modules.some(m => m.type === 'poll'))
		},
		channels() {
			return this.$store.state.rooms.filter((room) => room.modules.some(m => m.type === 'chat.native')).map((room) => {
				return {
					id: room.modules.find(m => m.type === 'chat.native').channel_id,
					name: room.name
				}
			})
		}
	},
	watch: {
		dateRangeOptions: {
			immediate: true,
			handler(newOptions) {
				if (!newOptions || newOptions.length === 0) return
				if (this.eventDays.length > 0 && (!this.selectedDayId || !this.eventDays.some(d => d.id === this.selectedDayId))) {
					this.selectedDayId = this.eventDays[0].id
				}
				if (this.activePreset && this.activePreset.startsWith('day_')) {
					this.selectedDayId = this.activePreset
				}
				const hasActive = this.activePreset && newOptions.some(o => o.id === this.activePreset)
				const hasEntireEvent = newOptions.some(o => o.id === 'entire_event')

				if (!hasActive || (!this._hasSeenEntireEvent && hasEntireEvent)) {
					const defaultOption = hasEntireEvent ? newOptions.find(o => o.id === 'entire_event') : newOptions[0]
					this._hasSeenEntireEvent = hasEntireEvent
					this.activePreset = defaultOption.id
					this.draftPreset = defaultOption.id
					if (defaultOption.start && defaultOption.end) {
						this.datetimeStart = this.formatDateTime(defaultOption.start)
						this.datetimeEnd = this.formatDateTime(defaultOption.end)
						this.draftStart = this.datetimeStart
						this.draftEnd = this.datetimeEnd
					}
				} else if (this.activePreset !== 'custom') {
					const currentOption = newOptions.find(o => o.id === this.activePreset)
					if (currentOption?.start && currentOption?.end) {
						this.datetimeStart = this.formatDateTime(currentOption.start)
						this.datetimeEnd = this.formatDateTime(currentOption.end)
						if (!this.dropdownOpen) {
							this.draftStart = this.datetimeStart
							this.draftEnd = this.datetimeEnd
						}
					}
				}
			}
		}
	},
	unmounted() {
		window.clearTimeout(this.timeout)
		window.removeEventListener('keydown', this.onEscKey)
		this.destroyPopper()
	},
	methods: {
		onEscKey(event) {
			if (event.key === 'Escape' && this.dropdownOpen) {
				event.preventDefault()
				this.cancelDropdown()
			}
		},
		formatDateTime(m) {
			return m ? m.format('YYYY-MM-DDTHH:mm') : ''
		},
		selectPresetById(id) {
			const option = this.dateRangeOptions.find(o => o.id === id)
			if (!option) return
			this.draftPreset = option.id
			if (option.start && option.end) {
				this.draftStart = this.formatDateTime(option.start)
				this.draftEnd = this.formatDateTime(option.end)
			}
		},
		selectIndividualDay() {
			if (!this.selectedDayId && this.eventDays.length > 0) {
				this.selectedDayId = this.eventDays[0].id
			}
			const dayToSelect = this.eventDays.find(d => d.id === this.selectedDayId) || this.eventDays[0]
			if (dayToSelect) {
				this.selectDay(dayToSelect)
			}
		},
		selectDay(day) {
			this.selectedDayId = day.id
			this.draftPreset = day.id
			if (day.start && day.end) {
				this.draftStart = this.formatDateTime(day.start)
				this.draftEnd = this.formatDateTime(day.end)
			}
		},
		onManualDateChange() {
			this.draftPreset = 'custom'
		},
		async toggleDropdown() {
			if (this.dropdownOpen) {
				this.cancelDropdown()
				return
			}
			this.draftPreset = this.activePreset
			if (this.activePreset && this.activePreset.startsWith('day_')) {
				this.selectedDayId = this.activePreset
			} else if (this.eventDays.length > 0 && !this.selectedDayId) {
				this.selectedDayId = this.eventDays[0].id
			}
			this.draftStart = this.datetimeStart
			this.draftEnd = this.datetimeEnd
			this.dropdownOpen = true
			window.addEventListener('keydown', this.onEscKey)
			await this.$nextTick()
			this.initPopper()
			requestAnimationFrame(() => {
				this.popperInstance?.forceUpdate?.()
			})
		},
		initPopper() {
			this.destroyPopper()
			if (!this.$refs.dropdownButton || !this.$refs.dropdownMenu) return
			this.popperInstance = createPopper(this.$refs.dropdownButton, this.$refs.dropdownMenu, {
				placement: 'bottom-end',
				strategy: 'fixed',
				modifiers: [
					{
						name: 'offset',
						options: {
							offset: [0, 8]
						}
					},
					{
						name: 'preventOverflow',
						options: {
							padding: 12
						}
					},
					{
						name: 'flip',
						options: {
							fallbackPlacements: ['top-end', 'bottom-start', 'top-start']
						}
					}
				]
			})
		},
		destroyPopper() {
			if (this.popperInstance) {
				this.popperInstance.destroy()
				this.popperInstance = null
			}
		},
		closeDropdown() {
			window.removeEventListener('keydown', this.onEscKey)
			this.destroyPopper()
			this.dropdownOpen = false
		},
		applyDropdown() {
			this.activePreset = this.draftPreset
			this.datetimeStart = this.draftStart
			this.datetimeEnd = this.draftEnd
			this.closeDropdown()
		},
		cancelDropdown() {
			this.draftPreset = this.activePreset
			if (this.activePreset && this.activePreset.startsWith('day_')) {
				this.selectedDayId = this.activePreset
			}
			this.draftStart = this.datetimeStart
			this.draftEnd = this.datetimeEnd
			this.closeDropdown()
		},
		getDateTimePayload() {
			return {
				begin: this.datetimeStart,
				end: this.datetimeEnd,
			}
		},
		generateReport(type) {
			return this.run(type, this.getDateTimePayload())
		},
		generateSummary() {
			return this.generateReport('summary')
		},
		generateRoomviews() {
			return this.generateReport('roomviews')
		},
		generateSessionviews() {
			return this.generateReport('sessionviews')
		},
		generateViews() {
			return this.generateReport('views')
		},
		async run(name, payload) {
			this.running = true
			this.error = false
			this.task = name
			try {
				const r = await api.call(`world.report.generate.${name}`, payload)
				this.resultid = r.resultid
				this.timeout = window.setTimeout(this.check, 2000)
			} catch (err) {
				console.error('Report generation failed:', String(err))
				this.error = true
				this.running = false
			}
		},
		async check() {
			try {
				const r = await api.call('world.report.status', {
					resultid: this.resultid
				})
				if (r.ready) {
					this.result = r.result
					this.error = false
					this.running = false
				} else {
					this.timeout = window.setTimeout(this.check, 2000)
				}
			} catch (err) {
				console.error('Report status check failed:', String(err))
				this.error = true
				this.running = false
			}
		},
		open() {
			window.open(this.result)
			this.clear()
		},
		clear() {
			this.result = null
			this.error = false
			this.running = false
			window.clearTimeout(this.timeout)
		}
	}
}
</script>
<style lang="stylus">
.c-reports
	flex: auto
	display: flex
	flex-direction: column

	.ui-form-body
		padding: 20px
		max-width: 100%

	.report-section
		margin-bottom: 32px
		padding: 16px 20px 24px 20px
		background: $clr-white
		border-radius: 4px
		box-shadow: 0 1px 3px rgba(0,0,0,0.08)

		h3
			margin: 0 0 6px 0
			font-size: 18px
			font-weight: 600
			line-height: 1.4

		.section-title-group
			margin-bottom: 16px

			.section-description
				margin: 0
				font-size: 13px
				color: $clr-secondary-text-light
				line-height: 1.4
				max-width: 640px

		.section-header-with-controls
			display: flex
			justify-content: space-between
			align-items: flex-start
			gap: 24px
			margin-bottom: 16px
			flex-wrap: wrap

			.section-title-group
				margin-bottom: 0
				flex: 1
				min-width: 280px

			.date-controls
				display: flex
				align-items: center
				justify-content: flex-end
				min-width: 200px

				.date-range-button
					display: inline-flex
					align-items: center
					gap: 8px
					height: 36px
					padding: 0 12px
					background: $clr-white
					border: 1px solid $clr-grey-300
					border-radius: 4px
					font-size: 13px
					font-family: inherit
					cursor: pointer
					transition: border-color 0.15s ease, box-shadow 0.15s ease
					box-sizing: border-box

					&:hover
						border-color: var(--clr-primary, #2185d0)
						background: var(--clr-input-secondary-fg-alpha, rgba(33, 133, 208, 0.04))

					&.open
						border-color: var(--clr-primary, #2185d0)
						box-shadow: 0 0 0 2px var(--clr-primary-alpha-18, rgba(33, 133, 208, 0.2))

					.btn-label
						font-weight: 600
						color: $clr-primary-text-light

					.btn-divider
						width: 1px
						height: 16px
						background-color: $clr-grey-300

					.btn-value
						font-weight: 600
						color: var(--clr-primary, #2185d0)

					.mdi-chevron-down
						font-size: 18px
						color: $clr-secondary-text-light
						transition: transform 0.2s ease

					&.open .mdi-chevron-down
						transform: rotate(180deg)

		.report-buttons
			display: flex
			flex-wrap: wrap
			gap: 12px

			button
				themed-button-secondary()
				flex-shrink: 0
				background-color: var(--clr-input-secondary-fg-alpha)

		.room-reports-list
			display: flex
			flex-direction: column
			gap: 8px

			.room-report-item
				display: flex
				align-items: center
				gap: 16px

				.bunt-select
					flex: 1
					max-width: 400px

					.bunt-input
						height: auto
						padding-top: 10px
						margin-bottom: 0

						.hint
							display: none

				button
					themed-button-secondary()
					flex-shrink: 0
					background-color: var(--clr-input-secondary-fg-alpha)

	.report-result-prompt
		.content
			padding: 32px 28px 28px
			text-align: center
			display: flex
			flex-direction: column
			align-items: center
			gap: 12px
			h1
				margin: 0
				font-size: 20px
				font-weight: 600
				color: $clr-grey-900
			.status-icon-wrap
				width: 64px
				height: 64px
				display: flex
				align-items: center
				justify-content: center
				.spinner-svg
					width: 56px
					height: 56px
					animation: spinner-rotate 1.4s linear infinite
					.spinner-track
						stroke: rgba(0, 0, 0, 0.08)
					.spinner-head
						stroke: var(--clr-primary, #bb0011)
						stroke-dasharray: 80 200
						stroke-dashoffset: 0
						stroke-linecap: round
						animation: spinner-dash 1.4s ease-in-out infinite
				.mdi
					font-size: 56px
					color: var(--clr-primary, #bb0011)
					opacity: 0.85
			.status-desc
				margin: 0
				font-size: 14px
				color: $clr-secondary-text-light
				max-width: 280px
			.btn-download
				themed-button-primary()
				margin-top: 4px

.date-range-blocker
	position: fixed
	top: 0
	left: 0
	width: 100vw
	height: 100vh
	z-index: 1290
	background: transparent

.date-range-popover
	position: fixed
	z-index: 1300
	background: $clr-white
	border-radius: 4px
	box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15), 0 2px 6px rgba(0, 0, 0, 0.08)
	border: 1px solid $clr-grey-300
	overflow: hidden
	display: flex
	flex-direction: column
	min-width: 480px
	max-width: 540px

	.popover-body
		display: flex
		padding: 16px
		gap: 16px
		border-bottom: 1px solid $clr-grey-200

	.presets-column
		display: flex
		flex-direction: column
		gap: 4px
		width: 160px
		flex-shrink: 0
		border-right: 1px solid $clr-grey-200
		padding-right: 12px

		.preset-btn
			background: transparent
			border: none
			text-align: left
			padding: 8px 12px
			border-radius: 4px
			font-size: 13px
			color: $clr-primary-text-light
			cursor: pointer
			transition: background-color 0.15s, color 0.15s
			font-weight: 500

			&:hover
				background: $clr-grey-100
				color: var(--clr-primary, #2185d0)

			&.active
				background: var(--clr-primary-alpha-18, rgba(33, 133, 208, 0.15))
				color: var(--clr-primary, #2185d0)
				font-weight: 600

	.inputs-column
		flex: 1
		display: flex
		flex-direction: column
		gap: 14px
		justify-content: center
		padding-left: 4px

		.day-selector-pane
			display: flex
			flex-direction: column
			gap: 8px

			.day-grid-title
				font-size: 11px
				font-weight: 600
				color: $clr-secondary-text-light

			.day-cards-grid
				display: grid
				grid-template-columns: repeat(auto-fill, minmax(62px, 1fr))
				gap: 5px
				max-height: 145px
				overflow-y: auto
				padding: 2px 2px 4px 2px

				&::-webkit-scrollbar
					width: 4px
				&::-webkit-scrollbar-track
					background: transparent
				&::-webkit-scrollbar-thumb
					background: $clr-grey-300
					border-radius: 2px

				.day-card
					display: flex
					flex-direction: column
					align-items: center
					justify-content: center
					padding: 4px 4px
					min-height: 34px
					background: $clr-white
					border: 1px solid $clr-grey-300
					border-radius: 4px
					cursor: pointer
					font-family: inherit
					transition: border-color 0.15s ease, background-color 0.15s ease, box-shadow 0.15s ease
					box-sizing: border-box

					&:hover
						border-color: var(--clr-primary, #2185d0)
						background: var(--clr-input-secondary-fg-alpha, rgba(33, 133, 208, 0.04))

					&.active
						border-color: var(--clr-primary, #2185d0)
						background: var(--clr-primary-alpha-18, rgba(33, 133, 208, 0.12))
						box-shadow: 0 0 0 1px var(--clr-primary, #2185d0)

						.day-card-num
							color: var(--clr-primary, #2185d0)

						.day-card-date
							color: var(--clr-primary, #2185d0)

					.day-card-num
						font-size: 10px
						font-weight: 600
						line-height: 1.1
						color: $clr-secondary-text-light
						margin-bottom: 1px

					.day-card-date
						font-size: 11px
						font-weight: 600
						line-height: 1.2
						color: $clr-primary-text-light
						white-space: nowrap

		.day-grid-title
			font-size: 11px
			font-weight: 600
			color: $clr-secondary-text-light

		.selected-day-details
			display: flex
			align-items: center
			gap: 6px
			font-size: 11px
			font-weight: 500
			color: $clr-primary-text-light
			padding: 6px 10px
			background: $clr-grey-50
			border: 1px solid $clr-grey-200
			border-radius: 4px

			.mdi
				font-size: 14px
				color: var(--clr-primary, #2185d0)

		.preset-summary-pane
			display: flex
			flex-direction: column
			gap: 8px

		.datetime-fields
			display: flex
			flex-direction: column
			gap: 12px

			.datetime-field
				display: flex
				flex-direction: column
				gap: 4px

				label
					display: flex
					align-items: center
					justify-content: space-between
					font-size: 12px
					font-weight: 600
					color: $clr-secondary-text-light

				.datetime-input
					height: 38px
					padding: 6px 10px
					border: 1px solid $clr-grey-300
					border-radius: 4px
					font-size: 13px
					font-family: inherit
					color: $clr-primary-text-light
					background-color: $clr-white
					box-sizing: border-box
					transition: border-color 0.15s ease, box-shadow 0.15s ease

					&:hover
						border-color: var(--clr-primary, #2185d0)

					&:focus
						border-color: var(--clr-primary, #2185d0)
						outline: none
						box-shadow: 0 0 0 2px var(--clr-primary-alpha-18, rgba(33, 133, 208, 0.18))

		.timezone-note
			display: flex
			align-items: center
			gap: 6px
			font-size: 12px
			color: $clr-secondary-text-light
			margin-top: 4px

			.mdi
				font-size: 16px
				color: var(--clr-primary, #2185d0)

	.popover-footer
		display: flex
		justify-content: flex-end
		align-items: center
		gap: 8px
		padding: 10px 16px
		background: $clr-grey-50
		border-top: 1px solid $clr-grey-200

		button
			font-size: 13px
			padding: 6px 14px
			border-radius: 4px

		.btn-cancel
			themed-button-secondary()
			background: transparent
			border: 1px solid $clr-grey-300

		.btn-apply
			themed-button-primary()

@keyframes spinner-rotate
	100%
		transform: rotate(360deg)

@keyframes spinner-dash
	0%
		stroke-dasharray: 1 200
		stroke-dashoffset: 0
	50%
		stroke-dasharray: 89 200
		stroke-dashoffset: -35px
	100%
		stroke-dasharray: 89 200
		stroke-dashoffset: -124px

@media (max-width: 600px)
	.date-range-popover
		min-width: 290px
		max-width: calc(100vw - 24px)

		.popover-body
			flex-direction: column
			gap: 12px

		.presets-column
			width: 100%
			border-right: none
			border-bottom: 1px solid $clr-grey-200
			padding-right: 0
			padding-bottom: 8px
</style>

<template lang="pug">
.c-schedule-view
	template(v-if="scheduleReady")
		.filter-actions
			app-dropdown(v-for="item in filterGroups", :key="item.refKey", className="schedule")
				template(#toggler)
					span {{ item.title }}
					app-dropdown-content(className="schedule")
						app-dropdown-item(v-for="entry in item.data", :key="entry.value")
							label.checkbox-line(:style="{'--track-color': entry.color}")
								input.filter-checkbox(type="checkbox", v-model="entry.selected", @change="onFilterChange")
								span.checkbox-label {{ entry.label }}
			button.fav-toggle(:class="{active: onlyFavs}", @click="toggleFavs")
				| ★ {{ resolvedFavs.length }}
			button.reset-btn(@click="resetAllFilters")
				| ✕
			.timezone-area(v-if="!inEventTimezone")
				select.timezone-select(v-model="currentTimezone", @change="saveTimezone")
					option(:value="resolvedSchedule.timezone") {{ resolvedSchedule.timezone }}
					option(:value="userTimezone") {{ userTimezone }}
			.timezone-label(v-else) {{ resolvedSchedule.timezone }}
			.export-area
				export-dropdown(:baseUrl="resolvedExportBaseUrl", :qrCodeModule="qrCodeModule", @export="onExport")
		.day-tabs(v-if="computedDays && computedDays.length > 1")
			button.day-tab(
				v-for="day in computedDays",
				:key="day.format('YYYY-MM-DD')",
				:class="{active: currentDay === day.format('YYYY-MM-DD')}",
				@click="changeDay(day)"
			) {{ day.format(dateFormat) }}
		.schedule-content(ref="scrollParent")
			grid-schedule-wrapper(v-if="showGrid",
				:sessions="filteredSessions",
				:rooms="computedRooms",
				:days="computedDays",
				:currentDay="currentDay",
				:now="resolvedNow",
				:hasAmPm="resolvedHasAmPm",
				:timezone="currentTimezone",
				:locale="locale",
				:scrollParent="$refs.scrollParent",
				:favs="resolvedFavs",
				@changeDay="setCurrentDay",
				@fav="onFav",
				@unfav="onUnfav")
			linear-schedule(v-else,
				:sessions="filteredSessions",
				:rooms="computedRooms",
				:currentDay="currentDay",
				:now="resolvedNow",
				:hasAmPm="resolvedHasAmPm",
				:timezone="currentTimezone",
				:locale="locale",
				:scrollParent="$refs.scrollParent",
				:favs="resolvedFavs",
				:sortBy="sortBy",
				@changeDay="dayScrolled",
				@fav="onFav",
				@unfav="onUnfav")
	.schedule-error(v-else-if="hasError")
		| An error occurred while loading the schedule.
	.schedule-loading(v-else)
		| Loading…
</template>

<script>
import moment from 'moment-timezone'
import LinearSchedule from './LinearSchedule'
import GridScheduleWrapper from './GridScheduleWrapper'
import ExportDropdown from './ExportDropdown'
import AppDropdown from './AppDropdown'
import AppDropdownContent from './AppDropdownContent'
import AppDropdownItem from './AppDropdownItem'
import { getLocalizedString } from '../utils'

export default {
	name: 'ScheduleView',
	components: { LinearSchedule, GridScheduleWrapper, ExportDropdown, AppDropdown, AppDropdownContent, AppDropdownItem },
	inject: {
		scheduleData: { default: null },
		scheduleFav: { default: null },
		scheduleUnfav: { default: null },
		scheduleDoExport: { default: null },
		exportBaseUrl: { default: '' },
		qrCodeModule: { default: null }
	},
	props: {
		schedule: Object,
		sessions: Array,
		rooms: Array,
		days: Array,
		favs: Array,
		now: Object,
		timezone: String,
		locale: String,
		hasAmPm: Boolean,
		onHomeServer: Boolean,
		errorLoading: Object,
		linearOnly: {
			type: Boolean,
			default: false
		},
		sortBy: {
			type: String,
			default: 'room'
		},
		exportUrl: {
			type: String,
			default: ''
		}
	},
	emits: ['fav', 'unfav', 'export'],
	data() {
		return {
			currentDay: null,
			onlyFavs: false,
			scrollParentWidth: Infinity,
			currentTimezone: null,
			userTimezone: null,
			filterState: {
				tracks: [],
				rooms: [],
				types: []
			}
		}
	},
	computed: {
		resolvedSchedule() {
			return this.scheduleData?.schedule || this.schedule
		},
		resolvedNow() {
			return this.scheduleData?.now || this.now || moment()
		},
		resolvedFavs() {
			return this.scheduleData?.favs || this.favs || []
		},
		resolvedHasAmPm() {
			if (this.hasAmPm !== undefined && this.hasAmPm !== null) return this.hasAmPm
			if (this.scheduleData?.hasAmPm !== undefined) return this.scheduleData.hasAmPm
			return new Intl.DateTimeFormat(undefined, { hour: 'numeric' }).resolvedOptions().hour12
		},
		resolvedExportBaseUrl() {
			return this.exportUrl || this.exportBaseUrl || ''
		},
		scheduleReady() {
			return !!(this.resolvedSchedule && this.enrichedSessions.length)
		},
		hasError() {
			return !!(this.errorLoading || this.scheduleData?.errorLoading)
		},
		tracksLookup() {
			if (!this.resolvedSchedule) return {}
			return (this.resolvedSchedule.tracks || []).reduce((acc, t) => { acc[t.id] = t; return acc }, {})
		},
		roomsLookup() {
			if (!this.resolvedSchedule) return {}
			return (this.resolvedSchedule.rooms || []).reduce((acc, r) => { acc[r.id] = r; return acc }, {})
		},
		speakersLookup() {
			if (!this.resolvedSchedule) return {}
			return (this.resolvedSchedule.speakers || []).reduce((acc, s) => { acc[s.code] = s; return acc }, {})
		},
		enrichedSessions() {
			if (this.sessions) return this.sessions
			if (!this.resolvedSchedule?.talks) return []
			const tz = this.currentTimezone || moment.tz.guess()
			return this.resolvedSchedule.talks
				.filter(t => t.start)
				.map(session => ({
					id: session.code,
					title: session.title,
					abstract: session.abstract,
					description: session.description,
					do_not_record: session.do_not_record,
					start: moment.tz(session.start, tz),
					end: moment.tz(session.end, tz),
					speakers: session.speakers?.map(s => this.speakersLookup[s]),
					track: this.tracksLookup[session.track],
					room: this.roomsLookup[session.room],
					fav_count: session.fav_count,
					tags: session.tags,
					session_type: session.session_type,
					resources: session.resources,
					answers: session.answers
				}))
				.sort((a, b) => a.start.diff(b.start))
		},
		filteredSessions() {
			let sessions = this.enrichedSessions
			if (this.onlyFavs) {
				sessions = sessions.filter(s => this.resolvedFavs.includes(s.id))
			}
			const selectedTracks = this.filterState.tracks.filter(t => t.selected).map(t => t.value)
			const selectedRooms = this.filterState.rooms.filter(r => r.selected).map(r => r.value)
			const selectedTypes = this.filterState.types.filter(t => t.selected).map(t => t.value)
			if (selectedTracks.length) {
				sessions = sessions.filter(s => s.track && selectedTracks.includes(s.track.id))
			}
			if (selectedRooms.length) {
				sessions = sessions.filter(s => s.room && selectedRooms.includes(s.room.id))
			}
			if (selectedTypes.length) {
				sessions = sessions.filter(s => {
					const st = s.session_type
					if (typeof st === 'string') return selectedTypes.includes(st)
					if (typeof st === 'object' && st) return Object.values(st).some(v => selectedTypes.includes(v))
					return false
				})
			}
			return sessions
		},
		computedRooms() {
			if (this.rooms) return this.rooms
			const seen = new Set()
			return this.filteredSessions
				.filter(s => { if (!s.room || seen.has(s.room.id)) return false; seen.add(s.room.id); return true })
				.map(s => s.room)
		},
		computedDays() {
			if (this.days) return this.days
			const days = []
			for (const session of this.filteredSessions) {
				const day = session.start.clone().tz(this.currentTimezone).startOf('day')
				if (!days.find(d => d.valueOf() === day.valueOf())) days.push(day)
			}
			return days.sort((a, b) => a.diff(b))
		},
		filterGroups() {
			return [
				{ refKey: 'track', title: 'Tracks', data: this.filterState.tracks },
				{ refKey: 'room', title: 'Rooms', data: this.filterState.rooms },
				{ refKey: 'session_type', title: 'Types', data: this.filterState.types }
			].filter(g => g.data.length > 0)
		},
		inEventTimezone() {
			if (!this.resolvedSchedule?.talks?.length) return false
			return moment().utcOffset() === moment.tz(this.resolvedSchedule.timezone).utcOffset()
		},
		showGrid() {
			return !this.linearOnly && this.scrollParentWidth > 710
		},
		dateFormat() {
			const dayCount = this.computedDays?.length || 0
			let weekday = this.showGrid ? (dayCount <= 7 ? 'dddd ' : 'ddd ') : ''
			let month = dayCount <= 5 ? 'MMMM' : 'MMM'
			return `${weekday}D ${month}`
		}
	},
	watch: {
		resolvedSchedule: {
			handler(val) {
				if (val) this.buildFilterState()
			},
			immediate: true
		}
	},
	created() {
		this.userTimezone = moment.tz.guess()
		this.currentTimezone = localStorage.getItem('userTimezone') || this.timezone || this.scheduleData?.timezone || this.userTimezone
	},
	mounted() {
		this.onResize()
		this._resizeObserver = new ResizeObserver(() => this.onResize())
		this._resizeObserver.observe(this.$el)
		if (this.computedDays?.length) {
			this.currentDay = this.computedDays[0].format('YYYY-MM-DD')
		}
	},
	beforeUnmount() {
		this._resizeObserver?.disconnect()
	},
	methods: {
		buildFilterState() {
			const schedule = this.resolvedSchedule
			if (!schedule) return
			const lang = localStorage.getItem('userLanguage') || 'en'
			this.filterState.tracks = (schedule.tracks || []).map(t => ({
				value: t.id,
				label: this.getI18nName(t.name, lang),
				color: t.color,
				selected: false
			}))
			this.filterState.rooms = (schedule.rooms || []).map(r => ({
				value: r.id,
				label: this.getI18nName(r.name, lang),
				selected: false
			}))
			const typeSet = new Set()
			const types = []
			for (const talk of (schedule.talks || [])) {
				const st = talk.session_type
				if (!st) continue
				const label = typeof st === 'object' ? (st[lang] || st.en || Object.values(st)[0]) : st
				if (label && !typeSet.has(label)) {
					typeSet.add(label)
					types.push({ value: label, label, selected: false })
				}
			}
			this.filterState.types = types
		},
		getI18nName(name, lang) {
			if (typeof name === 'string') return name
			if (typeof name === 'object' && name) return name[lang] || name.en || Object.values(name)[0] || ''
			return ''
		},
		changeDay(day) {
			const dayStr = day.format ? day.format('YYYY-MM-DD') : day
			if (dayStr === this.currentDay) return
			this.currentDay = dayStr
		},
		setCurrentDay(day) {
			this.changeDay(day)
		},
		dayScrolled(day) {
			const dayStr = day.format ? day.format('YYYY-MM-DD') : day
			this.currentDay = dayStr
		},
		toggleFavs() {
			this.onlyFavs = !this.onlyFavs
			if (this.onlyFavs) this.resetFilters()
		},
		resetAllFilters() {
			this.onlyFavs = false
			this.resetFilters()
		},
		resetFilters() {
			for (const group of Object.values(this.filterState)) {
				for (const item of group) { item.selected = false }
			}
		},
		onFilterChange() {
			this.onlyFavs = false
		},
		saveTimezone() {
			localStorage.setItem('userTimezone', this.currentTimezone)
		},
		onFav(id) {
			if (this.scheduleFav) this.scheduleFav(id)
			this.$emit('fav', id)
		},
		onUnfav(id) {
			if (this.scheduleUnfav) this.scheduleUnfav(id)
			this.$emit('unfav', id)
		},
		onExport(option) {
			if (this.scheduleDoExport) {
				this.scheduleDoExport(option)
			}
			this.$emit('export', option)
		},
		onResize() {
			this.scrollParentWidth = this.$el?.offsetWidth || Infinity
		}
	}
}
</script>

<style lang="stylus">
.c-schedule-view
	display: flex
	flex-direction: column
	min-height: 0
	min-width: 0
	.filter-actions
		display: flex
		flex-wrap: wrap
		align-items: center
		gap: 8px
		padding: 8px 16px
		.checkbox-line
			display: flex
			align-items: center
			gap: 4px
			cursor: pointer
			.filter-checkbox
				accent-color: var(--track-color, var(--clr-primary))
			.checkbox-label
				font-size: 14px
		.fav-toggle, .reset-btn
			border: none
			border-radius: 2px
			height: 32px
			padding: 0 16px
			cursor: pointer
			background: transparent
			font-size: 14px
			&:hover
				background-color: rgba(0, 0, 0, 0.05)
		.fav-toggle.active
			border: 2px solid #f9a557
		.timezone-area
			margin-left: auto
			.timezone-select
				height: 32px
				border-radius: 2px
				border: 1px solid #ccc
				font-size: 14px
		.timezone-label
			margin-left: auto
			font-size: 14px
			color: $clr-secondary-text-light
			padding: 4px 8px
	.day-tabs
		display: flex
		overflow-x: auto
		background-color: $clr-white
		border-bottom: 1px solid $clr-grey-300
		flex: none
		.day-tab
			flex: none
			border: none
			background: transparent
			padding: 12px 16px
			font-size: 14px
			white-space: nowrap
			cursor: pointer
			border-bottom: 2px solid transparent
			color: $clr-secondary-text-light
			&:hover
				background-color: rgba(0, 0, 0, 0.03)
			&.active
				color: var(--clr-primary, var(--pretalx-clr-primary, #3aa57c))
				border-bottom-color: var(--clr-primary, var(--pretalx-clr-primary, #3aa57c))
				font-weight: 600
	.schedule-content
		flex: 1
		min-height: 0
		overflow: auto
	.schedule-error
		padding: 32px
		text-align: center
		color: $clr-danger
		font-size: 18px
	.schedule-loading
		padding: 32px
		text-align: center
		font-size: 16px
		color: $clr-secondary-text-light

@media (max-width: 480px)
	.c-schedule-view .filter-actions
		flex-direction: column
		align-items: flex-start
</style>

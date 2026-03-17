<template lang="pug">
.c-schedule-view(ref="scheduleRoot")
	template(v-if="scheduleReady")
		schedule-toolbar(
			:version="resolvedMeta.version || ''",
			:isCurrent="resolvedMeta.is_current !== false",
			:changelogUrl="resolvedMeta.changelog_url || ''",
			:currentScheduleUrl="resolvedMeta.current_schedule_url || ''",
			:versions="resolvedMeta.versions || []",
			:filterGroups="filterGroups",
			:showRecordingFilter="showRecordingFilter",
			v-model:recordingFilter="recordingFilter",
			:favsCount="resolvedFavs.length",
			:onlyFavs="onlyFavs",
			:hasActiveFilters="onlyFavs || activeFilterCount > 0 || recordingFilter !== 'all'",
			:inEventTimezone="inEventTimezone",
			v-model:currentTimezone="currentTimezone",
			:scheduleTimezone="resolvedSchedule.timezone",
			:userTimezone="userTimezone",
			:exporters="resolvedExportersList",
			:fullscreenTarget="$refs.scheduleRoot",
			:days="computedDays",
			:currentDay="currentDay",
			:sessionsMode="sessionsMode",
			:density="density",
			v-model:searchQuery="searchQuery",
			:sortOptions="sortOptions",
			v-model:sortBy="internalSortBy",
			@selectDay="changeDay($event)",
			@filterToggle="onFilterChange",
			@toggleFavs="toggleFavs",
			@resetFilters="resetAllFilters",
			@saveTimezone="saveTimezone",
			@toggleSessionsMode="sessionsMode = !sessionsMode",
			@setDensity="setDensity")
		.schedule-content(ref="scrollParent")
			grid-schedule-wrapper(v-if="showGrid && !sessionsMode",
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
				:showFavCount="showFavCountOnCalendar",
				:density="density",
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
				:showFavCount="showFavCountOnList",
				:sortBy="effectiveSortBy",
				:showBreaks="!linearOnly && !sessionsMode",
				:density="density",
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
import ScheduleToolbar from './ScheduleToolbar'
import { getLocalizedString, getSessionTypeLabel, isProperSession } from '../utils'

function normalizeLocaleCode (code) {
	if (!code) return ''
	return code.toString().trim().toLowerCase().replace(/_/g, '-')
}

function localePrimary (code) {
	const normalized = normalizeLocaleCode(code)
	return normalized.split('-')[0] || normalized
}

function localesMatch (filterValue, sessionValue) {
	const a = normalizeLocaleCode(filterValue)
	const b = normalizeLocaleCode(sessionValue)
	if (!a || !b) return false
	if (a === b) return true
	return localePrimary(a) === localePrimary(b)
}

export default {
	name: 'ScheduleView',
	components: { LinearSchedule, GridScheduleWrapper, ScheduleToolbar },
	inject: {
		scheduleData: { default: null },
		scheduleFav: { default: null },
		scheduleUnfav: { default: null },
		loggedIn: { default: false },
		scheduleExporters: { default: () => [] },
		scheduleMetaData: { default: () => ({}) }
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
		exporters: {
			type: Array,
			default: () => []
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
			sessionsMode: this.linearOnly,
			searchQuery: '',
			recordingFilter: 'all',
			density: localStorage.getItem('schedule-density') || 'default',
			internalSortBy: this.sortBy || 'room',
			filterState: {
				tracks: [],
				rooms: [],
				types: [],
				languages: []
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
		activeFilterCount() {
			return Object.values(this.filterState)
				.reduce((sum, group) => sum + group.filter(i => i.selected).length, 0)
		},
		resolvedExportersList() {
			// Prefer prop, then injected exporters from provider
			if (this.exporters && this.exporters.length) return this.exporters
			const injected = this.scheduleExporters
			return (injected && injected.length) ? injected : []
		},
		resolvedMeta() {
			return this.scheduleMetaData || {}
		},
		scheduleReady() {
			return !!(this.resolvedSchedule && this.enrichedSessions.length)
		},
		showFavCountOnCalendar() {
			const flags = this.scheduleData?.schedule?.feature_flags || {}
			return !!(this.loggedIn && flags.session_popularity_enabled && flags.session_popularity_show_on_calendar)
		},
		showFavCountOnList() {
			const flags = this.scheduleData?.schedule?.feature_flags || {}
			return !!(this.loggedIn && flags.session_popularity_enabled && flags.session_popularity_show_on_list)
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
					answers: session.answers,
					exporters: session.exporters,
					recording_iframe: session.recording_iframe,
					content_locale: session.content_locale || null,
					stream_url: session.stream_url || null,
					stream_type: session.stream_type || null,
				}))
				.sort((a, b) => a.start.diff(b.start))
		},
		showRecordingFilter() {
			const sessions = this.enrichedSessions || []
			let hasRecorded = false
			let hasNotRecorded = false
			for (const s of sessions) {
				if (s?.do_not_record === true) hasNotRecorded = true
				else if (s?.do_not_record === false) hasRecorded = true
				if (hasRecorded && hasNotRecorded) return true
			}
			return false
		},
		filteredSessions() {
			let sessions = this.enrichedSessions
			// In linear-only (sessions) mode, filter out breaks
			if (this.linearOnly || this.sessionsMode) {
				sessions = sessions.filter(s => isProperSession(s))
			}
			if (this.onlyFavs) {
				sessions = sessions.filter(s => this.resolvedFavs.includes(s.id))
			}
			if (this.showRecordingFilter) {
				if (this.recordingFilter === 'yes') {
					sessions = sessions.filter(s => s?.do_not_record === false)
				} else if (this.recordingFilter === 'no') {
					sessions = sessions.filter(s => s?.do_not_record === true)
				}
			}
			const selectedTracks = this.filterState.tracks.filter(t => t.selected).map(t => t.value)
			const selectedRooms = this.filterState.rooms.filter(r => r.selected).map(r => r.value)
			const selectedTypes = this.filterState.types.filter(t => t.selected).map(t => t.value)
			const selectedLanguages = this.filterState.languages.filter(l => l.selected).map(l => l.value)
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
			if (selectedLanguages.length) {
				const fallbackLocale = this.resolvedSchedule?.content_locales?.[0] || null
				sessions = sessions.filter(s => {
					const sessionLocale = s.content_locale || fallbackLocale
					if (!sessionLocale) return false
					return selectedLanguages.some(sel => localesMatch(sel, sessionLocale))
				})
			}
			if (this.searchQuery) {
				const q = this.searchQuery.toLowerCase()
				sessions = sessions.filter(s => {
					const title = (getLocalizedString(s.title) || '').toLowerCase()
					const abstract = (getLocalizedString(s.abstract) || '').toLowerCase()
					const description = (getLocalizedString(s.description) || '').toLowerCase()
					const speakers = (s.speakers || []).map(sp => (sp?.name || '').toLowerCase()).join(' ')
					const track = (getLocalizedString(s.track?.name) || '').toLowerCase()
					const room = (getLocalizedString(s.room?.name) || '').toLowerCase()
					const tags = (s.tags || [])
						.map(t => (t?.tag || t?.name || '').toLowerCase())
						.join(' ')
					return [title, abstract, description, speakers, track, room, tags].some(f => f.includes(q))
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
			const groups = [
				{ refKey: 'track', title: 'Tracks', data: this.filterState.tracks },
				{ refKey: 'room', title: 'Rooms', data: this.filterState.rooms },
				{ refKey: 'session_type', title: 'Types', data: this.filterState.types }
			]
			if (this.filterState.languages.length > 1) {
				groups.push({ refKey: 'language', title: 'Language', data: this.filterState.languages })
			}
			return groups
		},
		inEventTimezone() {
			if (!this.resolvedSchedule?.talks?.length) return false
			const firstTalk = this.resolvedSchedule.talks[0]
			const eventTz = this.resolvedSchedule.timezone
			if (!firstTalk || !eventTz || !firstTalk.start) return false
			const reference = firstTalk.start
			const userTz = this.currentTimezone || moment.tz.guess()
			return moment.tz(reference, userTz).utcOffset() === moment.tz(reference, eventTz).utcOffset()
		},
		showGrid() {
			return !this.linearOnly && this.scrollParentWidth > 710
		},
		popularityFeatureEnabled() {
			return !!this.resolvedSchedule?.feature_flags?.session_popularity_enabled
		},
		sortOptions() {
			const options = ['room', 'title', 'title_desc']
			if (this.loggedIn && this.popularityFeatureEnabled) options.push('popularity')
			return options
		},
		effectiveSortBy() {
			return this.sortOptions.includes(this.internalSortBy) ? this.internalSortBy : 'room'
		}
	},
	watch: {
		recordingFilter() {
			this.writeRecordingQueryParam()
		},
		sortBy: {
			handler(val) {
				if (val && val !== this.internalSortBy) this.internalSortBy = val
			},
			immediate: true
		},
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
		this.readRecordingQueryParam()
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
		setDensity(density) {
			this.density = density
			try {
				localStorage.setItem('schedule-density', density)
			} catch {
				// ignore localStorage access errors
			}
		},
		readRecordingQueryParam() {
			try {
				const url = new URL(window.location.href)
				const value = url.searchParams.get('recording')
				if (value === 'yes' || value === 'no' || value === 'all') {
					this.recordingFilter = value
				}
			} catch {
				// ignore invalid URL contexts (e.g. non-browser env)
			}
		},
		writeRecordingQueryParam() {
			try {
				const url = new URL(window.location.href)
				const value = (this.recordingFilter === 'yes' || this.recordingFilter === 'no' || this.recordingFilter === 'all')
					? this.recordingFilter
					: 'all'
				url.searchParams.set('recording', value)
				window.history.replaceState({}, '', url.pathname + url.search + url.hash)
			} catch {
				// ignore invalid URL contexts
			}
		},
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
				const label = getSessionTypeLabel(st)
				if (label && !typeSet.has(label)) {
					typeSet.add(label)
					types.push({ value: label, label, selected: false })
				}
			}
			this.filterState.types = types
			// Build language filter from event content_locales (configured by organiser),
			// falling back to per-talk content_locale for older data.
			const langSet = new Set()
			const languages = []
			const eventLocales = schedule.content_locales || []
			for (const code of eventLocales) {
				if (!code || langSet.has(code)) continue
				langSet.add(code)
				let displayName = code
				try { displayName = new Intl.DisplayNames([lang], { type: 'language' }).of(code) } catch { /* fallback */ }
				languages.push({ value: code, label: displayName, selected: false })
			}
			// Also include any per-talk locales not already covered by event locales
			for (const talk of (schedule.talks || [])) {
				const locale = talk.content_locale
				if (!locale || langSet.has(locale)) continue
				langSet.add(locale)
				let displayName = locale
				try { displayName = new Intl.DisplayNames([lang], { type: 'language' }).of(locale) } catch { /* fallback to raw locale */ }
				languages.push({ value: locale, label: displayName, selected: false })
			}
			this.filterState.languages = languages
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
			if (!this.loggedIn) return
			this.onlyFavs = !this.onlyFavs
			if (this.onlyFavs) this.resetFilters()
		},
		resetAllFilters() {
			this.onlyFavs = false
			this.resetFilters()
			this.recordingFilter = 'all'
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
			if (!this.loggedIn) return
			if (this.scheduleFav) this.scheduleFav(id)
			this.$emit('fav', id)
		},
		onUnfav(id) {
			if (!this.loggedIn) return
			if (this.scheduleUnfav) this.scheduleUnfav(id)
			this.$emit('unfav', id)
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
	&:fullscreen
		background: #fff
		.c-schedule-toolbar
			border-bottom: 1px solid $clr-dividers-light
			box-shadow: 0 1px 3px rgba(0,0,0,0.08)
	.schedule-content
		flex: 1
		min-height: 0
		overflow: auto
		// The toolbar sits outside this scroll container, so reset
		// the sticky offset to cancel the +40px baked into GridSchedule.
		--pretalx-sticky-top-offset: calc(-30px - var(--pretalx-version-warning-height, 0px))
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

</style>

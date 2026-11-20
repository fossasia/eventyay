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
			:recordingFilter="recordingFilter",
			@update:recordingFilter="onRecordingFilterChange",
			:favsCount="resolvedFavs.length",
			:onlyFavs="onlyFavs",
			v-model:shareStarredSessions="shareStarredSessions",
			:scheduleUserLoggedIn="scheduleUserLoggedIn",
			:hasActiveFilters="onlyFavs || activeFilterCount > 0 || recordingFilter !== 'all' || !!selectedDay",
			v-model:currentTimezone="currentTimezone",
			:scheduleTimezone="resolvedSchedule.timezone",
			:userTimezone="userTimezone",
			:exporters="resolvedExportersList",
			:fullscreenTarget="$refs.scheduleRoot",
			:days="computedDays",
			:currentDay="currentDay",
			:selectedDay="selectedDay",
			:now="resolvedNow",
			:sessionsMode="sessionsMode",
			:timeDensityMinutes="timeDensityMinutes",
			v-model:searchQuery="searchQuery",
			:sortOptions="sortOptions",
			v-model:sortBy="internalSortBy",
			v-model:includeRoomSortKey="sortIncludeRoom",
			v-model:includeDateSortKey="sortIncludeDate",
			v-model:includePopularitySortKey="sortIncludePopularity",
			:popularityFeatureEnabled="popularityFeatureEnabled",
			:popularitySortAvailable="popularitySortAvailable",
			@selectDay="selectDay($event)",
			@goToNow="goToNow",
			@filterToggle="onFilterChange",
			@toggleFavs="toggleFavs",
			@update:shareStarredSessions="updateShareStarredSessions",
			@resetFilters="resetAllFilters",
			@saveTimezone="saveTimezone",
			@toggleSessionsMode="sessionsMode = !sessionsMode",
			@setTimeDensityMinutes="setTimeDensityMinutes($event)")
		.schedule-content(ref="scrollParent")
			grid-schedule-wrapper(v-if="showGrid && !sessionsMode",
				ref="scheduleDisplay",
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
				:showFavCount="showFavCountOnSchedule",
				:density="'default'",
				:timeDensityMinutes="timeDensityMinutes",
				@changeDay="setCurrentDay",
				@fav="onFav",
				@unfav="onUnfav")
			linear-schedule(v-else,
				ref="scheduleDisplay",
				:sessions="filteredSessions",
				:forceScrollDay="forceScrollDay",
				:rooms="computedRooms",
				:currentDay="currentDay",
				:now="resolvedNow",
				:hasAmPm="resolvedHasAmPm",
				:timezone="currentTimezone",
				:locale="locale",
				:scrollParent="$refs.scrollParent",
				:favs="resolvedFavs",
				:showFavCount="showFavCountOnSchedule",
				:sortBy="effectiveSortBy",
				:includeRoomSortKey="sortIncludeRoom",
				:includeDateSortKey="sortIncludeDate || linearScheduleGroupByDay",
				:includePopularitySortKey="sortIncludePopularity",
				:showBreaks="!linearOnly && !sessionsMode",
				:density="'default'",
				@changeDay="dayScrolled",
				@fav="onFav",
				@unfav="onUnfav")
	.schedule-error(v-else-if="hasError")
		| {{ t.load_error }}
	.schedule-empty(v-else-if="isScheduleLoaded")
		| {{ t.no_schedule_available }}
	.schedule-loading(v-else)
		| {{ t.loading }}
</template>

<script>
import moment from 'moment-timezone'
import LinearSchedule from './LinearSchedule'
import GridScheduleWrapper from './GridScheduleWrapper'
import ScheduleToolbar from './ScheduleToolbar'
import { getLocalizedString, getSessionTypeLabel, isProperSession, isPopularityFeatureEnabled, isPopularitySortAvailable, isPopularityVisibleOnSchedule, normalizePopularityCount, serializeScheduleFiltersToUrl, parseScheduleFiltersFromUrl, normalizeLocaleCode, localePrimary, localesMatch } from '../utils'
import { getLanguageNativeLabel } from '../../../i18n/index.js'


export default {
	name: 'ScheduleView',
	components: { LinearSchedule, GridScheduleWrapper, ScheduleToolbar },
	inject: {
		scheduleData: { default: null },
		scheduleFav: { default: null },
		scheduleUnfav: { default: null },
		scheduleExporters: { default: () => [] },
		scheduleMetaData: { default: () => ({}) },
		scheduleUserLoggedIn: { default: false },
		loadStarredSharingPreference: { default: null },
		updateStarredSharingPreference: { default: null },
		onSaveTimezone: { default: null },
		translationMessages: { default: () => ({}) },
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
		scheduleLoaded: Boolean,
		linearOnly: {
			type: Boolean,
			default: false
		},
		sortBy: {
			type: String,
			default: 'title'
		},
		exporters: {
			type: Array,
			default: () => []
		}
	},
	emits: ['fav', 'unfav', 'export'],
	data() {
		const userTz = moment.tz.guess()
		let initialTz = userTz
		try {
			initialTz = localStorage.getItem('userTimezone') || this.timezone || this.scheduleData?.timezone || userTz
		} catch {
			initialTz = this.timezone || this.scheduleData?.timezone || userTz
		}
		return {
			currentDay: null,
			selectedDay: null,
			_isApplyingUrlFilters: false,
			onlyFavs: false,
			shareStarredSessions: false,
			scrollParentWidth: Infinity,
			currentTimezone: initialTz,
			userTimezone: userTz,
			sessionsMode: this.linearOnly,
			searchQuery: '',
			recordingFilter: 'all',
			timeDensityMinutes: (() => {
				try {
					return Number(localStorage.getItem('schedule-time-density-minutes') || 30)
				} catch (error) {
					console.error('Failed to read schedule time density from localStorage', error)
					return 30
				}
			})(),
			internalSortBy: this.sortBy || 'title',
			sortIncludeRoom: false,
			sortIncludeDate: (() => {
				try {
					const stored = localStorage.getItem('schedule-include-datetime')
					if (stored === null) return true
					return stored === 'true'
				} catch (error) {
					console.error('Failed to read schedule date-sort preference from localStorage', error)
					return true
				}
			})(),
			sortIncludePopularity: false,
			forceScrollDay: 0,
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
		isScheduleLoaded() {
			return !!(this.scheduleLoaded || this.scheduleData?.scheduleLoaded)
		},
		t() {
			const m = this.translationMessages || {}
			return {
				no_schedule_available: m.no_schedule_available || this.$t('No schedule has been published yet. Please check back later.'),
				load_error: m.load_error || this.$t('An error occurred while loading the schedule.'),
				loading: m.loading || this.$t('Loading…'),
			}
		},
		showFavCountOnSchedule() {
			const flags = this.scheduleData?.schedule?.feature_flags || this.resolvedSchedule?.feature_flags || {}
			return isPopularityVisibleOnSchedule({ flags })
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
			if (this.scheduleData?.sessions) return this.scheduleData.sessions
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
					fav_count: normalizePopularityCount(session),
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
				const favSet = new Set(this.resolvedFavs)
				sessions = sessions.filter(s => favSet.has(s.id))
			}
			if (this.showRecordingFilter) {
				if (this.recordingFilter === 'yes') {
					sessions = sessions.filter(s => s?.do_not_record === false)
				} else if (this.recordingFilter === 'no') {
					sessions = sessions.filter(s => s?.do_not_record === true)
				}
			}
			const selectedTracks = new Set(this.filterState.tracks.filter(t => t.selected).map(t => t.value))
			const selectedRooms = new Set(this.filterState.rooms.filter(r => r.selected).map(r => r.value))
			const selectedTypes = new Set(this.filterState.types.filter(t => t.selected).map(t => t.value))
			const selectedLanguages = this.filterState.languages.filter(l => l.selected).map(l => l.value)
			if (selectedTracks.size) {
				sessions = sessions.filter(s => s.track && selectedTracks.has(s.track.id))
			}
			if (selectedRooms.size) {
				sessions = sessions.filter(s => s.room && selectedRooms.has(s.room.id))
			}
			if (selectedTypes.size) {
				sessions = sessions.filter(s => {
					const st = s.session_type
					if (typeof st === 'string') return selectedTypes.has(st)
					if (typeof st === 'object' && st) {
						for (const v of Object.values(st)) {
							if (selectedTypes.has(v)) return true
						}
						return false
					}
					return false
				})
			}
			if (selectedLanguages.length) {
				const fallbackLocale = this.resolvedSchedule?.content_locales?.[0] || null
				sessions = sessions.filter(s => {
					const sessionLocale = s.content_locale || fallbackLocale
					if (!sessionLocale) return false
					for (const sel of selectedLanguages) {
						if (localesMatch(sel, sessionLocale)) return true
					}
					return false
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
			if (this.selectedDay) {
				sessions = sessions.filter(s => s.start && s.start.clone().tz(this.currentTimezone).format('YYYY-MM-DD') === this.selectedDay)
			}
			return sessions
		},
		computedRooms() {
			if (this.rooms) return this.rooms
			const orderSource = this.scheduleData?.rooms || this.resolvedSchedule?.rooms
			if (orderSource?.length) {
				const roomsInSessions = new Map()
				for (const session of this.enrichedSessions) {
					if (!session.room) continue
					const key = session.room.pretalx_id ?? session.room.id
					if (!roomsInSessions.has(key)) roomsInSessions.set(key, session.room)
				}
				return orderSource
					.filter(room => roomsInSessions.has(room.pretalx_id ?? room.id))
					.map(room => roomsInSessions.get(room.pretalx_id ?? room.id))
			}
			const seen = new Set()
			return this.filteredSessions
				.filter(s => { if (!s.room || seen.has(s.room.id)) return false; seen.add(s.room.id); return true })
				.map(s => s.room)
		},
		allScheduleDays() {
			if (this.days) return this.days
			const days = []
			const seen = new Set()
			const sourceSessions = this.enrichedSessions.length ? this.enrichedSessions : this.filteredSessions
			const tz = this.currentTimezone || moment.tz.guess()
			for (const session of sourceSessions) {
				if (!session.start) continue
				const day = session.start.clone().tz(tz).startOf('day')
				const key = day.valueOf()
				if (!seen.has(key)) {
					seen.add(key)
					days.push(day)
				}
			}
			return days.sort((a, b) => a.diff(b))
		},
		computedDays() {
			const sortedDays = this.allScheduleDays
			if ((this.linearOnly || this.sessionsMode) && !this.sortIncludeDate && ['title', 'title_desc'].includes(this.effectiveSortBy)) {
				return sortedDays.length ? [sortedDays[0]] : []
			}
			return sortedDays
		},
		filterGroups() {
			const groups = [
				{ refKey: 'track', title: this.$t('Tracks'), data: this.filterState.tracks },
				{ refKey: 'room', title: this.$t('Rooms'), data: this.filterState.rooms },
				{ refKey: 'session_type', title: this.$t('Types'), data: this.filterState.types }
			]
			if (this.filterState.languages.length > 1) {
				groups.push({ refKey: 'language', title: this.$t('Language'), data: this.filterState.languages })
			}
			return groups
		},
		showGrid() {
			return !this.linearOnly && this.scrollParentWidth > 710
		},
		linearScheduleGroupByDay() {
			return !this.showGrid && this.computedDays.length > 1
		},
		popularityFeatureEnabled() {
			const flags = this.resolvedSchedule?.feature_flags || {}
			return isPopularityFeatureEnabled(flags)
		},
		popularitySortAvailable() {
			const flags = this.resolvedSchedule?.feature_flags || {}
			return isPopularitySortAvailable({ flags })
		},
		sortOptions() {
			const options = ['title', 'title_desc']
			if (this.popularitySortAvailable) options.push('popularity')
			return options
		},
		effectiveSortBy() {
			return this.sortOptions.includes(this.internalSortBy) ? this.internalSortBy : 'title'
		}
	},
	watch: {
		sortIncludeDate() {
			try {
				localStorage.setItem('schedule-include-datetime', String(this.sortIncludeDate))
			} catch {
				// ignore localStorage access errors
			}
		},
		sortBy: {
			handler(val) {
				if (val && val !== this.internalSortBy) this.internalSortBy = val
			},
			immediate: true
		},
		popularitySortAvailable(enabled) {
			if (!enabled) {
				this.sortIncludePopularity = false
				if (this.internalSortBy === 'popularity') this.internalSortBy = 'title'
			}
		},
		popularityFeatureEnabled(enabled) {
			if (!enabled) {
				this.sortIncludePopularity = false
				if (this.internalSortBy === 'popularity') this.internalSortBy = 'title'
			}
		},
		resolvedSchedule: {
			handler(val) {
				if (val) this.buildFilterState()
			},
			immediate: true
		}
	},
	created() {
		this.userTimezone = this.userTimezone || moment.tz.guess()
		this.currentTimezone = this.currentTimezone || localStorage.getItem('userTimezone') || this.timezone || this.scheduleData?.timezone || this.userTimezone
		if (this.allScheduleDays?.length) {
			const today = this.resolvedNow.clone().tz(this.currentTimezone).format('YYYY-MM-DD')
			const fragment = window.location.hash.slice(1)
			const fragmentDay = /^\d{4}-\d{2}-\d{2}$/.test(fragment) && this.allScheduleDays.some(day => day.format('YYYY-MM-DD') === fragment)
				? fragment
				: null
			const todayExists = this.allScheduleDays.some(day => day.format('YYYY-MM-DD') === today)
			this.currentDay = fragmentDay || (todayExists ? today : this.allScheduleDays[0].format('YYYY-MM-DD'))
		}
	},
	mounted() {
		this.onResize()
		this._resizeObserver = new ResizeObserver(() => this.onResize())
		this._resizeObserver.observe(this.$el)
		this._onPopState = () => this.readFiltersFromUrl()
		window.addEventListener('popstate', this._onPopState)
		if (this.loadStarredSharingPreference) {
			this.loadStarredSharingPreference().then((enabled) => {
				this.shareStarredSessions = !!enabled
			})
		}
	},
	beforeUnmount() {
		if (this._onPopState) {
			window.removeEventListener('popstate', this._onPopState)
			this._onPopState = null
		}
		this._resizeObserver?.disconnect()
	},
	methods: {
		setTimeDensityMinutes(minutes) {
			const parsedMinutes = Number(minutes)
			const fallbackMinutes = 30
			const validMinutes = Number.isFinite(parsedMinutes) && parsedMinutes > 0 ? parsedMinutes : fallbackMinutes
			this.timeDensityMinutes = validMinutes
			try {
				localStorage.setItem('schedule-time-density-minutes', String(this.timeDensityMinutes))
			} catch {
				// ignore localStorage access errors
			}
		},
		readFiltersFromUrl() {
			this._isApplyingUrlFilters = true
			try {
				const result = parseScheduleFiltersFromUrl(window.location.href, {
					allTracks: this.filterState.tracks,
					allRooms: this.filterState.rooms,
					allTypes: this.filterState.types,
					allLanguages: this.filterState.languages,
					availableDays: this.allScheduleDays,
				})
				this.recordingFilter = result.recordingFilter
				if (result.selectedDay) {
					this.selectedDay = result.selectedDay
					this.currentDay = result.selectedDay
				} else {
					this.selectedDay = null
					const fragment = window.location.hash.slice(1)
					const daysList = this.allScheduleDays || []
					if (/^\d{4}-\d{2}-\d{2}$/.test(fragment) && daysList.some(day => day.format('YYYY-MM-DD') === fragment)) {
						this.currentDay = fragment
					}
				}
			} catch (error) {
				console.error('Failed to parse schedule filters from URL', error)
			} finally {
				this._isApplyingUrlFilters = false
			}
		},
		writeFiltersToUrl({ pushState = false } = {}) {
			if (this._isApplyingUrlFilters) return
			try {
				const newUrl = serializeScheduleFiltersToUrl(window.location.href, {
					filteredTracks: this.filterState.tracks.filter(t => t.selected),
					filteredRooms: this.filterState.rooms.filter(r => r.selected),
					filteredTypes: this.filterState.types.filter(t => t.selected),
					filteredLanguages: this.filterState.languages.filter(l => l.selected),
					allTracks: this.filterState.tracks,
					allRooms: this.filterState.rooms,
					allTypes: this.filterState.types,
					selectedDay: this.selectedDay,
					recordingFilter: this.recordingFilter,
				})
				const currentRelative = window.location.pathname + window.location.search + window.location.hash
				if (newUrl !== currentRelative) {
					if (pushState) window.history.pushState({}, '', newUrl)
					else window.history.replaceState({}, '', newUrl)
				}
			} catch (error) {
				console.error('Failed to update schedule filters in URL', error)
			}
		},
		buildFilterState() {
			const schedule = this.resolvedSchedule
			if (!schedule) return
			const lang = localStorage.getItem('userLanguage') || 'en'
			this.filterState.tracks = (schedule.tracks || []).map(t => ({
				id: t.id,
				value: t.id,
				name: t.name,
				label: this.getI18nName(t.name, lang),
				color: t.color,
				selected: false
			}))
			this.filterState.rooms = (schedule.rooms || []).map(r => ({
				id: r.id,
				value: r.id,
				name: r.name,
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
					types.push({ value: label, label, raw: st, selected: false })
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
				const displayName = getLanguageNativeLabel(code) || code
				languages.push({ value: code, label: displayName, selected: false })
			}
			// Also include any per-talk locales not already covered by event locales
			for (const talk of (schedule.talks || [])) {
				const locale = talk.content_locale
				if (!locale || langSet.has(locale)) continue
				langSet.add(locale)
				const displayName = getLanguageNativeLabel(locale) || locale
				languages.push({ value: locale, label: displayName, selected: false })
			}
			this.filterState.languages = languages
			this.readFiltersFromUrl()
		},
		getI18nName(name, lang) {
			if (typeof name === 'string') return name
			if (typeof name === 'object' && name) return name[lang] || name.en || Object.values(name)[0] || ''
			return ''
		},
		selectDay(day) {
			const dayStr = day?.format ? day.format('YYYY-MM-DD') : (day ? String(day) : null)
			if (!dayStr) return
			const isToggleOff = this.selectedDay === dayStr
			if (isToggleOff) {
				this.selectedDay = null
			} else {
				this.selectedDay = dayStr
				this.currentDay = dayStr
			}
			this.writeFiltersToUrl({ pushState: true })
			if (this.linearScheduleGroupByDay) {
				this.forceScrollDay++
			}
		},
		changeDay(day) {
			this.setCurrentDay(day)
			if (this.linearScheduleGroupByDay) {
				this.forceScrollDay++
			}
		},
		setCurrentDay(day) {
			if (this.selectedDay) return
			const dayStr = day?.format ? day.format('YYYY-MM-DD') : (day ? String(day) : null)
			if (!dayStr || dayStr === this.currentDay) return
			this.currentDay = dayStr
			try {
				const hashUrl = window.location.pathname + window.location.search + '#' + dayStr
				window.history.replaceState(null, null, hashUrl)
			} catch (e) {
				window.location.hash = dayStr
			}
		},
		dayScrolled(day) {
			this.setCurrentDay(day)
		},
		goToNow() {
			const today = this.resolvedNow.clone().tz(this.currentTimezone).format('YYYY-MM-DD')
			const todayExists = this.computedDays.some(day => day.format('YYYY-MM-DD') === today)
			if (!todayExists) return
			if (this.selectedDay && this.selectedDay !== today) {
				this.selectedDay = today
				this.writeFiltersToUrl({ pushState: true })
			}
			this.setCurrentDay(today)
			if (this.linearScheduleGroupByDay) {
				this.forceScrollDay++
			}
			this.$nextTick(() => {
				this.$refs.scheduleDisplay?.scrollToNow?.()
			})
		},
		toggleFavs() {
			this.onlyFavs = !this.onlyFavs
			if (this.onlyFavs) {
				this.resetFilters()
				this.writeFiltersToUrl({ pushState: true })
			}
		},
		async updateShareStarredSessions(value) {
			const previous = this.shareStarredSessions
			this.shareStarredSessions = !!value
			if (!this.updateStarredSharingPreference) return
			try {
				const enabled = await this.updateStarredSharingPreference(this.shareStarredSessions)
				this.shareStarredSessions = !!enabled
			} catch {
				this.shareStarredSessions = previous
			}
		},
		resetAllFilters() {
			this.onlyFavs = false
			this.resetFilters()
			this.recordingFilter = 'all'
			this.selectedDay = null
			this.writeFiltersToUrl({ pushState: true })
		},
		resetFilters() {
			for (const group of Object.values(this.filterState)) {
				for (const item of group) { item.selected = false }
			}
		},
		onFilterChange() {
			this.onlyFavs = false
			this.writeFiltersToUrl({ pushState: true })
		},
		onRecordingFilterChange(value) {
			this.recordingFilter = value
			this.onlyFavs = false
			this.writeFiltersToUrl({ pushState: true })
		},
		saveTimezone() {
			localStorage.setItem('userTimezone', this.currentTimezone)
			if (this.onSaveTimezone) {
				this.onSaveTimezone(this.currentTimezone)
			}
		},
		onFav(id) {
			if (this.scheduleFav) this.scheduleFav(id)
			this.$emit('fav', id)
		},
		onUnfav(id) {
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
	font-size: 14px
	color: rgb(13, 15, 16)
	--pretalx-clr-text: rgb(13, 15, 16)
	overflow: hidden
	&:fullscreen
		background: #fff
		padding: 0 8px
		@media (max-width: 768px)
			padding: 0 6px
		.c-schedule-toolbar
			border-bottom: 1px solid $clr-dividers-light
			box-shadow: 0 1px 3px rgba(0,0,0,0.08)
	.schedule-content
		flex: 1
		min-height: 0
		overflow: auto
		// The toolbar sits outside this scroll container, so reset
		// the sticky offset to cancel the +40px baked into GridSchedule.
		--pretalx-sticky-top-offset: calc(-40px - var(--pretalx-version-warning-height, 0px))
	.schedule-error
		padding: 32px
		text-align: center
		color: $clr-danger
		font-size: 18px
	.schedule-empty
		padding: 32px
		text-align: center
		font-size: 16px
		color: $clr-secondary-text-light
	.schedule-loading
		padding: 32px
		text-align: center
		font-size: 16px
		color: $clr-secondary-text-light

</style>

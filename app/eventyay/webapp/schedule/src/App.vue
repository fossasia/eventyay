<template lang="pug">
.pretalx-schedule(:style="{'--scrollparent-width': scrollParentWidth + 'px', '--schedule-max-width': scheduleMaxWidth + 'px', '--pretalx-sticky-date-offset': '0px'}", :class="isSpeakerView ? ['speaker-view'] : isTalkView ? ['talk-view'] : sessionsMode ? ['sessions-view', 'list-schedule'] : showGrid ? ['grid-schedule'] : ['list-schedule']")
	template(v-if="scheduleError")
		.schedule-error
			.error-message An error occurred while loading the schedule. Please try again later.
	template(v-else-if="isTalkView && schedule && resolvedTalk")
		talk-detail(:talk="resolvedTalk", :baseUrl="eventUrl")
	template(v-else-if="isSpeakerView && schedule")
		featured-speakers(v-if="view === 'featured-speakers'")
		speakers-list(v-else-if="view === 'speakers'")
		speaker-detail(v-else-if="view === 'speaker'", :speakerId="speakerCode", :onHomeServer="onHomeServer")
	template(v-else-if="schedule && schedule.talks.length")
		schedule-toolbar(v-if="(scheduleMeta || schedule) && !publicFavsUrl",
			:version="scheduleMeta?.version || ''",
			:isCurrent="scheduleMeta?.is_current !== false",
			:changelogUrl="scheduleMeta?.changelog_url || ''",
			:currentScheduleUrl="scheduleMeta?.current_schedule_url || ''",
			:exporters="scheduleMeta?.exporters || []",
			:versions="scheduleMeta?.versions || []",
			:fullscreenTarget="$el",
			:filterGroups="filterGroups",
			:showRecordingFilter="showRecordingFilter",
			v-model:recordingFilter="recordingFilter",
			:sortOptions="sortOptions",
			v-model:sortBy="sortBy",
			:favsCount="favs.length",
			:onlyFavs="onlyFavs",
			:hasActiveFilters="onlyFavs || hasActiveFilterSelections || recordingFilter !== 'all'",
			:inEventTimezone="inEventTimezone",
			v-model:currentTimezone="currentTimezone",
			:scheduleTimezone="schedule.timezone",
			:userTimezone="userTimezone",
			:days="days",
			:currentDay="currentDay",
			:sessionsMode="sessionsMode",
			v-model:searchQuery="searchQuery",
			@selectDay="selectDay($event)",
			@filterToggle="onlyFavs = false",
			@toggleFavs="onlyFavs = !onlyFavs; if (onlyFavs) resetAllFilters()",
			@resetFilters="onlyFavs = false; resetAllFilters()",
			@saveTimezone="saveTimezone",
			@toggleSessionsMode="sessionsMode = !sessionsMode")
		grid-schedule-wrapper(v-if="showGrid && !sessionsMode",
			:sessions="sessions",
			:rooms="rooms",
			:days="days",
			:currentDay="currentDay",
			:now="now",
			:hasAmPm="hasAmPm",
			:timezone="currentTimezone",
			:locale="locale",
			:scrollParent="scrollParent",
			:favs="favs",
			:showFavCount="showPopularityOnCalendar",
			:onHomeServer="onHomeServer",
			:disableAutoScroll="disableAutoScroll",
			:forceScrollDay="forceScrollDay",
			@changeDay="setCurrentDay($event)",
			@fav="fav($event)",
			@unfav="unfav($event)")
		linear-schedule(v-else,
			:sessions="sessionsMode ? properSessions : sessions",
			:rooms="rooms",
			:currentDay="currentDay",
			:now="now",
			:hasAmPm="hasAmPm",
			:timezone="currentTimezone",
			:locale="locale",
			:scrollParent="scrollParent",
			:favs="favs",
			:showFavCount="showPopularityOnList",
			:sortBy="effectiveSortBy",
			:onHomeServer="onHomeServer",
			:disableAutoScroll="disableAutoScroll",
			:showBreaks="!sessionsMode",
			@changeDay="setCurrentDay($event)",
			@fav="fav($event)",
			@unfav="unfav($event)")
		.no-results(v-if="sessions && !sessions.length && searchQuery")
			.no-results-text No sessions match your search.
	bunt-progress-circular(v-else, size="huge", :page="true")
	.error-messages(v-if="errorMessages.length")
		.error-message(v-for="message in errorMessages", :key="message")
			.btn.btn-danger(@click="errorMessages = errorMessages.filter(m => m !== message)") x
			div.message {{ message }}
	#bunt-teleport-target(ref="teleportTarget")
	session-modal(
		ref="sessionModal",
		:modalContent="modalContent",
		:currentTimezone="currentTimezone",
		:locale="locale",
		:hasAmPm="hasAmPm",
		:now="now",
		:onHomeServer="onHomeServer",
		:favs="favs",
		:showJoinRoom="showJoinRoom",
		@toggleFav="toggleSessionModalFav",
		@showSpeaker="showSpeakerDetails",
		@fav="fav($event)",
		@unfav="unfav($event)"
	)
</template>
<script>
import { computed } from 'vue'
import moment from 'moment-timezone'
import MarkdownIt from 'markdown-it'
import ScheduleToolbar from '~/components/ScheduleToolbar'
import LinearSchedule from '~/components/LinearSchedule'
import GridScheduleWrapper from '~/components/GridScheduleWrapper'
import FavButton from '~/components/FavButton'
import Session from '~/components/Session'
import SessionModal from '~/components/SessionModal'
import SpeakersList from '~/components/SpeakersList'
import FeaturedSpeakers from '~/components/FeaturedSpeakers'
import SpeakerDetail from '~/components/SpeakerDetail'
import TalkDetail from '~/components/TalkDetail'
import { findScrollParent, getLocalizedString, getSessionTime, isProperSession } from '~/utils'

function getCsrfToken () {
	const match = document.cookie.match(/eventyay_csrftoken=([^;]+)/)
	return match ? match[1] : ''
}

const markdownIt = MarkdownIt({
	linkify: false,
	breaks: true
})

export default {
	name: 'PretalxSchedule',
	components: { FavButton, LinearSchedule, GridScheduleWrapper, Session, SessionModal, ScheduleToolbar, SpeakersList, FeaturedSpeakers, SpeakerDetail, TalkDetail },
	props: {
		eventUrl: String,
		locale: String,
		format: {
			type: String,
			default: 'grid'
		},
		version: {
			type: String,
			default: ''
		},
		// View mode: 'schedule' (default), 'speakers' (list), 'speaker' (detail), 'talk' (single talk), 'sessions' (sessions only, no breaks)
		view: {
			type: String,
			default: 'schedule'
		},
		// Speaker code, used when view === 'speaker'
		speakerCode: {
			type: String,
			default: ''
		},
		// Talk/submission code, used when view === 'talk'
		talkCode: {
			type: String,
			default: ''
		},
		// URL returning an array of favourited talk codes for public display
		publicFavsUrl: {
			type: String,
			default: ''
		},
		// List the dates that should be displayed, as comma-separated ISO strings
		dateFilter: {
			type: String,
			default: ''
		},
		// Disable auto-scroll to current time on page load
		disableAutoScroll: {
			type: Boolean,
			default: false
		},
		// Show join-room button on sessions (video feature, available on agenda too)
		showJoinRoom: {
			type: Boolean,
			default: true
		},
		// Base URL for video room join links (e.g. /org/event/video/rooms/)
		joinRoomBaseUrl: {
			type: String,
			default: ''
		}
	},
	provide () {
		return {
			eventUrl: this.eventUrl,
			remoteApiUrl: computed(() => this.remoteApiUrl),
			buntTeleportTarget: computed(() => this.$refs.teleportTarget),
			onSessionLinkClick: (event, session) => {
				if (this.onHomeServer) return
				event.preventDefault()

				this.showSessionDetails(session, event)
			},
			scheduleFav: (id) => this.fav(id),
			scheduleUnfav: (id) => this.unfav(id),
			scheduleData: computed(() => ({
				schedule: this.schedule,
				sessions: this.sessions || [],
				favs: this.favs,
				timezone: this.currentTimezone,
				now: this.now,
				hasAmPm: this.hasAmPm,
			})),
			showJoinRoom: computed(() => this.showJoinRoom),
			getJoinRoomLink: (session) => {
				if (!this.showJoinRoom) return ''
				const base = this.joinRoomBaseUrl || (session?.stream_url ? this.defaultJoinRoomBaseUrl : '')
				if (!base || !session?.room) return ''
				const roomId = typeof session.room === 'object' ? session.room.id : session.room
				return roomId ? `${base}${roomId}/` : ''
			},
			generateSpeakerLinkUrl: ({speaker}) => {
				if (this.onHomeServer) return `${this.eventUrl}speakers/${speaker.code}/`
				return `#speakers/${speaker.code}`
			},
			onSpeakerLinkClick: (event, speaker) => {
				if (!this.onHomeServer) {
					event.preventDefault()
					this.showSpeakerDetails(speaker, event)
				}
			},
			translationMessages: computed(() => this.translationMessages)
		}
	},
	data () {
		return {
			getLocalizedString,
			getSessionTime,
			markdownIt,
			sortBy: 'room',
			scrollParentWidth: Infinity,
			schedule: null,
			userTimezone: null,
			now: moment(),
			currentDay: null,
			forceScrollDay: 0,
			currentTimezone: null,
			favs: [],
			favsReadOnly: false,
			allTracks: [],
			allRooms: [],
			allTypes: [],
			allLanguages: [],
			onlyFavs: false,
			scheduleError: false,
			onHomeServer: false,
			loggedIn: false,
			apiUrl: null,
			translationMessages: {},
			errorMessages: [],
			displayDates: this.dateFilter?.split(',').filter(d => d.length === 10) || [],
			modalContent: null,
			scheduleMeta: null,
			sessionsMode: false,
			searchQuery: '',
			recordingFilter: 'all',
		}
	},
	computed: {
		defaultJoinRoomBaseUrl () {
			if (!this.eventUrl) return ''
			return `${this.eventUrl.replace(/\/$/, '')}/video/rooms/`
		},
		scheduleMaxWidth () {
			return this.schedule ? Math.min(this.scrollParentWidth, 78 + this.schedule.rooms.length * 365) : this.scrollParentWidth
		},
		showGrid () {
			// Changes to the 710px cutoff must also be reflected in the static/agenda/_agenda.css file in pretalx-core
			return this.scrollParentWidth > 710 && this.format !== 'list' // if we can't fit two rooms together, switch to list
		},
		roomsLookup () {
			if (!this.schedule) return {}
			return this.schedule.rooms.reduce((acc, room) => { acc[room.id] = room; return acc }, {})
		},
		tracksLookup () {
			if (!this.schedule) return {}
			return this.schedule.tracks.reduce((acc, t) => { acc[t.id] = t; return acc }, {})
		},
		filteredTracks () {
			return this.allTracks.filter(t => t.selected)
		},
		filteredRooms () {
			return this.allRooms.filter(r => r.selected)
		},
		filteredTypes () {
			return this.allTypes.filter(t => t.selected)
		},
		filteredLanguages () {
			return this.allLanguages.filter(l => l.selected)
		},
		hasActiveFilterSelections () {
			return this.filteredTracks.length > 0 || this.filteredRooms.length > 0 || this.filteredTypes.length > 0 || this.filteredLanguages.length > 0
		},
		showRecordingFilter () {
			if (!this.schedule?.talks?.length) return false
			let hasRecorded = false
			let hasNotRecorded = false
			for (const s of this.schedule.talks) {
				if (s?.do_not_record === true) hasNotRecorded = true
				else if (s?.do_not_record === false) hasRecorded = true
				if (hasRecorded && hasNotRecorded) return true
			}
			return false
		},
		filterGroups () {
			const groups = [
				{ refKey: 'track', title: 'Tracks', data: this.allTracks },
				{ refKey: 'room', title: 'Rooms', data: this.allRooms },
				{ refKey: 'type', title: 'Types', data: this.allTypes }
			]
			if (this.allLanguages.length > 1) {
				groups.push({ refKey: 'language', title: 'Language', data: this.allLanguages })
			}
			return groups
		},
		speakersLookup () {
			if (!this.schedule) return {}
			return this.schedule.speakers.reduce((acc, s) => { acc[s.code] = s; return acc }, {})
		},
		// baseSessions: filtered by favs/tracks/rooms/types/languages/dates but NOT search.
		// Used for structural data (days, rooms) so the UI scaffold stays stable during search.
		baseSessions () {
			if (!this.schedule || !this.currentTimezone) return
			const sessions = []
			for (const session of this.schedule.talks.filter(s => s.start)) {
				if (this.onlyFavs && !this.favs.includes(session.code)) continue
				if (this.showRecordingFilter) {
					if (this.recordingFilter === 'yes' && session.do_not_record !== false) continue
					if (this.recordingFilter === 'no' && session.do_not_record !== true) continue
				}
				if (this.filteredTracks.length && !this.filteredTracks.find(t => t.id === session.track)) continue
				if (this.filteredRooms.length && !this.filteredRooms.find(r => r.id === session.room)) continue
				if (this.filteredTypes.length && !this.filteredTypes.find(t => t.value === session.session_type)) continue
				if (this.filteredLanguages.length && !this.filteredLanguages.find(l => l.value === session.content_locale)) continue
				const start = moment.tz(session.start, this.currentTimezone)
				if (this.displayDates.length && !this.displayDates.includes(start.clone().tz(this.schedule.timezone).format('YYYY-MM-DD'))) continue
				sessions.push({
					id: session.code,
					title: session.title,
					abstract: session.abstract,
					description: session.description,
					do_not_record: session.do_not_record,
					start: start,
					end: moment.tz(session.end, this.currentTimezone),
					speakers: (session.speakers || [])
						.map(code => this.speakersLookup[code] || { code })
						.filter(Boolean),
					track: this.tracksLookup[session.track],
					room: this.roomsLookup[session.room],
					fav_count: session.fav_count,
					tags: session.tags,
					session_type: session.session_type,
					content_locale: session.content_locale,
					resources: session.resources,
					answers: session.answers,
					exporters: session.exporters,
					recording_iframe: session.recording_iframe,
					stream_url: session.stream_url || null,
					stream_type: session.stream_type || null,
				})
			}
			sessions.sort((a, b) => a.start.diff(b.start))
			return sessions
		},
		// sessions: baseSessions + search filter. Used for display.
		sessions () {
			if (!this.baseSessions) return
			if (!this.searchQuery) return this.baseSessions
			const q = this.searchQuery.toLowerCase()
			return this.baseSessions.filter(s => {
				const speakerNames = (s.speakers || []).map(sp => (sp?.name || '').toLowerCase()).join(' ')
				const trackName = (s.track ? (getLocalizedString(s.track.name) || '') : '').toLowerCase()
				const roomName = (s.room ? (getLocalizedString(s.room.name) || '') : '').toLowerCase()
				const fields = [
					(getLocalizedString(s.title) || '').toLowerCase(),
					(getLocalizedString(s.abstract) || '').toLowerCase(),
					speakerNames,
					trackName,
					roomName
				]
				return fields.some(f => f.includes(q))
			})
		},
		rooms () {
			return this.schedule.rooms.filter(r => this.baseSessions.some(s => s.room === r))
		},
		days () {
			if (!this.baseSessions) return
			let days = []
			for (const session of this.baseSessions) {
				const day = session.start.clone().tz(this.currentTimezone).startOf('day')
				if (!days.find(d => d.valueOf() === day.valueOf())) days.push(day)
			}
			days.sort((a, b) => a.diff(b))
			return days
		},
		inEventTimezone () {
			if (!this.schedule?.talks?.length) return false
			return moment().utcOffset() === moment.tz(this.schedule.timezone).utcOffset()
		},
		hasAmPm () {
			return new Intl.DateTimeFormat(this.locale, {hour: 'numeric'}).resolvedOptions().hour12
		},
		isSpeakerView () {
			return this.view === 'speakers' || this.view === 'speaker' || this.view === 'featured-speakers'
		},
		isTalkView () {
			return this.view === 'talk'
		},
		properSessions () {
			if (!this.sessions) return []
			return this.sessions.filter(s => isProperSession(s))
		},
		resolvedTalk () {
			if (!this.talkCode || !this.sessions) return null
			return this.sessions.find(s => s.id === this.talkCode) || null
		},
		eventSlug () {
			let url = ''
			if (this.eventUrl.startsWith('http')) {
				url = new URL(this.eventUrl)
			} else {
				url = new URL('http://example.org/' + this.eventUrl)
			}
			// Extract the last non-empty path segment as the event slug
			const segments = url.pathname.split('/').filter(s => s.length > 0)
			return segments[segments.length - 1] || url.pathname.replace(/\//g, '')
		},
		remoteApiUrl () {
			if (!this.eventUrl) return ''
			let eventUrlObj
			try {
				eventUrlObj = new URL(this.eventUrl)
			} catch {
				eventUrlObj = new URL(this.eventUrl, window.location.origin)
			}
			return `${eventUrlObj.protocol}//${eventUrlObj.host}/api/v1/events/${this.eventSlug}/`
		},
		popularityFeatureEnabled () {
			return !!this.schedule?.feature_flags?.session_popularity_enabled
		},
		showPopularityOnCalendar () {
			return this.popularityFeatureEnabled && !!this.schedule?.feature_flags?.session_popularity_show_on_calendar
		},
		showPopularityOnList () {
			return this.popularityFeatureEnabled && !!this.schedule?.feature_flags?.session_popularity_show_on_list
		},
		sortOptions () {
			const options = ['room', 'title']
			if (this.popularityFeatureEnabled) options.push('popularity')
			return options
		},
		effectiveSortBy () {
			return this.sortOptions.includes(this.sortBy) ? this.sortBy : 'room'
		}
	},
	watch: {
		popularityFeatureEnabled (enabled) {
			if (!enabled && this.sortBy === 'popularity') {
				this.sortBy = 'room'
			}
		},
		recordingFilter () {
			this.writeRecordingQueryParam()
		}
	},
	async created () {
		// Gotta get the fragment early, before anything else sneakily modifies it
		const fragment = window.location.hash.slice(1)
		this.readRecordingQueryParam()
		moment.locale(this.locale)
		this.userTimezone = moment.tz.guess()
		// If opened via old /sessions/ URL, activate sessions mode
		if (this.view === 'sessions') {
			this.sessionsMode = true
		}

		// Detect login state from the DOM element (always rendered by Django),
		// independent of whether the PRETALX_MESSAGES JS global loaded
		const messagesEl = document.querySelector('#pretalx-messages')
		if (messagesEl) {
			this.onHomeServer = true
			if (messagesEl.dataset.loggedIn === 'true') {
				this.loggedIn = true
			}
		}

		// Load translation messages if available
		/* global PRETALX_MESSAGES */
		if (typeof PRETALX_MESSAGES !== 'undefined') {
			this.translationMessages = PRETALX_MESSAGES
		}

		// Use inline data if available (on-site), otherwise fetch (external embed)
		const dataEl = document.getElementById('pretalx-schedule-data')
		if (dataEl) {
			try { this.schedule = JSON.parse(dataEl.textContent) } catch (e) { /* ignore parse error, fall through to fetch */ }
		}
		if (this.schedule) {
			this.onHomeServer = true
		} else {
			let version = ''
			if (this.version)
				version = `v/${this.version}/`
			const url = `${this.eventUrl}schedule/${version}widgets/schedule.json`
			const legacyUrl = `${this.eventUrl}schedule/${version}widget/v2.json`
			// fetch from url, but fall back to legacyUrl if url fails
			try {
				this.schedule = await (await fetch(url)).json()
			} catch (e) {
				try {
					this.schedule = await (await fetch(legacyUrl)).json()
				} catch (e) {
					this.scheduleError = true
					return
				}
			}
		}
		// Read toolbar metadata (version, exporters) injected by Django
		const metaEl = document.getElementById('pretalx-schedule-meta')
		if (metaEl) {
			try { this.scheduleMeta = JSON.parse(metaEl.textContent) } catch (e) { /* ignore */ }
		}

		// For speaker and talk views, we only need schedule data + favs (no day tabs, filters, etc.)
		if (this.isSpeakerView || this.isTalkView) {
			if (!this.schedule) {
				this.scheduleError = true
				return
			}
			this.currentTimezone = localStorage.getItem(`${this.eventSlug}_timezone`)
			this.currentTimezone = [this.schedule.timezone, this.userTimezone].includes(this.currentTimezone) ? this.currentTimezone : this.schedule.timezone
			this.now = moment.tz(this.currentTimezone)
			setInterval(() => this.now = moment.tz(this.currentTimezone), 30000)
			this.apiUrl = window.location.origin + '/api/v1/events/' + this.eventSlug + '/'
			if (this.publicFavsUrl) {
				this.favsReadOnly = true
				this.onlyFavs = true
				this.favs = this.pruneFavs(await this.loadPublicFavs(), this.schedule)
			} else {
				this.favs = this.pruneFavs(await this.loadFavs(), this.schedule)
			}
			return
		}

		if (!this.schedule.talks.length) {
			this.scheduleError = true
			return
		}
		this.currentTimezone = localStorage.getItem(`${this.eventSlug}_timezone`)
		this.currentTimezone = [this.schedule.timezone, this.userTimezone].includes(this.currentTimezone) ? this.currentTimezone : this.schedule.timezone
		this.currentDay = this.days[0].format('YYYY-MM-DD')
		this.now = moment.tz(this.currentTimezone)
		setInterval(() => this.now = moment.tz(this.currentTimezone), 30000)
		if (!this.scrollParentResizeObserver) {
			await this.$nextTick()
			this.onWindowResize()
		}
		this.schedule.tracks.forEach(t => { t.value = t.id; t.label = getLocalizedString(t.name); this.allTracks.push(t) })
		this.schedule.rooms.forEach(r => { this.allRooms.push({ id: r.id, value: r.id, label: getLocalizedString(r.name), selected: false }) })
		const typeSet = new Set()
		this.schedule.talks.forEach(s => {
			if (s.session_type && !typeSet.has(s.session_type)) {
				typeSet.add(s.session_type)
				this.allTypes.push({ value: s.session_type, label: s.session_type, selected: false })
			}
		})
		// Build language filter from event content_locales (configured by organiser),
		// falling back to per-talk content_locale for older data.
		const langSet = new Set()
		const eventLocales = this.schedule.content_locales || []
		eventLocales.forEach(code => {
			if (code && !langSet.has(code)) {
				langSet.add(code)
				const displayName = (() => {
					try { return new Intl.DisplayNames([this.locale], { type: 'language' }).of(code) } catch { return code }
				})()
				this.allLanguages.push({ value: code, label: displayName, selected: false })
			}
		})

		// Also include any per-talk locales not already covered by event locales
		this.schedule.talks.forEach(s => {
			if (s.content_locale && !langSet.has(s.content_locale)) {
				langSet.add(s.content_locale)
				const displayName = (() => {
					try { return new Intl.DisplayNames([this.locale], { type: 'language' }).of(s.content_locale) } catch { return s.content_locale }
				})()
				this.allLanguages.push({ value: s.content_locale, label: displayName, selected: false })
			}
		})

		// set API URL before loading favs
		this.apiUrl = window.location.origin + '/api/v1/events/' + this.eventSlug + '/'
		if (this.publicFavsUrl) {
			this.favsReadOnly = true
			this.onlyFavs = true
			this.favs = this.pruneFavs(await this.loadPublicFavs(), this.schedule)
		} else {
			this.favs = this.pruneFavs(await this.loadFavs(), this.schedule)
		}

		if (fragment && fragment.length === 10) {
			const initialDay = moment.tz(fragment, this.currentTimezone)
			const filteredDays = this.days.filter(d => d.clone().tz(this.currentTimezone).format('YYYY-MM-DD') === initialDay.format('YYYY-MM-DD'))
			if (filteredDays.length) {
				this.currentDay = filteredDays[0].format('YYYY-MM-DD')
			}
		}
	},
	async mounted () {
		// We block until we have either a regular parent or a shadow DOM parent
		await new Promise((resolve) => {
			const poll = () => {
				if (this.$el.parentElement || this.$el.getRootNode().host) return resolve()
				setTimeout(poll, 100)
			}
			poll()
		})
		this.scrollParent = findScrollParent(this.$el.parentElement || this.$el.getRootNode().host)
		if (this.scrollParent) {
			this.scrollParentResizeObserver = new ResizeObserver(this.onScrollParentResize)
			this.scrollParentResizeObserver.observe(this.scrollParent)
			this.scrollParentWidth = this.scrollParent.offsetWidth
		} else { // scrolling document
			window.addEventListener('resize', this.onWindowResize)
			this.onWindowResize()
		}
	},
	destroyed () {
		// TODO destroy observers
	},
	methods: {
		readRecordingQueryParam () {
			try {
				const url = new URL(window.location.href)
				const value = url.searchParams.get('recording')
				if (value === 'yes' || value === 'no' || value === 'all') {
					this.recordingFilter = value
				}
			} catch {
				// ignore invalid URL contexts
			}
		},
		writeRecordingQueryParam () {
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
		setCurrentDay (day) {
			// Find best match among days, because timezones can muddle this
			const matchingDays = this.days.filter(d => d.format('YYYY-MM-DD') === day.format('YYYY-MM-DD'))
			if (matchingDays.length) {
				this.currentDay = matchingDays[0].format('YYYY-MM-DD')
			}
		},
		changeDay (day) {
			if (day.clone().startOf('day').format('YYYY-MM-DD') === this.currentDay) return
			this.currentDay = day.clone().startOf('day').format('YYYY-MM-DD')
			window.location.hash = day.format('YYYY-MM-DD')
		},
		selectDay (dayId) {
			this.currentDay = dayId
			window.location.hash = dayId
			this.forceScrollDay++
		},
		onWindowResize () {
			this.scrollParentWidth = document.body.offsetWidth
		},
		saveTimezone () {
			localStorage.setItem(`${this.eventSlug}_timezone`, this.currentTimezone)
		},
		onScrollParentResize (entries) {
			this.scrollParentWidth = entries[0].contentRect.width
		},
		async remoteApiRequest (path, method, data) {
			const eventUrlObj = new URL(this.eventUrl)
			const baseUrl = `${eventUrlObj.protocol}//${eventUrlObj.host}/api/v1/events/${this.eventSlug}/`
			return this.apiRequest(path, method, data, baseUrl)
		},
		async apiRequest (path, method, data, baseUrl) {
			const base = baseUrl || this.apiUrl
			const url = `${base}${path}`
			const headers = new Headers()
			if (this.onHomeServer) {
				headers.append('Content-Type', 'application/json')
			}
			if (method === 'POST' || method === 'DELETE') headers.append('X-CSRFToken', getCsrfToken())
			const response = await fetch(url, {
				method,
				headers,
				body: JSON.stringify(data),
				credentials: this.onHomeServer ? 'same-origin' : 'omit'
			})
			if (!response.ok) {
				throw new Error(`HTTP error! status: ${response.status}`)
			}
			return response.json()
		},
		async loadFavs () {
			const storageKey = `${this.eventSlug}_favs`
			const data = localStorage.getItem(storageKey)
			let localFavs = []
			if (data) {
				try {
					localFavs = JSON.parse(data) || []
				} catch {
					localStorage.setItem(storageKey, '[]')
				}
			}
			if (this.loggedIn) {
				try {
					const merged = await this.apiRequest(
						'submissions/favourites/merge/',
						'POST',
						localFavs
					)
					if (Array.isArray(merged)) {
						localStorage.removeItem(storageKey)
						return merged
					}
				} catch {
					this.pushErrorMessage(this.translationMessages.favs_not_saved)
				}
			}
			return localFavs
		},
		async loadPublicFavs () {
			if (!this.publicFavsUrl) return []
			try {
				const response = await fetch(this.publicFavsUrl)
				if (!response.ok) return []
				const data = await response.json()
				if (Array.isArray(data)) return data
				if (data && Array.isArray(data.favs)) return data.favs
			} catch {
				return []
			}
			return []
		},
		pushErrorMessage (message) {
			if (!message || !message.length) return
			if (this.errorMessages.includes(message)) return
			this.errorMessages.push(message)
		},
		pruneFavs (favs, schedule) {
			const talks = schedule.talks || []
			const talkIds = talks.map(e => e.code)
			// we're not pushing the changed list to the server, as if a talk vanished but will appear again,
			// we want it to still be faved
			return favs.filter(e => talkIds.includes(e))
		},
		saveFavs () {
			if (!this.loggedIn) {
				localStorage.setItem(`${this.eventSlug}_favs`, JSON.stringify(this.favs))
			}
		},
		toggleSessionModalFav (id) {
			if (this.favs.includes(id)) {
				this.unfav(id)
			} else {
				this.fav(id)
			}
		},
		async fav (id) {
			if (this.favsReadOnly) return
			if (this.favs.includes(id)) return
			this.favs.push(id)
			this.saveFavs()
			if (this.loggedIn) {
				try {
					await this.apiRequest(`submissions/${id}/favourite/`, 'POST')
				} catch (error) {
					console.error('Failed to save favourite: %s', error)
					this.pushErrorMessage(this.translationMessages.favs_not_saved)
				}
			}
		},
		async unfav (id) {
			if (this.favsReadOnly) return
			this.favs = this.favs.filter(elem => elem !== id)
			this.saveFavs()
			if (this.loggedIn) {
				try {
					await this.apiRequest(`submissions/${id}/favourite/`, 'DELETE')
				} catch (error) {
					console.error('Failed to remove favourite: %s', error)
					this.pushErrorMessage(this.translationMessages.favs_not_saved)
				}
			}
			if (!this.favs.length) this.onlyFavs = false
		},
		async fetchSpeakerApiContentIfNeeded (speakerCode) {
			const speakerObj = this.speakersLookup[speakerCode]
			if (!speakerObj) {
				console.warn(`Speaker with code ${speakerCode} not found in speakersLookup.`)
				return
			}

			if (speakerObj.apiContent || speakerObj.isLoadingApiContent) {
				return // Already fetched or currently fetching
			}

			speakerObj.isLoadingApiContent = true
			try {
				const apiData = await this.remoteApiRequest(`speakers/${speakerCode}/?expand=answers.question`, 'GET')
				speakerObj.apiContent = apiData
			} catch (e) {
				console.error(`Failed to fetch API content for speaker ${speakerCode}:`, e)
				// Potentially set an error flag on speakerObj if needed for UI
			} finally {
				speakerObj.isLoadingApiContent = false
			}
		},
		async showSpeakerDetails(speaker, ev) {
			ev.preventDefault()
			const speakerObj = this.speakersLookup[speaker.code];
			if (!speakerObj) {
				console.warn(`Speaker ${speaker.code} not found for details view.`);
				return;
			}

			const speakerSessions = this.sessions.filter(session =>
				session.speakers?.some(s => s.code === speaker.code)
			)

			// Show speaker immediately with loading state
			this.modalContent = {
				contentType: 'speaker',
				contentObject: {
					...speakerObj,
					sessions: speakerSessions.map(s => ({...s, faved: this.favs.includes(s.id)})),
					isLoading: !speakerObj.apiContent
				}
			}
			this.$refs.sessionModal?.showModal()

			// Attempt to fetch/refresh speaker's apiContent.
			// The helper method handles "already fetched" or "currently fetching" internally.
			await this.fetchSpeakerApiContentIfNeeded(speaker.code)

			// After the fetch attempt, speakerObj in speakersLookup might have been updated.
			// Re-set modalContent to reflect the latest state and turn off modal's isLoading.
			if (this.modalContent && this.modalContent.contentType === 'speaker' && this.modalContent.contentObject.code === speaker.code) {
				this.modalContent = {
					contentType: 'speaker',
					contentObject: {
						...this.speakersLookup[speaker.code], // Use the potentially updated speakerObj
						sessions: speakerSessions.map(s => ({...s, faved: this.favs.includes(s.id)})),
						isLoading: false // Fetch attempt is done, modal's own spinner can be turned off.
										 // Content visibility (biography) depends on speakerObj.apiContent.
					}
				}
			}
		},
		async showSessionDetails(session, ev) {
			ev.preventDefault()

			// Find the talk in the schedule
			const talk = this.schedule.talks.find(t => t.code === session.id)

			// Show session immediately with loading state
			this.modalContent = {
				contentType: 'session',
				contentObject: {
					...session,
					apiContent: talk.apiContent,
					isLoading: !talk.apiContent,
					faved: this.favs.includes(session.id)
				}
			}
			this.$refs.sessionModal?.showModal()

			// Fetch additional data if needed
			if (!talk.apiContent) {
				try {
					// Ensure isLoading is true for the session description part
					if (this.modalContent && this.modalContent.contentType === 'session' && this.modalContent.contentObject.id === session.id) {
						this.modalContent.contentObject.isLoading = true;
					}
					talk.apiContent = await this.remoteApiRequest(`submissions/${session.id}/?expand=answers.question`, 'GET')
					// Update content with fetched description if we are still on the same session
					if (this.modalContent && this.modalContent.contentType === 'session' && this.modalContent.contentObject.id === session.id) {
						this.modalContent = {
							contentType: 'session',
							contentObject: {
								...session,
								apiContent: talk.apiContent,
								isLoading: false,
								faved: this.favs.includes(session.id)
							}
						}
					}
				} catch (e) {
					console.error('Failed to fetch session details:', e)
					if (this.modalContent && this.modalContent.contentType === 'session' && this.modalContent.contentObject.id === session.id) {
						this.modalContent.contentObject.isLoading = false
					}
				}
			}

			// Asynchronously fetch speaker biographies for all speakers in this session
			if (session.speakers && session.speakers.length > 0) {
				const speakerFetchPromises = session.speakers.map(spk =>
					this.fetchSpeakerApiContentIfNeeded(spk.code)
				);
				// We don't need to await these here; they will update speaker objects reactively.
				// Errors are logged by the helper.
				Promise.allSettled(speakerFetchPromises);
			}
		},
		resetAllFilters () {
			this.allTracks.forEach(t => t.selected = false)
			this.allRooms.forEach(r => r.selected = false)
			this.allTypes.forEach(t => t.selected = false)
			this.allLanguages.forEach(l => l.selected = false)
			this.recordingFilter = 'all'
		}
	}
}
</script>
<style lang="stylus">
@import 'styles/global.styl'
.schedule-error
	color: $clr-error
	font-size: 18px
	text-align: center
	padding: 32px
	.error-message
		margin-top: 16px

.pretalx-schedule, dialog.pretalx-modal
	color: rgb(13 15 16)

.pretalx-schedule
	display: flex
	flex-direction: column
	min-height: 0
	font-size: 14px
	--pretalx-clr-text: rgb(13,15,16)
	&:fullscreen
		background: #fff
		padding: 0
		margin: 0
		overflow: auto
		--pretalx-sticky-top-offset: 0px
		> .c-schedule-toolbar
			border-bottom: 1px solid $clr-dividers-light
	&.grid-schedule
		margin: 0 auto
	&.list-schedule
		min-width: 0
	&.speaker-view
		min-width: 0
	.days
		background-color: $clr-white
		tabs-style(active-color: var(--pretalx-clr-primary), indicator-color: var(--pretalx-clr-primary), background-color: transparent)
		overflow-x: auto
		position: sticky
		top: calc(var(--pretalx-sticky-top-offset, 0px) + 40px)
		left: 0
		margin-bottom: 0
		flex: none
		min-width: 0
		height: 48px
		z-index: 30
		display: none
		.bunt-tabs-header
			min-width: min-content
		.bunt-tabs-header-items
			justify-content: center
			min-width: min-content
			.bunt-tab-header-item
				min-width: min-content
			.bunt-tab-header-item-text
				white-space: nowrap
.error-messages
	position: fixed
	width: 250px
	bottom: 0
	right: 0
	padding: 12px
	z-index: 1000
	.error-message
		padding: 8px
		color: $clr-danger
		background-color: $clr-white
		border: 2px solid $clr-danger
		border-radius: 6px
		box-shadow: 0 2px 4px rgba(0,0,0,0.2)
		margin-top: 8px
		position: relative
		.btn
			border: 1px solid $clr-danger
			border-radius: 2px
			box-shadow: 1px 1px 2px rgba(0,0,0,0.2)
			width: 18px
			height: 18px
			position: absolute
			top: 4px
			right: 4px
			display: flex
			justify-content: center
			align-items: center
			cursor: pointer
		.message
			margin-right: 22px
.no-results
	text-align: center
	padding: 48px 16px
	color: #888
	font-size: 16px
.powered-by
	text-align: center
	color: $clr-grey-600
	font-size: 12px
	margin-top: 16px
	margin-bottom: 16px
	.pretalx
		transition: all 0.1s ease-in
		font-weight: bold
		margin-left: 4px
		color: $clr-grey-600
	&:hover .pretalx
		color: #3aa57c

@media print
	.pretalx-schedule
		height: auto !important
		overflow: visible !important
		&:fullscreen
			padding: 0
		.days
			position: static !important
		.error-messages
			display: none
	.pretalx-modal
		display: none !important
	.c-linear-schedule-session, .break
		break-inside: avoid
		page-break-inside: avoid
		box-shadow: none !important
		border: 1px solid #ccc !important
		-webkit-print-color-adjust: exact
		print-color-adjust: exact
		color-adjust: exact
		.time-box
			-webkit-print-color-adjust: exact
			print-color-adjust: exact
			color-adjust: exact
		.info
			border: 1px solid #ccc !important
			border-left: none !important
			-webkit-print-color-adjust: exact
			print-color-adjust: exact
			color-adjust: exact
		.session-icons
			display: none
	.c-linear-schedule-session
		.info
			background: #fff !important
	.break
		.info
			-webkit-print-color-adjust: exact
			print-color-adjust: exact
			color-adjust: exact
	.c-grid-schedule
		overflow: visible !important
		.timeslice
			position: static !important
			-webkit-print-color-adjust: exact
			print-color-adjust: exact
			color-adjust: exact
			&.gap::before
				display: none
		.c-linear-schedule-session .time-box,
		.break .time-box
			-webkit-print-color-adjust: exact
			print-color-adjust: exact
			color-adjust: exact
	.powered-by
		display: none

</style>

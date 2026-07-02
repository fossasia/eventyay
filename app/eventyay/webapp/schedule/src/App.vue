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
			:version="version || scheduleMeta?.version || ''",
			:isCurrent="scheduleMeta?.is_current !== false",
			:isFeaturedPage="isFeaturedPage",
			:isListView="!showGrid || sessionsMode",
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
			:days="allDays",
			:currentDay="currentDay",
			:sessionsMode="sessionsMode",
			:timeDensityMinutes="timeDensityMinutes",
			v-model:searchQuery="searchQuery",
			v-model:includeRoomSortKey="sortIncludeRoom",
			v-model:includeDateSortKey="sortIncludeDate",
			v-model:includePopularitySortKey="sortIncludePopularity",
			:popularityFeatureEnabled="popularityFeatureEnabled",
			:popularitySortAvailable="popularitySortAvailable",
			:exportsDisabled="exportsDisabled",
			@selectDay="selectDay($event)",
			@filterToggle="onlyFavs = false",
			@toggleFavs="onlyFavs = !onlyFavs; if (onlyFavs) resetAllFilters()",
			@resetFilters="onlyFavs = false; resetAllFilters()",
			@saveTimezone="saveTimezone",
			@toggleSessionsMode="sessionsMode = !sessionsMode",
			@setTimeDensityMinutes="setTimeDensityMinutes($event)")
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
			:showFavCount="showPopularityOnSchedule",
			:onHomeServer="onHomeServer",
			:disableAutoScroll="disableAutoScroll",
			:forceScrollDay="forceScrollDay",
			:density="'default'",
			:timeDensityMinutes="timeDensityMinutes",
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
			:showFavCount="showPopularityOnSchedule",
			:sortBy="effectiveSortBy",
			:includeRoomSortKey="sortIncludeRoom",
			:includeDateSortKey="sortIncludeDate",
			:includePopularitySortKey="sortIncludePopularity",
			:onHomeServer="onHomeServer",
			:disableAutoScroll="disableAutoScroll",
			:showBreaks="!sessionsMode",
			:density="'default'",
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
import { computed, defineAsyncComponent } from 'vue'
import moment from 'moment-timezone'
import MarkdownIt from 'markdown-it'
import ScheduleToolbar from '~/components/ScheduleToolbar'
import LinearSchedule from '~/components/LinearSchedule'
import GridScheduleWrapper from '~/components/GridScheduleWrapper'
import FavButton from '~/components/FavButton'
import Session from '~/components/Session'
import SessionModal from '~/components/SessionModal'
const SpeakersList = defineAsyncComponent(() => import('~/components/SpeakersList'))
const FeaturedSpeakers = defineAsyncComponent(() => import('~/components/FeaturedSpeakers'))
const SpeakerDetail = defineAsyncComponent(() => import('~/components/SpeakerDetail'))
const TalkDetail = defineAsyncComponent(() => import('~/components/TalkDetail'))
import { findScrollParent, getLocalizedString, getSessionTime, getSessionTypeLabel, isProperSession, isPopularityFeatureEnabled, isPopularitySortAvailable, isPopularityVisibleOnSchedule, normalizePopularityCount, computeTalkExporters, areScheduleExportsDisabled, talksToScheduleSessions, buildSessionsBySpeaker, talkToSession, sortSessionsByStart, isTalkSchedulePending } from '~/utils'

function getCsrfToken () {
	const match = document.cookie.match(/eventyay_csrftoken=([^;]+)/)
	return match ? match[1] : ''
}

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
		isFeaturedPage: {
			type: Boolean,
			default: false
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
		},
		// Fetch the enriched schedule payload used on first-party agenda pages.
		enrichData: {
			type: Boolean,
			default: false
		},
		speakersListPublic: {
			type: [Boolean, String],
			default: null
		}
	},
	provide () {
		const wipLinkPrefix = () => {
			const version = this.version || this.scheduleMeta?.version || ''
			return version === 'wip' ? 'schedule/v/wip/' : ''
		}
		return {
			eventUrl: this.eventUrl,
			remoteApiUrl: computed(() => this.remoteApiUrl),
			buntTeleportTarget: computed(() => this.$refs.teleportTarget),
			onSessionLinkClick: (event, session) => {
				if (this.onHomeServer) return
				event.preventDefault()

				this.showSessionDetails(session, event)
			},
			generateSessionLinkUrl: ({eventUrl, session}) => {
				if (!this.onHomeServer) return `#session/${session.id}/`
				return `${eventUrl}${wipLinkPrefix()}talk/${session.id}/`
			},
			scheduleFav: (id) => this.fav(id),
			scheduleUnfav: (id) => this.unfav(id),
			scheduleData: computed(() => ({
				schedule: this.schedule,
				sessions: this.sessions || this.inlineScheduleSessions || [],
				sessionsBySpeaker: this.sessionsBySpeaker,
				sessionsLookup: this.sessionsLookup,
				speakersLookup: this.speakersLookup,
				favs: this.favs,
				favSet: this.favSet,
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
				if (this.onHomeServer) return `${this.eventUrl}${wipLinkPrefix()}speakers/${speaker.code}/`
				return `#speakers/${speaker.code}`
			},
			onSpeakerLinkClick: (event, speaker) => {
				if (!this.onHomeServer) {
					event.preventDefault()
					this.showSpeakerDetails(speaker, event)
				}
			},
			favsReadOnly: computed(() => this.favsReadOnly),
			translationMessages: computed(() => this.translationMessages),
			isWipPreview: computed(() => (this.version || this.scheduleMeta?.version || '') === 'wip'),
			exportsDisabled: computed(() => this.exportsDisabled),
			speakersListPublic: computed(() => this.resolvedSpeakersListPublic),
		}
	},
	data () {
		return {
			getLocalizedString,
			getSessionTime,
			markdownIt,
			sortBy: 'title',
			scrollParentWidth: Infinity,
			schedule: null,
			userTimezone: null,
			now: moment(),
			currentDay: null,
			forceScrollDay: 0,
			userNavigatingToDay: null,
			_dayNavTimeout: null,
			currentTimezone: null,
			favs: [],
			userCode: null,
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
			timeDensityMinutes: Number(localStorage.getItem('schedule-time-density-minutes') || 30),
			sortIncludeRoom: false,
			sortIncludePopularity: false,
			sortIncludeDate: (() => {
				try {
					const stored = localStorage.getItem('schedule-include-datetime')
					if (stored === null) return false
					return stored === 'true'
				} catch {
					return false
				}
			})(),
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
			// Always allow a distinct calendar grid view when not explicitly in list format
			return this.format !== 'list'
		},
		exportsDisabled () {
			return areScheduleExportsDisabled({
				version: this.version,
				scheduleMetaVersion: this.scheduleMeta?.version,
				isFeaturedPage: this.isFeaturedPage,
				exportersCount: this.scheduleMeta?.exporters?.length || 0,
				isWipPreview: this.isWipPreview,
				scheduleExportsDisabled: Boolean(this.schedule?.exports_disabled),
			}) || (this.isTalkView && Boolean(this.resolvedTalk?.schedule_pending))
		},
		resolvedSpeakersListPublic () {
			const prop = this.speakersListPublic
			if (prop === false || prop === 'false') return false
			if (prop === true || prop === 'true') return true
			return Boolean(this.schedule?.speakers_list_public) && !this.schedule?.exports_disabled
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
		talksLookup () {
			if (!this.schedule) return {}
			return (this.schedule.talks || []).reduce((acc, t) => { acc[t.code] = t; return acc }, {})
		},
		sessionsBySpeaker () {
			const sessions = this.sessions || this.inlineScheduleSessions
			return buildSessionsBySpeaker(sessions)
		},
		favSet () {
			return new Set(this.favs || [])
		},
		// baseSessions: filtered by favs/tracks/rooms/types/languages/dates but NOT search.
		// Used for structural data (days, rooms) so the UI scaffold stays stable during search.
		baseSessions () {
			if (!this.schedule || !this.currentTimezone) return
			const filteredTrackIds = this.filteredTracks.length ? new Set(this.filteredTracks.map(t => t.id)) : null
			const filteredRoomIds = this.filteredRooms.length ? new Set(this.filteredRooms.map(r => r.id)) : null
			const filteredTypeValues = this.filteredTypes.length ? new Set(this.filteredTypes.map(t => t.value)) : null
			const favSet = this.onlyFavs ? this.favSet : null
			const displayDateSet = this.displayDates.length ? new Set(this.displayDates) : null
			let langExact = null
			let langPrimary = null
			if (this.filteredLanguages.length) {
				langExact = new Set(this.filteredLanguages.map(l => normalizeLocaleCode(l.value)))
				langPrimary = new Set(
					this.filteredLanguages
						.map(l => normalizeLocaleCode(l.value))
						.map((code) => localePrimary(code))
						.filter(Boolean)
				)
			}
			const sessionContext = {
				timezone: this.currentTimezone,
				speakersLookup: this.speakersLookup,
				tracksLookup: this.tracksLookup,
				roomsLookup: this.roomsLookup,
				includePopularity: true,
			}
			const sessions = []
			for (const talk of this.schedule.talks) {
				if (favSet && !favSet.has(talk.code)) continue
				if (this.showRecordingFilter) {
					if (this.recordingFilter === 'yes' && talk.do_not_record !== false) continue
					if (this.recordingFilter === 'no' && talk.do_not_record !== true) continue
				}
				if (filteredTrackIds && !filteredTrackIds.has(talk.track)) continue
				if (filteredRoomIds && !filteredRoomIds.has(talk.room)) continue
				if (filteredTypeValues && !filteredTypeValues.has(getSessionTypeLabel(talk.session_type))) continue
				if (langExact) {
					const fallbackLocale = this.schedule?.content_locales?.[0] || null
					const sessionLocale = talk.content_locale || fallbackLocale
					const normalized = normalizeLocaleCode(sessionLocale)
					if (!normalized) continue
					const primary = localePrimary(normalized)
					if (!langExact.has(normalized) && !(primary && langPrimary.has(primary))) continue
				}
				if (!isTalkSchedulePending(talk)) {
					const start = moment.tz(talk.start, this.currentTimezone)
					if (displayDateSet && !displayDateSet.has(start.clone().tz(this.schedule.timezone).format('YYYY-MM-DD'))) continue
				}
				sessions.push(talkToSession(talk, sessionContext))
			}
			return sortSessionsByStart(sessions)
		},
		inlineScheduleSessions () {
			return talksToScheduleSessions(this.schedule?.talks, {
				timezone: this.currentTimezone,
				speakersLookup: this.speakersLookup,
				tracksLookup: this.tracksLookup,
				roomsLookup: this.roomsLookup,
				includePopularity: true,
			})
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
				const title = (getLocalizedString(s.title) || '').toLowerCase()
				const abstract = (getLocalizedString(s.abstract) || '').toLowerCase()
				return title.includes(q) || abstract.includes(q) || speakerNames.includes(q)
					|| trackName.includes(q) || roomName.includes(q)
			})
		},
		sessionsLookup () {
			if (!this.sessions) return {}
			return this.sessions.reduce((acc, s) => { acc[s.id] = s; return acc }, {})
		},
		rooms () {
			if (!this.baseSessions) return []
			const roomsInSessions = new Set()
			for (const s of this.baseSessions) {
				if (s.room) roomsInSessions.add(s.room)
			}
			return this.schedule.rooms.filter(r => roomsInSessions.has(r))
		},
		// allDays: all unique days from baseSessions, always unfiltered by sort.
		// Passed to the toolbar so day-picker buttons are never hidden by the
		// 'Include datetime' sort toggle.
		allDays () {
			if (!this.baseSessions) return []
			const seen = new Set()
			const days = []
			for (const session of this.baseSessions) {
				if (!session.start) continue
				const day = session.start.clone().tz(this.currentTimezone).startOf('day')
				const key = day.valueOf()
				if (!seen.has(key)) {
					seen.add(key)
					days.push(day)
				}
			}
			days.sort((a, b) => a.diff(b))
			return days
		},
		// days: collapses to one entry when sorting without date grouping.
		// Only used by LinearSchedule to control day-header rendering.
		days () {
			if (!this.baseSessions) return
			const days = []
			for (const session of this.baseSessions) {
				if (!session.start) continue
				const day = session.start.clone().tz(this.currentTimezone).startOf('day')
				if (!days.find(d => d.valueOf() === day.valueOf())) days.push(day)
			}
			days.sort((a, b) => a.diff(b))
			// In session list mode without datetime grouping, collapse to 1 virtual day
			// so LinearSchedule renders a single flat sorted list.
			if (this.sessionsMode && !this.sortIncludeDate) {
				return days.length ? [days[0]] : []
			}
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
			return this.sessionsLookup[this.talkCode] || null
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
			return isPopularityFeatureEnabled(this.schedule?.feature_flags || {})
		},
		showPopularityOnSchedule () {
			return isPopularityVisibleOnSchedule({
				flags: this.schedule?.feature_flags || {},
			})
		},
		popularitySortAvailable () {
			return isPopularitySortAvailable({
				flags: this.schedule?.feature_flags || {},
			})
		},
		sortOptions () {
			const options = ['title', 'title_desc']
			if (this.popularitySortAvailable) options.push('popularity')
			return options
		},
		effectiveSortBy () {
			return this.sortOptions.includes(this.sortBy) ? this.sortBy : 'title'
		}
	},
	watch: {
		popularityFeatureEnabled (enabled) {
			if (!enabled) {
				this.sortIncludePopularity = false
				if (this.sortBy === 'popularity') this.sortBy = 'title'
			}
		},
		popularitySortAvailable (enabled) {
			if (!enabled) {
				this.sortIncludePopularity = false
				if (this.sortBy === 'popularity') this.sortBy = 'title'
			}
		},
		loggedIn () {
			if (!this.schedule) return
			this.loadFavs().then((favs) => {
				this.favs = this.pruneFavs(favs, this.schedule)
			})
		},
		recordingFilter () {
			this.writeRecordingQueryParam()
		},
		sortIncludeDate () {
			try {
				localStorage.setItem('schedule-include-datetime', String(this.sortIncludeDate))
			} catch {
				// ignore localStorage access errors
			}
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
		if (this.isFeaturedPage) {
			this.sessionsMode = true
		}

		const messagesEl = document.querySelector('#pretalx-messages')
		if (messagesEl) {
			this.onHomeServer = true
			this.userCode = messagesEl.dataset.userCode ?? null
			if (messagesEl.dataset.loggedIn === 'true') {
				this.loggedIn = true
			}
		}

		/* global PRETALX_MESSAGES */
		if (typeof PRETALX_MESSAGES !== 'undefined') {
			this.translationMessages = PRETALX_MESSAGES
		}

		// Use inline data if available, otherwise fetch the schedule JSON.
		const dataEl = document.getElementById('pretalx-schedule-data')
		if (dataEl && dataEl.textContent.trim()) {
			try { this.schedule = JSON.parse(dataEl.textContent) } catch (e) { /* ignore parse error, fall through to fetch */ }
		}
		if (this.schedule) {
			this.onHomeServer = true
		} else {
			let version = ''
			if (this.version)
				version = `v/${this.version}/`
			const params = new URLSearchParams()
			if (this.enrichData) params.set('enrich', '1')
			const query = params.toString()
			const suffix = query ? `?${query}` : ''
			const url = `${this.eventUrl}schedule/${version}widgets/schedule.json${suffix}`
			const legacyUrl = `${this.eventUrl}schedule/${version}widget/v2.json${suffix}`
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
				if (!this.loggedIn && this.favs.length) this.showAnonymousFavsInfo()
			}
			if (this.view === 'speaker' && this.speakerCode) {
				this.fetchSpeakerApiContentIfNeeded(this.speakerCode)
			}
			return
		}

		if (!this.schedule.talks.length) {
			this.scheduleError = true
			return
		}
		this.currentTimezone = localStorage.getItem(`${this.eventSlug}_timezone`)
		this.currentTimezone = [this.schedule.timezone, this.userTimezone].includes(this.currentTimezone) ? this.currentTimezone : this.schedule.timezone
		if (this.days?.length) {
			this.currentDay = this.days[0].format('YYYY-MM-DD')
		}
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
			const typeLabel = getSessionTypeLabel(s.session_type)
			if (typeLabel && !typeSet.has(typeLabel)) {
				typeSet.add(typeLabel)
				this.allTypes.push({ value: typeLabel, label: typeLabel, selected: false })
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
			if (!this.loggedIn && this.favs.length) this.showAnonymousFavsInfo()
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
		getFavStorageKey (userCode = null) {
			if (this.loggedIn && userCode) return `${this.eventSlug}_${userCode}_favs`
			return `${this.eventSlug}_favs`
		},
		readLocalFavs (storageKey) {
			const raw = localStorage.getItem(storageKey)
			if (!raw) return []
			try {
				const parsed = JSON.parse(raw)
				return Array.isArray(parsed) ? parsed : []
			} catch {
				localStorage.setItem(storageKey, '[]')
				return []
			}
		},
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
			const dayStr = day.format('YYYY-MM-DD')
			if (this.userNavigatingToDay && dayStr !== this.userNavigatingToDay) {
				return
			}
			const matchingDays = this.days.filter(d => d.format('YYYY-MM-DD') === dayStr)
			if (!matchingDays.length) return
			const nextDay = matchingDays[0].format('YYYY-MM-DD')
			if (nextDay === this.currentDay) {
				if (this.userNavigatingToDay === nextDay) {
					this.clearDayNavigationLock()
				}
				return
			}
			this.currentDay = nextDay
			if (this.userNavigatingToDay === nextDay) {
				this.clearDayNavigationLock()
			}
		},
		clearDayNavigationLock () {
			if (this._dayNavTimeout) {
				clearTimeout(this._dayNavTimeout)
				this._dayNavTimeout = null
			}
			this.userNavigatingToDay = null
		},
		beginDayNavigation (dayId) {
			this.clearDayNavigationLock()
			this.userNavigatingToDay = dayId
			this._dayNavTimeout = setTimeout(() => this.clearDayNavigationLock(), 2000)
		},
		changeDay (day) {
			if (day.clone().startOf('day').format('YYYY-MM-DD') === this.currentDay) return
			this.currentDay = day.clone().startOf('day').format('YYYY-MM-DD')
			try {
				window.history.replaceState(null, null, '#' + day.format('YYYY-MM-DD'))
			} catch (e) {
				window.location.hash = day.format('YYYY-MM-DD')
			}
		},
		selectDay (dayId) {
			try {
				window.history.replaceState(null, null, '#' + dayId)
			} catch (e) {
				window.location.hash = dayId
			}
			if (dayId !== this.currentDay) {
				this.beginDayNavigation(dayId)
				this.currentDay = dayId
			}
			// Always scroll on toolbar click. When the day is already visible,
			// scroll-sync may have set currentDay with _scrollDayUpdate, which
			// skips the currentDay watcher — forceScrollDay handles that case.
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
			const eventUrlObj = new URL(this.eventUrl, window.location.origin)
			const baseUrl = `${eventUrlObj.origin}/api/v1/events/${this.eventSlug}/`
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
			const anonymousStorageKey = this.getFavStorageKey(null)
			const localFavs = this.readLocalFavs(anonymousStorageKey)
			if (!this.loggedIn) {
				return localFavs
			}
			const userStorageKey = this.getFavStorageKey(this.userCode)
			const mergedLocal = [...new Set([
				...this.readLocalFavs(userStorageKey),
				...localFavs,
			])]
			try {
				const merged = await this.apiRequest(
					'submissions/favourites/merge/',
					'POST',
					mergedLocal
				)
				if (Array.isArray(merged)) {
					localStorage.setItem(userStorageKey, JSON.stringify(merged))
					localStorage.removeItem(anonymousStorageKey)
					return merged
				}
			} catch (error) {
				console.error('Failed to merge favourites: %s', error)
			}
			return mergedLocal
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
		showAnonymousFavsInfo () {
			if (this.loggedIn || this.favsReadOnly) return
			const message = this.translationMessages.favs_anonymous_notice
			if (message) this.pushErrorMessage(message)
		},
		pruneFavs (favs, schedule) {
			const talkSet = new Set((schedule.talks || []).map(talk => talk.code))
			return favs.filter(code => talkSet.has(code))
		},
		saveFavs () {
			const storageKey = this.getFavStorageKey(this.loggedIn ? this.userCode : null)
			try {
				localStorage.setItem(storageKey, JSON.stringify(this.favs))
			} catch (error) {
				console.error('Failed to save favourites locally: %s', error)
			}
		},
		toggleSessionModalFav (id) {
			if (this.favsReadOnly) return
			if (this.favSet.has(id)) {
				this.unfav(id)
			} else {
				this.fav(id)
			}
		},
		async fav (id) {
			if (this.favsReadOnly) return
			if (this.favSet.has(id)) return
			this.favs.push(id)
			const talk = this.schedule?.talks?.find(t => t.code === id)
			if (talk) {
				talk.fav_count = Math.max(0, Number(talk.fav_count || 0) + 1)
			}
			this.saveFavs()
			if (!this.loggedIn) {
				this.showAnonymousFavsInfo()
				return
			}
			try {
				await this.apiRequest(`submissions/${id}/favourite/`, 'POST')
			} catch (error) {
				console.error('Failed to save favourite: %s', error)
			}
		},
		async unfav (id) {
			if (this.favsReadOnly) return
			this.favs = this.favs.filter(elem => elem !== id)
			const talk = this.schedule?.talks?.find(t => t.code === id)
			if (talk) {
				talk.fav_count = Math.max(0, Number(talk.fav_count || 0) - 1)
			}
			this.saveFavs()
			if (!this.loggedIn) return
			try {
				await this.apiRequest(`submissions/${id}/favourite/`, 'DELETE')
			} catch (error) {
				console.error('Failed to remove favourite: %s', error)
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

			const speakerSessions = (
				this.sessionsBySpeaker[speaker.code?.toLowerCase()]
				|| this.sessionsBySpeaker[speaker.code]
				|| []
			)

			// Show speaker immediately with loading state
			this.modalContent = {
				contentType: 'speaker',
				contentObject: {
					...speakerObj,
					sessions: speakerSessions.map(s => ({...s, faved: this.favSet.has(s.id)})),
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
						sessions: speakerSessions.map(s => ({...s, faved: this.favSet.has(s.id)})),
						isLoading: false // Fetch attempt is done, modal's own spinner can be turned off.
										 // Content visibility (biography) depends on speakerObj.apiContent.
					}
				}
			}
		},
		computedExporters(code) {
			return computeTalkExporters(this.eventUrl, code)
		},
		async showSessionDetails(session, ev) {
			ev.preventDefault()

			const talk = this.talksLookup[session.id]
			const exporters = session.exporters || (this.onHomeServer && !this.exportsDisabled ? this.computedExporters(session.id) : null)

			// Show session immediately with loading state
			this.modalContent = {
				contentType: 'session',
				contentObject: {
					...session,
					exporters,
					apiContent: talk.apiContent,
					isLoading: !talk.apiContent,
					faved: this.favSet.has(session.id)
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
					talk.apiContent = await this.remoteApiRequest(`submissions/${session.id}/?expand=answers.question,resources`, 'GET')
					// Update content with fetched description if we are still on the same session
					if (this.modalContent && this.modalContent.contentType === 'session' && this.modalContent.contentObject.id === session.id) {
						this.modalContent = {
							contentType: 'session',
							contentObject: {
								...session,
								exporters,
								apiContent: talk.apiContent,
								isLoading: false,
								faved: this.favSet.has(session.id)
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
		},
		setTimeDensityMinutes (minutes) {
			const parsedMinutes = Number(minutes)
			const fallbackMinutes = 30
			const validMinutes = Number.isFinite(parsedMinutes) && parsedMinutes > 0 ? parsedMinutes : fallbackMinutes
			this.timeDensityMinutes = validMinutes
			try {
				localStorage.setItem('schedule-time-density-minutes', String(this.timeDensityMinutes))
			} catch (e) {
				// Ignore storage errors (e.g., in restricted environments)
			}
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
		overflow-x: clip
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

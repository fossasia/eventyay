<template lang="pug">
.pretalx-schedule(:style="{'--scrollparent-width': scrollParentWidth + 'px', '--schedule-max-width': scheduleMaxWidth + 'px', '--pretalx-sticky-date-offset': '0px'}", :class="isSpeakerView ? ['speaker-view'] : isTalkView ? ['talk-view'] : sessionsMode ? ['sessions-view', 'list-schedule'] : showGrid ? ['grid-schedule'] : ['list-schedule']")
	template(v-if="scheduleUnavailable")
		.schedule-unavailable
			.info-message {{ noScheduleMessage }}
	template(v-else-if="scheduleError")
		.schedule-error
			.error-message {{ $t('An error occurred while loading the schedule. Please try again later.') }}
	template(v-else-if="isTalkView && schedule")
		talk-detail(:talk="resolvedTalk", :talkId="talkCode", :baseUrl="eventUrl")
	template(v-else-if="isSpeakerView && schedule")
		featured-speakers(v-if="view === 'featured-speakers'")
		speakers-list(v-else-if="view === 'speakers'")
		speaker-detail(v-else-if="view === 'speaker'", :speakerId="speakerCode", :onHomeServer="onHomeServer")
	template(v-else-if="schedule && (schedule.talks.length || (isFeaturedPage && featuredRemote))")
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
			v-model:shareStarredSessions="shareStarredSessions",
			:scheduleUserLoggedIn="loggedIn",
			:hasActiveFilters="onlyFavs || hasActiveFilterSelections || recordingFilter !== 'all'",
			v-model:currentTimezone="currentTimezone",
			:scheduleTimezone="schedule.timezone",
			:userTimezone="userTimezone",
			:days="allDays",
			:currentDay="currentDay",
			:now="now",
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
			@update:shareStarredSessions="updateShareStarredSessions",
			@resetFilters="onlyFavs = false; resetAllFilters()",
			@saveTimezone="saveTimezone",
			@toggleSessionsMode="sessionsMode = !sessionsMode",
			@setTimeDensityMinutes="setTimeDensityMinutes($event)",
			@goToNow="goToNow")
		bunt-progress-circular(v-if="dayLoading", size="huge")
		grid-schedule-wrapper(ref="scheduleDisplay", v-else-if="showGrid && !sessionsMode",
			:sessions="gridDisplaySessions",
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
		linear-schedule(ref="scheduleDisplay", v-else,
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
		.no-results(v-if="sessions && !sessions.length && (searchQuery || (isFeaturedPage && featuredRemote))")
			.no-results-text No sessions match your search.
		list-pagination(
			v-if="isFeaturedPage && featuredTotalPages > 1",
			compact,
			:current-page="featuredPage",
			:total-pages="featuredTotalPages",
			:items="featuredVisiblePages",
			:status="featuredPageStatus",
			:aria-label="$t('Featured sessions pagination')",
			:previous-label="$t('Prev')",
			:previous-aria-label="$t('Previous page')",
			:next-label="$t('Next')",
			:next-aria-label="$t('Next page')",
			:loading="featuredPageLoading",
			@change="fetchFeaturedPage"
		)
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
import { validateLanguageCode } from './locales/momentLocales'
import { loadMomentLocale, preloadCommonLocales } from './locales/lazyLoader'
import MarkdownIt from 'markdown-it'
import ScheduleToolbar from '~/components/ScheduleToolbar'
import LinearSchedule from '~/components/LinearSchedule'
import GridScheduleWrapper from '~/components/GridScheduleWrapper'
import FavButton from '~/components/FavButton'
import Session from '~/components/Session'
import SessionModal from '~/components/SessionModal'
import ListPagination from '~/components/ListPagination.vue'
const SpeakersList = defineAsyncComponent(() => import('~/components/SpeakersList'))
const FeaturedSpeakers = defineAsyncComponent(() => import('~/components/FeaturedSpeakers'))
const SpeakerDetail = defineAsyncComponent(() => import('~/components/SpeakerDetail'))
const TalkDetail = defineAsyncComponent(() => import('~/components/TalkDetail'))
import { findScrollParent, getLocalizedString, getSessionTime, getSessionTypeLabel, isProperSession, isPopularityFeatureEnabled, isPopularitySortAvailable, isPopularityVisibleOnSchedule, normalizePopularityCount, computeTalkExporters, areScheduleExportsDisabled, resolveScheduleApiBase, talksToScheduleSessions, buildSessionsBySpeaker, talkToSession, sortSessionsByStart, isTalkSchedulePending, visiblePageItems, pageStatusRange, getCsrfToken, loadStarredSharingPreference, updateStarredSharingPreference, fetchWidgetScheduleData, fetchTalkScheduleDetail, mergeCompactScheduleDay, sessionIntersectsDay } from '~/utils'
import { changeScheduleLanguage } from './i18n.js'
import { isShiftSchedule, resolveMode } from './teamshifts-adapter'
import { logOperational } from './operationalLog.js'

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

function localeToMoment (code) {
	if (!code) return 'en'
	const normalized = normalizeLocaleCode(code)
	const map = {
		'zh-hans': 'zh-cn',
		'zh-hant': 'zh-tw',
		'pt-pt': 'pt',
		'nn-no': 'nn',
		'nb-no': 'nb',
		'de-formal': 'de',
		'de-informal': 'de',
		'nl-informal': 'nl',
	}
	return map[normalized] || normalized
}

async function setMomentLocale (code) {
	const locale = localeToMoment(code)

	// Validate locale before setting
	const validation = validateLanguageCode(locale)
	if (!validation.valid) {
		console.warn('⚠️ Invalid locale for moment:', validation.errors.join(', '))
		moment.locale('en')
		return
	}

	try {
		// Load the locale chunk on demand instead of bundling all locales upfront
		const loadResult = await loadMomentLocale(locale)
		if (!loadResult.success) {
			console.warn('⚠️ Could not lazy-load moment locale, falling back to en:', locale, loadResult.error)
			moment.locale('en')
			return
		}
		moment.locale(locale)
	} catch (error) {
		console.error('Failed to set moment locale:', error)
		moment.locale('en')
	}
}
const markdownIt = MarkdownIt({
	linkify: false,
	breaks: true
})

export default {
	name: 'PretalxSchedule',
	components: { FavButton, LinearSchedule, GridScheduleWrapper, Session, SessionModal, ScheduleToolbar, SpeakersList, FeaturedSpeakers, SpeakerDetail, TalkDetail, ListPagination },
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
				if (this.isShiftMode) {
					event.preventDefault()
					return
				}
				if (this.onHomeServer || isTalkSchedulePending(session)) return
				event.preventDefault()
				this.showSessionDetails(session, event)
			},
			generateSessionLinkUrl: ({eventUrl, session}) => {
				if (this.isShiftMode) return undefined
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
			scrollParent: null,
			scrollParentWidth: Infinity,
			schedule: null,
			loadedScheduleDays: {},
			textReadyDays: {},
			displayedGridDay: null,
			gridScrollDays: [],
			dayLoading: false,
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
			shareStarredSessions: false,
			scheduleError: false,
			scheduleUnavailable: false,
			onHomeServer: false,
			loggedIn: false,
			_initialized: false,
			apiUrl: null,
			translationMessages: {},
			errorMessages: [],
			displayDates: this.dateFilter?.split(',').filter(d => d.length === 10) || [],
			modalContent: null,
			scheduleMeta: null,
			sessionsMode: false,
			searchQuery: '',
			featuredPage: 1,
			featuredTotalCount: 0,
			featuredTotalPages: 1,
			featuredPageSize: 48,
			featuredPageLoading: false,
			featuredRemote: false,
			featuredPagingReady: false,
			featuredSearchTimeout: null,
			recordingFilter: 'all',
			timeDensityMinutes: (() => {
				try {
					return Number(localStorage.getItem('schedule-time-density-minutes') || 30)
				} catch (error) {
					console.error('Failed to read schedule time density from localStorage', error)
					return 30
				}
			})(),
			sortIncludeRoom: false,
			sortIncludePopularity: false,
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
		}
	},
	computed: {
		isShiftMode () {
			return isShiftSchedule(this.schedule)
		},
		defaultJoinRoomBaseUrl () {
			if (!this.eventUrl) return ''
			return `${this.eventUrl.replace(/\/$/, '')}/video/rooms/`
		},
		resolvedNow() {
			return this.scheduleData?.now || this.now || moment()
		},
		scheduleMaxWidth () {
			return this.schedule ? Math.min(this.scrollParentWidth, 78 + (this.schedule.rooms?.length || 0) * 365) : this.scrollParentWidth
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
			return (this.schedule.rooms || []).reduce((acc, room) => { acc[room.id] = room; return acc }, {})
		},
		tracksLookup () {
			if (!this.schedule) return {}
			return (this.schedule.tracks || []).reduce((acc, t) => { acc[t.id] = t; return acc }, {})
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
				{ refKey: 'track', title: this.$t('Tracks'), data: this.allTracks },
				{ refKey: 'room', title: this.$t('Rooms'), data: this.allRooms },
				{ refKey: 'type', title: this.$t('Types'), data: this.allTypes }
			]
			if (this.allLanguages.length > 1) {
				groups.push({ refKey: 'language', title: this.$t('Language'), data: this.allLanguages })
			}
			return groups
		},
		speakersLookup () {
			if (!this.schedule) return {}
			return (this.schedule.speakers || []).reduce((acc, s) => { acc[s.code] = s; return acc }, {})
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
				mode: resolveMode(this.schedule),
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
				mode: resolveMode(this.schedule),
			})
		},
		// sessions: baseSessions + search filter. Used for display.
		sessions () {
			if (!this.baseSessions) return
			if (!this.searchQuery || (this.isFeaturedPage && this.featuredRemote)) return this.baseSessions
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
		scheduleNeedsEveryDay () {
			if (!this.schedule?.compact || this.isTalkView || this.isSpeakerView || this.isFeaturedPage) return false
			return !this.showGrid || this.sessionsMode || !!this.searchQuery || this.onlyFavs
				|| this.hasActiveFilterSelections || this.recordingFilter !== 'all'
		},
		scheduleNeedsText () {
			if (!this.schedule?.compact) return false
			return !this.showGrid || this.sessionsMode || !!this.searchQuery
		},
		gridDisplaySessions () {
			if (!this.sessions) return this.sessions
			if (!this.schedule?.compact || !this.showGrid || this.sessionsMode || this.scheduleNeedsEveryDay) return this.sessions
			const days = this.gridScrollDays.length
				? this.gridScrollDays
				: [this.displayedGridDay || this.currentDay].filter(Boolean)
			if (!days.length) return this.sessions
			return this.sessions.filter(session => (
				session.start && days.some(day => sessionIntersectsDay(session, day, this.currentTimezone))
			))
		},
		// allDays: day index from a compact payload when it matches the active
		// timezone, otherwise every day present in the loaded sessions.
		// Passed to the toolbar so day-picker buttons are never hidden by the
		// 'Include datetime' sort toggle.
		allDays () {
			if (
				this.schedule?.compact
				&& this.currentTimezone
				&& Array.isArray(this.schedule.days)
				&& this.schedule.days.length
				&& this.schedule.view_timezone === this.currentTimezone
			) {
				return this.schedule.days.map(day => moment.tz(day, this.currentTimezone).startOf('day'))
			}
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
		featuredPageStatus () {
			if (!this.isFeaturedPage || this.featuredTotalPages <= 1 || !this.featuredTotalCount) return ''
			const range = pageStatusRange(this.featuredPage, this.featuredPageSize, this.featuredTotalCount)
			if (!range) return ''
			return this.$t('Showing {{start}}–{{end}} of {{total}} featured sessions', range)
		},
		featuredVisiblePages () {
			return visiblePageItems(this.featuredTotalPages, this.featuredPage)
		},
		resolvedTalk () {
			if (!this.talkCode) return null
			return this.sessionsLookup[this.talkCode]
				|| this.inlineScheduleSessions.find(session => session.id === this.talkCode || session.code === this.talkCode)
				|| null
		},
		talkUnavailableMessage () {
			const m = this.translationMessages || {}
			return m.schedule_pending_secondary || this.$t('To be announced')
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
		},
		noScheduleMessage () {
			const m = this.translationMessages || {}
			return m.no_schedule_available || this.$t('No schedule has been published yet. Please check back later.')
		}
	},
	watch: {
		async locale (value) {
			await changeScheduleLanguage(value)
			await setMomentLocale(value)
		},
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
		loggedIn (isLoggedIn) {
			if (!this._initialized) return
			if (!isLoggedIn) {
				this.shareStarredSessions = false
			}
			if (!this.schedule || !this.remoteApiUrl) return
			if (!this.apiUrl) {
				this.apiUrl = this.remoteApiUrl
			}
			this.loadFavs().then((favs) => {
				this.favs = this.featuredRemote ? favs : this.pruneFavs(favs, this.schedule)
			})
		},
		recordingFilter () {
			this.writeRecordingQueryParam()
			if (this._initialized && this.schedule?.compact) this.syncCompactCoverage()
		},
		sortIncludeDate () {
			try {
				localStorage.setItem('schedule-include-datetime', String(this.sortIncludeDate))
			} catch {
				// ignore localStorage access errors
			}
		},
		searchQuery () {
			if (this.schedule?.compact && this._initialized) this.syncCompactCoverage()
			if (!this.featuredPagingReady || !this.isFeaturedPage || !this.featuredRemote) return
			if (this.featuredSearchTimeout) clearTimeout(this.featuredSearchTimeout)
			this.featuredSearchTimeout = setTimeout(() => {
				this.fetchFeaturedPage(1)
			}, 300)
		},
		currentDay () {
			if (!this._initialized || !this.schedule?.compact || this.scheduleNeedsEveryDay) return
			this.syncCompactCoverage()
		},
		currentTimezone () {
			if (!this._initialized || !this.schedule?.compact) return
			this._compactTimezoneGeneration = (this._compactTimezoneGeneration || 0) + 1
			this.reloadCompactIndex()
		},
		sessionsMode () {
			if (!this._initialized || !this.schedule?.compact) return
			this.syncCompactCoverage()
		},
		onlyFavs () {
			if (!this._initialized || !this.schedule?.compact) return
			this.syncCompactCoverage()
		},
		hasActiveFilterSelections (active) {
			if (active && this._initialized && this.schedule?.compact) this.syncCompactCoverage()
		},
		sortBy () {
			if (!this.featuredPagingReady || !this.isFeaturedPage || !this.featuredRemote) return
			this.fetchFeaturedPage(1)
		}
	},
	async created () {
		this._compactTimezoneGeneration = 0
		// Preload common locales in background for instant locale switching
		preloadCommonLocales().catch(err => console.warn('Preload common locales failed:', err))
		// Gotta get the fragment early, before anything else sneakily modifies it
		const fragment = window.location.hash.slice(1)
		await changeScheduleLanguage(this.locale)
		this.readRecordingQueryParam()
		try {
			await setMomentLocale(this.locale)
		} catch (error) {
			// Log error for debugging
			console.error('Failed to set moment locale:', {
				operation: 'locale-initialization',
				message: error.message,
				code: error.code,
				stack: error.stack,
				timestamp: new Date().toISOString()
			});

			// Fallback to default locale (English)
			this.locale = 'en';
			await setMomentLocale('en');

			// Show user-friendly error message
			this.$toast.error('Failed to load schedule locale. Please try refreshing the page.');
		}
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
			this.apiUrl = this.remoteApiUrl
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
			try {
				const parsed = JSON.parse(dataEl.textContent)
				if (parsed && typeof parsed === 'object' && (parsed.timezone || parsed.schedule_unavailable || Array.isArray(parsed.talks))) {
					this.schedule = parsed
					if (!Array.isArray(this.schedule.talks)) {
						this.schedule.talks = []
					}
					this.readFeaturedPageMeta(this.schedule)
				}
			} catch (e) { /* ignore parse error, fall through to fetch */ }
		}
		if (this.schedule) {
			this.onHomeServer = true
		} else {
			if (this.isSpeakerView && this.view === 'speakers') {
				let timezone = ''
				const metaEl = document.getElementById('pretalx-speakers-meta')
				if (metaEl) {
					try { timezone = JSON.parse(metaEl.textContent).timezone || '' } catch (e) { /* ignore */ }
				}
				this.schedule = { talks: [], speakers: [], rooms: [], timezone, schedule_unavailable: false }
			} else {
				try {
					this.schedule = await fetchWidgetScheduleData(this.eventUrl, {
						version: this.version || '',
						enrichData: this.enrichData,
					})
				} catch {
					this.scheduleError = true
					return
				}
				if (!this.schedule) {
					this.scheduleUnavailable = true
					return
				}
			}
		}
		if (this.isShiftMode) {
			this.favsReadOnly = true
		}
		// Read toolbar metadata (version, exporters) injected by Django
		const metaEl = document.getElementById('pretalx-schedule-meta')
		if (metaEl) {
			try { this.scheduleMeta = JSON.parse(metaEl.textContent) } catch (e) { /* ignore */ }
		}

		// For speaker and talk views, we only need schedule data + favs (no day tabs, filters, etc.)
		if (this.isSpeakerView || this.isTalkView) {
			if (!this.schedule || this.schedule.schedule_unavailable) {
				this.scheduleUnavailable = true
				return
			}
			this.currentTimezone = this.getSavedTimezone()
			this.now = moment.tz(this.currentTimezone)
			setInterval(() => this.now = moment.tz(this.currentTimezone), 30000)
			this.apiUrl = this.remoteApiUrl || (window.location.origin + '/api/v1/events/' + this.eventSlug + '/')
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

		const showWithoutTalks = this.isFeaturedPage || this.view === 'featured-speakers'
		if (this.schedule.schedule_unavailable || (!this.schedule.talks.length && !showWithoutTalks)) {
			this.scheduleUnavailable = true
			return
		}
		this.currentTimezone = this.getSavedTimezone()
		if (this.schedule.compact) {
			this.noteCompactPayload(this.schedule)
			if (this.currentTimezone !== this.schedule.view_timezone) {
				await this.reloadCompactIndex()
			}
		}
		const knownDays = this.allDays || []
		if (knownDays.length) {
			const todayStr = this.now.clone().tz(this.currentTimezone).format('YYYY-MM-DD')
			const todayDay = knownDays.find(d => d.clone().tz(this.currentTimezone).format('YYYY-MM-DD') === todayStr)
			this.currentDay = todayDay ? todayStr : knownDays[0].format('YYYY-MM-DD')
		}
		this.now = moment.tz(this.currentTimezone)
		setInterval(() => this.now = moment.tz(this.currentTimezone), 30000)
		this.featuredPagingReady = this.isFeaturedPage
		if (!this.scrollParentResizeObserver) {
			await this.$nextTick()
			this.onWindowResize()
		}
		this.mergeFeaturedFilters(this.schedule)

		// set API URL before loading favs
		this.apiUrl = this.remoteApiUrl || (window.location.origin + '/api/v1/events/' + this.eventSlug + '/')
		if (this.publicFavsUrl) {
			this.favsReadOnly = true
			this.onlyFavs = true
			const publicFavs = await this.loadPublicFavs()
			this.favs = this.featuredRemote ? publicFavs : this.pruneFavs(publicFavs, this.schedule)
		} else {
			const savedFavs = await this.loadFavs()
			this.favs = this.featuredRemote ? savedFavs : this.pruneFavs(savedFavs, this.schedule)
			if (!this.loggedIn && this.favs.length) this.showAnonymousFavsInfo()
		}
		this.shareStarredSessions = await loadStarredSharingPreference(this.eventUrl)

		if (fragment && fragment.length === 10) {
			const initialDay = moment.tz(fragment, this.currentTimezone)
			const knownDays = (this.allDays?.length ? this.allDays : this.days) || []
			const filteredDays = knownDays.filter(d => d.clone().tz(this.currentTimezone).format('YYYY-MM-DD') === initialDay.format('YYYY-MM-DD'))
			if (filteredDays.length) {
				this.currentDay = filteredDays[0].format('YYYY-MM-DD')
			}
		}
		this._initialized = true
		if (this.schedule?.compact) {
			this.syncCompactCoverage()
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
		this._onScheduleScroll = () => this.maybeLoadNextGridDay()
		if (this.scrollParent) {
			this.scrollParentResizeObserver = new ResizeObserver(this.onScrollParentResize)
			this.scrollParentResizeObserver.observe(this.scrollParent)
			this.scrollParentWidth = this.scrollParent.offsetWidth
			this.scrollParent.addEventListener('scroll', this._onScheduleScroll, { passive: true })
		} else { // scrolling document
			window.addEventListener('resize', this.onWindowResize)
			this.onWindowResize()
			window.addEventListener('scroll', this._onScheduleScroll, { passive: true })
		}
	},
	unmounted () {
		if (this._onScheduleScroll) {
			window.removeEventListener('scroll', this._onScheduleScroll)
			this.scrollParent?.removeEventListener('scroll', this._onScheduleScroll)
		}
	},
	destroyed () {
		// TODO destroy observers
	},
	methods: {
		noteCompactPayload (payload) {
			if (!payload?.compact || !payload.date) return
			this.loadedScheduleDays = { ...this.loadedScheduleDays, [payload.date]: true }
			if (!this.displayedGridDay) this.displayedGridDay = payload.date
			if (payload.text) {
				this.textReadyDays = { ...this.textReadyDays, [payload.date]: true }
			}
		},
		compactRequestTimezone () {
			if (!this.currentTimezone || this.currentTimezone === this.schedule?.timezone) return ''
			return this.currentTimezone
		},
		async reloadCompactIndex () {
			if (!this.schedule?.compact) return
			const generation = this._compactTimezoneGeneration || 0
			const timezone = this.compactRequestTimezone()
			const payload = await fetchWidgetScheduleData(this.eventUrl, {
				version: this.version || '',
				compact: true,
				indexOnly: true,
				timezone,
			})
			if (generation !== (this._compactTimezoneGeneration || 0) || timezone !== this.compactRequestTimezone()) return
			if (!payload?.days) return
			this.schedule.days = payload.days
			this.schedule.view_timezone = payload.view_timezone || this.currentTimezone
			if (payload.session_types) this.schedule.session_types = payload.session_types
			if (payload.content_locales) this.schedule.content_locales = payload.content_locales
			if (payload.rooms) this.schedule.rooms = payload.rooms
			if (payload.tracks) this.schedule.tracks = payload.tracks
			this.loadedScheduleDays = {}
			this.textReadyDays = {}
			this.displayedGridDay = null
			this.gridScrollDays = []
			this.mergeFeaturedFilters(this.schedule)
			if (this.currentDay && !payload.days.includes(this.currentDay)) {
				this.currentDay = payload.days[0] || this.currentDay
			}
			// currentDay's watcher does not run when the selected day is still in the new index.
			if (this._initialized && payload.days.length) {
				await this.syncCompactCoverage()
			}
		},
		async ensureScheduleDay (day, { includeText = false } = {}) {
			if (!this.schedule?.compact || !day) return
			const loaded = !!this.loadedScheduleDays[day]
			const textReady = !!this.textReadyDays[day]
			if (loaded && (!includeText || textReady)) return
			const key = `${this._compactTimezoneGeneration || 0}|${this.compactRequestTimezone()}|${day}|${includeText ? 'text' : 'cards'}`
			if (!this._dayPromises) this._dayPromises = {}
			if (this._dayPromises[key]) return this._dayPromises[key]
			const promise = this.fetchCompactDay(day, includeText)
			this._dayPromises[key] = promise
			try {
				await promise
			} finally {
				delete this._dayPromises[key]
			}
		},
		/**
		 * @throws {Error} when the schedule day request fails
		 */
		async fetchCompactDay (day, includeText) {
			const generation = this._compactTimezoneGeneration || 0
			const timezone = this.compactRequestTimezone()
			const payload = await fetchWidgetScheduleData(this.eventUrl, {
				version: this.version || '',
				compact: true,
				date: day,
				timezone,
				includeText,
			})
			if (generation !== (this._compactTimezoneGeneration || 0) || timezone !== this.compactRequestTimezone()) return
			if (!payload) return
			mergeCompactScheduleDay(this.schedule, payload)
			this.loadedScheduleDays = { ...this.loadedScheduleDays, [day]: true }
			if (includeText || payload.text) {
				this.textReadyDays = { ...this.textReadyDays, [day]: true }
			}
			this.mergeFeaturedFilters(this.schedule)
		},
		async ensureAllScheduleDays ({ includeText = false } = {}) {
			const days = this.schedule?.days || []
			if (!days.length) return
			await Promise.all(days.map(day => this.ensureScheduleDay(day, { includeText })))
		},
		prefetchAdjacentScheduleDays (day) {
			const days = this.schedule?.days || []
			const index = days.indexOf(day)
			if (index < 0) return
			const neighbors = [days[index - 1], days[index + 1]].filter(Boolean)
			neighbors.forEach(neighbor => {
				this.ensureScheduleDay(neighbor, { includeText: false }).catch(error => {
					console.error('Failed to prefetch schedule day', neighbor, error)
				})
			})
		},
		async syncCompactCoverage () {
			if (!this.schedule?.compact || this.isTalkView || this.isSpeakerView || this.isFeaturedPage) return
			if (this.scheduleNeedsEveryDay) {
				this.dayLoading = true
				try {
					await this.ensureAllScheduleDays({ includeText: this.scheduleNeedsText })
				} catch (error) {
					console.error('Failed to load schedule days', error)
				} finally {
					this.dayLoading = false
				}
				return
			}
			if (!this.currentDay) return
			const alreadyLoaded = !!this.loadedScheduleDays[this.currentDay]
			const showingOtherDay = this.gridScrollDays.some(day => day !== this.currentDay && this.loadedScheduleDays[day])
			if (!alreadyLoaded && !showingOtherDay) this.dayLoading = true
			try {
				await this.ensureScheduleDay(this.currentDay, { includeText: false })
				this.displayedGridDay = this.currentDay
				// Keep days already revealed by scrolling. Reset only when the
				// selected day is not on screen, such as a toolbar jump.
				if (!this.gridScrollDays.includes(this.currentDay)) {
					this.gridScrollDays = [this.currentDay]
				}
				this.prefetchAdjacentScheduleDays(this.currentDay)
				if (this.userNavigatingToDay === this.currentDay) {
					this.$nextTick(() => { this.forceScrollDay++ })
				}
				this.$nextTick(() => this.maybeLoadNextGridDay())
			} catch (error) {
				console.error('Failed to load schedule day', this.currentDay, error)
			} finally {
				this.dayLoading = false
			}
		},
		distanceToScheduleEnd () {
			const el = this.scrollParent
			if (!el || el === document.documentElement || el === document.body) {
				const doc = document.documentElement
				return doc.scrollHeight - window.scrollY - window.innerHeight
			}
			return el.scrollHeight - el.scrollTop - el.clientHeight
		},
		scheduleScrollHeight () {
			const el = this.scrollParent
			if (!el || el === document.documentElement || el === document.body) {
				return document.documentElement.scrollHeight
			}
			return el.scrollHeight
		},
		async maybeLoadNextGridDay () {
			if (!this._initialized || !this.schedule?.compact || !this.showGrid || this.sessionsMode || this.scheduleNeedsEveryDay) return
			if (this._extendingGrid) return
			const distance = this.distanceToScheduleEnd()
			if (distance == null || distance > 640) return
			const days = this.schedule.days || []
			const shown = this.gridScrollDays.length ? this.gridScrollDays : (this.currentDay ? [this.currentDay] : [])
			const last = shown[shown.length - 1]
			const index = days.indexOf(last)
			if (index < 0 || index + 1 >= days.length) return
			const next = days[index + 1]
			const heightBefore = this.scheduleScrollHeight()
			this._extendingGrid = true
			try {
				await this.ensureScheduleDay(next, { includeText: false })
				if (!this.gridScrollDays.includes(next)) {
					this.gridScrollDays = [...shown, next]
				}
				this.prefetchAdjacentScheduleDays(next)
			} catch (error) {
				console.error('Failed to load the next schedule day', next, error)
				return
			} finally {
				this._extendingGrid = false
			}
			this.$nextTick(() => {
				if (this.scheduleScrollHeight() <= heightBefore) return
				this.maybeLoadNextGridDay()
			})
		},
		readFeaturedPageMeta (data) {
			if (!this.isFeaturedPage || !data) return
			this.featuredPage = data.page || 1
			this.featuredTotalCount = typeof data.count === 'number' ? data.count : (data.talks || []).length
			this.featuredTotalPages = data.num_pages || 1
			this.featuredPageSize = data.page_size || this.featuredPageSize
			if (this.featuredTotalPages > 1) this.featuredRemote = true
		},
		mergeFeaturedFilters (schedule) {
			if (!schedule) return
			const knownTracks = new Set(this.allTracks.map(track => track.id))
			;(schedule.tracks || []).forEach(track => {
				if (track?.id == null || knownTracks.has(track.id)) return
				knownTracks.add(track.id)
				this.allTracks.push({
					...track,
					value: track.id,
					label: getLocalizedString(track.name),
					selected: false,
				})
			})
			const knownRooms = new Set(this.allRooms.map(room => room.id))
			;(schedule.rooms || []).forEach(room => {
				if (room?.id == null || knownRooms.has(room.id)) return
				knownRooms.add(room.id)
				this.allRooms.push({
					id: room.id,
					value: room.id,
					label: getLocalizedString(room.name),
					selected: false,
				})
			})
			const knownTypes = new Set(this.allTypes.map(type => type.value))
			const knownLanguages = new Set(this.allLanguages.map(language => language.value))
			const addLanguage = (code) => {
				if (!code || knownLanguages.has(code)) return
				knownLanguages.add(code)
				let label = code
				try {
					label = new Intl.DisplayNames([this.locale], { type: 'language' }).of(code) || code
				} catch {
					label = code
				}
				this.allLanguages.push({ value: code, label, selected: false })
			}
			;(schedule.content_locales || []).forEach(addLanguage)
			;(schedule.session_types || []).forEach(type => {
				const typeLabel = getSessionTypeLabel(type)
				if (typeLabel && !knownTypes.has(typeLabel)) {
					knownTypes.add(typeLabel)
					this.allTypes.push({ value: typeLabel, label: typeLabel, selected: false })
				}
			})
			;(schedule.talks || []).forEach(talk => {
				const typeLabel = getSessionTypeLabel(talk.session_type)
				if (typeLabel && !knownTypes.has(typeLabel)) {
					knownTypes.add(typeLabel)
					this.allTypes.push({ value: typeLabel, label: typeLabel, selected: false })
				}
				addLanguage(talk.content_locale)
			})
		},
		async fetchFeaturedPage (page) {
			if (!this.isFeaturedPage) return
			this._featuredFetchController?.abort()
			const controller = new AbortController()
			this._featuredFetchController = controller
			const nextPage = Math.min(Math.max(page, 1), this.featuredTotalPages || 1)
			this.featuredPageLoading = true
			try {
				const base = (this.eventUrl || '').replace(/\/?$/, '/')
				const url = new URL(`${base}featured/`, window.location.origin)
				url.searchParams.set('format', 'json')
				if (nextPage > 1) url.searchParams.set('page', String(nextPage))
				if (this.searchQuery) url.searchParams.set('q', this.searchQuery)
				if (this.sortBy && this.sortBy !== 'title') url.searchParams.set('sort', this.sortBy)
				const response = await fetch(url.toString(), { signal: controller.signal })
				if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
				const data = await response.json()
				this.schedule = {
					...(this.schedule || {}),
					...data,
					talks: data.talks || [],
				}
				this.readFeaturedPageMeta(data)
				this.mergeFeaturedFilters(this.schedule)
				window.scrollTo({top: 0, behavior: 'smooth'})
			} catch (error) {
				if (error?.name !== 'AbortError') {
					this.scheduleError = true
				}
			} finally {
				if (this._featuredFetchController === controller) this.featuredPageLoading = false
			}
		},
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
		goToNow() {
			const todayMoment = this.resolvedNow.clone().tz(this.currentTimezone).startOf('day')
			const today = todayMoment.format('YYYY-MM-DD')
			const todayExists = this.allDays.some(day => day.format('YYYY-MM-DD') === today)
			if (!todayExists) return
			this.changeDay(todayMoment)
			this.$nextTick(() => {
				this.$refs.scheduleDisplay?.scrollToNow?.()
			})
		},
		onWindowResize () {
			this.scrollParentWidth = document.body.offsetWidth
		},
		getSavedTimezone () {
			// Any timezone from the picker can be saved, not only the event or browser timezone
			const saved = localStorage.getItem(`${this.eventSlug}_timezone`)
			return saved && moment.tz.zone(saved) ? saved : this.schedule.timezone
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
			const base = resolveScheduleApiBase({
				baseUrl,
				apiUrl: this.apiUrl,
				remoteApiUrl: this.remoteApiUrl,
				onHomeServer: this.onHomeServer,
			})
			if (!base) {
				throw new Error('schedule API base URL is not configured')
			}
			const url = `${base}${path}`
			const headers = new Headers()
			if (this.onHomeServer) {
				headers.append('Content-Type', 'application/json')
			}
			if (method === 'POST' || method === 'DELETE' || method === 'PATCH') headers.append('X-CSRFToken', getCsrfToken())
			const response = await fetch(url, {
				method,
				headers,
				body: JSON.stringify(data),
				credentials: this.onHomeServer ? 'same-origin' : 'omit'
			})
			if (!response.ok) {
				logOperational({action: 'schedule.fetch', outcome: 'failure', backend: 'schedule_api', error_code: 'http_error', status: response.status})
				throw new Error(`HTTP error! status: ${response.status}`)
			}
			return response.json()
		},
		async updateShareStarredSessions (value) {
			const previous = this.shareStarredSessions
			this.shareStarredSessions = !!value
			if (!this.loggedIn) return
			try {
				this.shareStarredSessions = await updateStarredSharingPreference(this.eventUrl, this.shareStarredSessions)
			} catch {
				logOperational({action: 'schedule.fav', outcome: 'failure', backend: 'schedule_api', error_code: 'share_pref_failed'})
				this.shareStarredSessions = previous
			}
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
					mergedLocal,
					this.remoteApiUrl
				)
				if (Array.isArray(merged)) {
					localStorage.setItem(userStorageKey, JSON.stringify(merged))
					localStorage.removeItem(anonymousStorageKey)
					return merged
				}
			} catch {
				// Server sync is optional; local favourites are already loaded.
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
			const message = this.translationMessages.favs_anonymous_notice || this.$t('Your favourites can only be saved locally in this browser. Please sign in or register to sync starred sessions and use more features. Locally saved stars may be lost if you clear your browser data; we are not responsible for data loss in this case.')
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
				return true
			} catch {
				logOperational({action: 'schedule.fav', outcome: 'failure', backend: 'local_storage', error_code: 'quota_or_denied'})
				this.pushErrorMessage(this.translationMessages.favs_not_saved || this.$t('Could not save favourites in this browser. Please check your browser storage settings.'))
				return false
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
			const previousFavs = [...this.favs]
			this.favs.push(id)
			const talk = this.schedule?.talks?.find(t => t.code === id)
			const previousFavCount = talk ? Number(talk.fav_count || 0) : 0
			if (talk) {
				talk.fav_count = Math.max(0, previousFavCount + 1)
			}
			if (!this.saveFavs()) {
				this.favs = previousFavs
				if (talk) talk.fav_count = previousFavCount
				return
			}
			if (!this.loggedIn) {
				this.showAnonymousFavsInfo()
				return
			}
			try {
				await this.apiRequest(`submissions/${id}/favourite/`, 'POST', undefined, this.remoteApiUrl)
			} catch {
				// Local favourite is already saved.
			}
		},
		async unfav (id) {
			if (this.favsReadOnly) return
			const previousFavs = [...this.favs]
			this.favs = this.favs.filter(elem => elem !== id)
			const talk = this.schedule?.talks?.find(t => t.code === id)
			const previousFavCount = talk ? Number(talk.fav_count || 0) : 0
			if (talk) {
				talk.fav_count = Math.max(0, previousFavCount - 1)
			}
			if (!this.saveFavs()) {
				this.favs = previousFavs
				if (talk) talk.fav_count = previousFavCount
				return
			}
			if (!this.loggedIn) {
				if (!this.favs.length) this.onlyFavs = false
				return
			}
			try {
				await this.apiRequest(`submissions/${id}/favourite/`, 'DELETE', undefined, this.remoteApiUrl)
			} catch {
				// Local favourite is already saved.
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
			} catch {
				logOperational({action: 'schedule.fetch', outcome: 'failure', backend: 'schedule_api', error_code: 'speaker_failed'})
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

			// Fetch additional data if needed. The submissions API supplies answers
			// and resources; the schedule detail supplies the recording iframe
			// and fills abstract/description when the grid payload omitted them.
			if (!talk.apiContent || !talk.scheduleDetailLoaded) {
				try {
					if (this.modalContent && this.modalContent.contentType === 'session' && this.modalContent.contentObject.id === session.id) {
						this.modalContent.contentObject.isLoading = true
					}
					const detailPromise = talk.scheduleDetailLoaded
						? Promise.resolve(null)
						: fetchTalkScheduleDetail(this.eventUrl, session.id, { version: this.version || '' }).catch(error => {
							console.error('Failed to load session schedule detail', session.id, error)
							return null
						})
					const apiPromise = talk.apiContent
						? Promise.resolve(talk.apiContent)
						: this.remoteApiRequest(`submissions/${session.id}/?expand=answers.question,resources`, 'GET')
					const [apiData, detail] = await Promise.all([apiPromise, detailPromise])
					if (apiData) talk.apiContent = apiData
					if (detail) {
						talk.scheduleDetailLoaded = true
						if (detail.recording_iframe) talk.recording_iframe = detail.recording_iframe
						if (!talk.abstract && detail.abstract) talk.abstract = detail.abstract
						if (!talk.description && detail.description) talk.description = detail.description
					}
					if (apiData?.abstract && !talk.abstract) talk.abstract = apiData.abstract
					if (apiData?.description && !talk.description) talk.description = apiData.description
					if (this.modalContent && this.modalContent.contentType === 'session' && this.modalContent.contentObject.id === session.id) {
						this.modalContent = {
							contentType: 'session',
							contentObject: {
								...session,
								abstract: session.abstract || talk.abstract,
								description: session.description || talk.description,
								recording_iframe: session.recording_iframe || talk.recording_iframe,
								exporters,
								apiContent: talk.apiContent,
								isLoading: false,
								faved: this.favSet.has(session.id)
							}
						}
					}
				} catch {
					logOperational({action: 'schedule.fetch', outcome: 'failure', backend: 'schedule_api', error_code: 'session_failed'})
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
.schedule-unavailable
	color: var(--pretalx-clr-text, rgb(13, 15, 16))
	font-size: 18px
	text-align: center
	padding: 32px
	.info-message
		margin-top: 16px
		line-height: 1.5

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

<template lang="pug">
.pretalx-schedule(:style="{'--scrollparent-width': scrollParentWidth + 'px', '--schedule-max-width': scheduleMaxWidth + 'px', '--pretalx-sticky-date-offset': days && days.length > 1 ? '48px' : '0px'}", :class="showGrid ? ['grid-schedule'] : ['list-schedule']")
	template(v-if="scheduleError")
		.schedule-error
			.error-message An error occurred while loading the schedule. Please try again later.
	template(v-else-if="schedule && sessions.length")
		schedule-settings(
			:tracks="schedule.tracks",
			:filteredTracksCount="filteredTracks.length",
			:favsCount="favs.length",
			:language-filtered-tracks="filter.tracks.data"
			:language-filtered-rooms="filter.rooms.data"
			:language-filtered-session-types="filter.types.data"
			:onlyFavs="onlyFavs",
			:inEventTimezone="inEventTimezone",
			v-model:currentTimezone="currentTimezone",
			:scheduleTimezone="schedule.timezone",
			:userTimezone="userTimezone",
			@openFilter="$refs.filterModal?.showModal()",
			@toggleFavs="onlyFavs = !onlyFavs; if (onlyFavs) resetFilteredTracks()",
			@saveTimezone="saveTimezone"
			@trackToggled="toggleTrackFilterChoice"
			@roomToggled="toggleRoomFilterChoice"
		)
		bunt-tabs.days(v-if="days && days.length > 1", v-model="currentDay", ref="tabs" :class="showGrid? ['grid-tabs'] : ['list-tabs']")
			bunt-tab(v-for="day in days", :id="day.toISODate()", :header="day.toLocaleString(dateFormat)", @selected="changeDay(day)")
		grid-schedule-wrapper(v-if="showGrid",
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
			:onHomeServer="onHomeServer",
			@changeDay="setCurrentDay($event)",
			@fav="fav($event)",
			@unfav="unfav($event)")
		linear-schedule(v-else,
			:sessions="sessions",
			:rooms="rooms",
			:currentDay="currentDay",
			:now="now",
			:hasAmPm="hasAmPm",
			:timezone="currentTimezone",
			:locale="locale",
			:scrollParent="scrollParent",
			:favs="favs",
			:onHomeServer="onHomeServer",
			@changeDay="setCurrentDay($event)",
			@fav="fav($event)",
			@unfav="unfav($event)",
			:sortBy="sortBy",)
		.modal(v-if="showModal")
			.modal-content
				.modal-header
					.h3.modal-title Warning
				.modal-body.p Please login to add a session to your personal schedule.
				.modal-footer
					.button(@click="closeModal") OK
	bunt-progress-circular(v-else, size="huge", :page="true")
	.error-messages(v-if="errorMessages.length")
		.error-message(v-for="message in errorMessages", :key="message")
			.btn.btn-danger(@click="errorMessages = errorMessages.filter(m => m !== message)") x
			div.message {{ message }}
	#bunt-teleport-target(ref="teleportTarget")
	filter-modal(
		ref="filterModal",
		:tracks="allTracks",
		@trackToggled="onlyFavs = false"
	)
	session-modal(
		ref="sessionModal",
		:modalContent="modalContent",
		:currentTimezone="currentTimezone",
		:locale="locale",
		:hasAmPm="hasAmPm",
		:now="now",
		:onHomeServer="onHomeServer",
		@toggleFav="favs.includes(modalContent?.contentObject.id) ? unfav(modalContent.contentObject.id) : fav(modalContent.contentObject.id)",
		@showSpeaker="showSpeakerDetails",
		@fav="fav($event)",
		@unfav="unfav($event)"
	)
	a(href="https://pretalx.com", target="_blank", v-if="!onHomeServer").powered-by powered by
		span.pretalx(href="https://pretalx.com", target="_blank") pretalx
</template>
<script>
import { computed } from 'vue'
import { DateTime, Settings } from 'luxon'
import MarkdownIt from 'markdown-it'
import LinearSchedule from '~/components/LinearSchedule'
import GridScheduleWrapper from '~/components/GridScheduleWrapper'
import FavButton from '~/components/FavButton'
import Session from '~/components/Session'
import ScheduleSettings from '~/components/ScheduleSettings.vue'
import SessionModal from '~/components/SessionModal'
import FilterModal from '~/components/FilterModal'
import { findScrollParent, getLocalizedString, getSessionTime } from '~/utils'
import {
	filterSessionTypesByLanguage,
	filterItemsByLanguage,
	filteredSessions
} from '~/utils'

const markdownIt = MarkdownIt({
	linkify: false,
	breaks: true
})

export default {
	name: 'PretalxSchedule',
	components: { FavButton, LinearSchedule, GridScheduleWrapper, Session, ScheduleSettings, SessionModal, FilterModal },
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
		// List the dates that should be displayed, as comma-separated ISO strings
		dateFilter: {
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
			}
		}
	},
	data () {
		return {
			getLocalizedString,
			getSessionTime,
			markdownIt,
			scrollParentWidth: Infinity,
			schedule: null,
			userTimezone: null,
			now: DateTime.now(),
			currentDay: null,
			currentTimezone: null,
			favs: [],
			allTracks: [],
			onlyFavs: false,
			scheduleError: false,
			showModal: false,
			filter: {
				tracks: {
					refKey: 'track',
					/** @type {Array<{name: string, value: number, selected: boolean}>} */
					data: [],
					title: 'Tracks'
				},
				rooms: {
					refKey: 'room',
					/** @type {Array<{name: string, value: number, selected: boolean}>} */
					data: [],
					title: 'Rooms'
				},
				types: {
					refKey: 'session_type',
					/** @type {Array<{name: string, value: number, selected: boolean}>} */
					data: [],
					title: 'Types'
				}
			},
			sortOptions: [
				{id: 'title', label: 'Title'}, {id: 'time', label: 'Time'}, {id: 'popularity', label: 'Popularity'}
			],
			selectedSort: 'time',
			showSortOptions: false,
			selectedSortIcon: '',
			onHomeServer: false,
			loggedIn: false,
			apiUrl: null,
			translationMessages: {},
			errorMessages: [],
			displayDates: this.dateFilter?.split(',').filter(d => d.length === 10) || [],
			modalContent: null,
		}
	},
	computed: {
		scheduleMaxWidth () {
			return this.schedule ? Math.min(this.scrollParentWidth, 78 + this.schedule.rooms.length * 650) : this.scrollParentWidth
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
			if (!this.schedule) return []
			return filteredSessions(this.filter, this.schedule.talks)
		},
		speakersLookup () {
			if (!this.schedule) return {}
			return this.schedule.speakers.reduce((acc, s) => { acc[s.code] = s; return acc }, {})
		},
		sessions () {
			if (!this.schedule || !this.currentTimezone) return
			const sessions = []
			const filter = this.filteredTracks
			for (const session of this.schedule.talks.filter(s => s.start)) {
				if (this.onlyFavs && !this.favs.includes(session.code)) continue
				if (this.filteredTracks && this.filteredTracks.length && !this.filteredTracks.find(t => t.id === session.track)) continue
				const start = DateTime.fromISO(session.start)
				if (this.displayDates.length && !this.displayDates.includes(start.setZone(this.schedule.timezone).toISODate())) continue
				sessions.push({
					id: session.code,
					title: session.title,
					abstract: session.abstract,
					do_not_record: session.do_not_record,
					start: start,
					end: DateTime.fromISO(session.end),
					speakers: session.speakers?.map(s => this.speakersLookup[s]),
					track: this.tracksLookup[session.track],
					room: this.roomsLookup[session.room],
					fav_count: session.fav_count,
					tags: session.tags
				})
			}
			sessions.sort((a, b) => a.start.diff(b.start))
			return sessions
		},
		rooms () {
			return this.schedule.rooms.filter(r => this.sessions.some(s => s.room === r))
		},
		days () {
			if (!this.sessions) return
			let days = []
			for (const session of this.sessions) {
				const day = session.start.setZone(this.currentTimezone).startOf('day')
				if (!days.find(d => d.ts === day.ts)) days.push(day)
			}
			days.sort((a, b) => a.diff(b))
			return days
		},
		inEventTimezone () {
			if (!this.schedule?.talks?.length) return false
			return DateTime.local().offset === DateTime.local({ zone: this.schedule.timezone }).offset
		},
		dateFormat () {
			// Defaults to cccc d. LLLL for: all grid schedules with more than two rooms, and all list schedules with less than five days
			// After that, we start to shorten the date string, hoping to reduce unwanted scroll behaviour
			if ((this.showGrid && this.schedule && this.schedule.rooms.length > 2) || !this.days || !this.days.length) return { weekday: 'long', day: 'numeric', month: 'long'}
			if (this.days && this.days.length <= 5) return { weekday: 'long', day: 'numeric', month: 'long'}
			if (this.days && this.days.length <= 7) return { weekday: 'long', day: 'numeric', month: 'short'}
			return { weekday: 'short', day: 'numeric', month: 'short'}
		},
		hasAmPm () {
			return new Intl.DateTimeFormat(this.locale, {hour: 'numeric'}).resolvedOptions().hour12
		},
		eventSlug () {
			let url = ''
			if (this.eventUrl.startsWith('http')) {
				url = new URL(this.eventUrl)
			} else {
				url = new URL('http://example.org/' + this.eventUrl)
			}
			return url.pathname.replace(/\//g, '')
		},
		remoteApiUrl () {
			if (!this.eventUrl) return ''
			const eventUrlObj = new URL(this.eventUrl)
			return `${eventUrlObj.protocol}//${eventUrlObj.host}/api/events/${this.eventSlug}/`
		}
	},
	async created () {
		// Gotta get the fragment early, before anything else sneakily modifies it
		const fragment = window.location.hash.slice(1)
		Settings.defaultLocale = this.locale
		this.userTimezone = DateTime.local().zoneName
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
		if (!this.schedule.talks.length) {
			this.scheduleError = true
			return
		}
		this.currentTimezone = localStorage.getItem(`${this.eventSlug}_timezone`)
		this.currentTimezone = [this.schedule.timezone, this.userTimezone].includes(this.currentTimezone) ? this.currentTimezone : this.schedule.timezone
		this.currentDay = this.days[0].toISODate()
		this.now = DateTime.local({ zone: this.currentTimezone })
		setInterval(() => this.now = DateTime.local({ zone: this.currentTimezone }), 30000)
		if (!this.scrollParentResizeObserver) {
			await this.$nextTick()
			this.onWindowResize()
		}
		this.schedule.tracks.forEach(t => { t.value = t.id; t.label = getLocalizedString(t.name); this.allTracks.push(t) })

		// set API URL before loading favs
		this.apiUrl = window.location.origin + '/api/events/' + this.eventSlug + '/'
		this.favs = this.pruneFavs(await this.loadFavs(), this.schedule)

		this.filter.types.data = filterSessionTypesByLanguage(this?.schedule?.talks)
		this.filter.rooms.data = filterItemsByLanguage(this?.schedule?.rooms)
		this.filter.tracks.data = filterItemsByLanguage(this?.schedule?.tracks)

		if (fragment && fragment.length === 10) {
			const initialDay = DateTime.fromISO(fragment, { zone: this.currentTimezone })
			const filteredDays = this.days.filter(d => d.setZone(this.timezone).toISODate() === initialDay.toISODate())
			if (filteredDays.length) {
				this.currentDay = filteredDays[0].toISODate()
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
		/* global PRETALX_MESSAGES */
		if (typeof PRETALX_MESSAGES !== 'undefined') {
			this.translationMessages = PRETALX_MESSAGES
			// this variable being present indicates that we're running on our home instance rather than as an embedded widget elsewhere
			this.onHomeServer = true
			if (document.querySelector('#pretalx-messages')?.dataset.loggedIn === 'true') {
				this.loggedIn = true
			}
		}
	},
	destroyed () {
		// TODO destroy observers
	},
	methods: {
		setCurrentDay (day) {
			// Find best match among days, because timezones can muddle this
			const matchingDays = this.days.filter(d => d.toISODate() === day.toISODate())
			if (matchingDays.length) {
				this.currentDay = matchingDays[0].toISODate()
			}
		},
		changeDay (day) {
			if (day.startOf('day').toISODate() === this.currentDay) return
			this.currentDay = day.startOf('day').toISODate()
			window.location.hash = day.toISODate()
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
			const baseUrl = `${eventUrlObj.protocol}//${eventUrlObj.host}/api/events/${this.eventSlug}/`
			return this.apiRequest(path, method, data, baseUrl)
		},
		async apiRequest (path, method, data, baseUrl) {
			const base = baseUrl || this.apiUrl
			const url = `${base}${path}`
			const headers = new Headers()
			if (this.onHomeServer) {
				headers.append('Content-Type', 'application/json')
			}
			if (method === 'POST' || method === 'DELETE') headers.append('X-CSRFToken', document.cookie.split('pretalx_csrftoken=').pop().split(';').shift())
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
			const data = localStorage.getItem(`${this.eventSlug}_favs`)
			let favs = []
			if (data) {
				try {
					favs = JSON.parse(data) || []
				} catch {
					localStorage.setItem(`${this.eventSlug}_favs`, '[]')
				}
			}
			if (this.loggedIn) {
				try {
					favs = await this.apiRequest('submissions/favourites/', 'GET').then(data => {
						const toFav = favs.filter(e => !data.includes(e))
						toFav.forEach(e => this.apiRequest(`submissions/${e}/favourite/`, 'POST').catch())
						return data
					}).catch(e => {
						this.pushErrorMessage(this.translationMessages.favs_not_saved)
					})
				} catch (e) {
					this.pushErrorMessage(this.translationMessages.favs_not_saved)
				}
			}
			return favs
		},
		pushErrorMessage (message) {
			if (!message || !message.length) return
			if (this.errorMessages.includes(message)) return
			this.errorMessages.push(message)
		},
		toggleTrackFilterChoice(id) {
			for (const track of this.filter.tracks.data) {
				if (track.value === id) {
					track.selected = !(track.selected || false)
				}
			}
		},
		toggleRoomFilterChoice(id) {
			for (const room of this.filter.rooms.data) {
				if (room.value === id) {
					room.selected = !(room.selected || false)
				}
			}
		},
		pruneFavs (favs, schedule) {
			const talks = schedule.talks || []
			const talkIds = talks.map(e => e.code)
			// we're not pushing the changed list to the server, as if a talk vanished but will appear again,
			// we want it to still be faved
			return favs.filter(e => talkIds.includes(e))
		},
		closeModal () {
			this.showModal = false
		},
		saveFavs () {
			localStorage.setItem(`${this.eventSlug}_favs`, JSON.stringify(this.favs))
		},
		fav (id) {
			if (!this.favs.includes(id)) {
				this.favs.push(id)
				this.saveFavs()
			}
			if (this.loggedIn) {
				this.apiRequest(`submissions/${id}/favourite/`, 'POST').catch(e => {
					this.pushErrorMessage(this.translationMessages.favs_not_saved)
				})
			} else {
				this.pushErrorMessage(this.translationMessages.favs_not_logged_in)
			}
		},
		unfav (id) {
			this.favs = this.favs.filter(elem => elem !== id)
			this.saveFavs()
			if (this.loggedIn) {
				this.apiRequest(`submissions/${id}/favourite/`, 'DELETE').catch(e => {
					this.pushErrorMessage(this.translationMessages.favs_not_saved)
				})
			} else {
				this.pushErrorMessage(this.translationMessages.favs_not_logged_in)
			}
			if (!this.favs.length) this.onlyFavs = false
		},
		resetAllFiltered () {
			this.resetFiltered()
			this.onlyFavs = false
		},
		resetFiltered () {
			for (const [key, value] of Object.entries(this.filter)) {
				for (const item of value.data) {
					item.selected = false
				}
			}
		},
		toggleSortOptions () {
			this.showSortOptions = !this.showSortOptions
		},
		handleSortSelected () {
			this.selectedSort = this.selectedSortIcon
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
		resetFilteredTracks () {
			this.allTracks.forEach(t => t.selected = false)
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
	height: 100%
	font-size: 14px
	--pretalx-clr-text: rgb(13,15,16)
	&.grid-schedule
		max-width: var(--schedule-max-width)
		margin: 0 auto
	&.list-schedule
		min-width: 0
	.modal-overlay
		position: fixed
		z-index: 1000
		top: 0
		left: 0
		width: 100%
		height: 100%
		background-color: rgba(0,0,0,0.4)
		.modal-box
			width: 600px
			max-width: calc(95% - 64px)
			border-radius: 32px
			padding: 4px 32px
			margin-top: 32px
			background: white
			margin-left: auto
			margin-right: auto
			.checkbox-line
				margin: 16px 8px
				.bunt-checkbox.checked .bunt-checkbox-box
					background-color: var(--track-color)
					border-color: var(--track-color)
				.track-description
					color: $clr-grey-600
					margin-left: 32px
	.settings
		max-width: calc(var(--schedule-max-width) - 10px)
		position: sticky
		left: 0
		align-self: flex-start
		flex-wrap: wrap
		display: flex
		align-items: center
		z-index: 100
		left: 18px
		width: calc(100% - 36px)
		.fav-toggle
			display: flex
			margin-right: 5px
			&.active
				border: #FFA000 2px solid
			.bunt-button-text
				display: flex
				align-items: center
			svg
				width: 20px
				height: 20px
				margin-right: 6px
		.filter-tracks
			margin-right: 8px
			display: flex
			.bunt-button-text
				display: flex
				align-items: center
				padding-right: 8px
			svg
				width: 36px
				height: 36px
				margin-right: 6px
		.bunt-select
			max-width: 150px
			padding-right: 8px
			margin-left: 5px
		.timezone-label
			cursor: default
			color: $clr-secondary-text-light
	.days
		background-color: $clr-white
		tabs-style(active-color: var(--pretalx-clr-primary), indicator-color: var(--pretalx-clr-primary), background-color: transparent)
		overflow-x: auto
		position: sticky
		top: var(--pretalx-sticky-top-offset, 0px)
		left: 0
		margin-bottom: 0
		flex: none
		min-width: 0
		max-width: var(--schedule-max-width)
		height: 48px
		z-index: 30
		.bunt-tabs-header
			min-width: min-content
		.bunt-tabs-header-items
			justify-content: center
			min-width: min-content
			.bunt-tab-header-item
				min-width: min-content
			.bunt-tab-header-item-text
				white-space: nowrap
.modal {
	display: flex;
	justify-content: center;
	align-items: center;
	position: fixed;
	top: 0;
	left: 0;
	width: 100%;
	height: 100%;
	z-index: 999;
}

.modal-content {
	background-color: white;
	padding: 20px;
	border-radius: 5px;
	width: 300px;
	text-align: center;
	position: relative;
	border: 1px solid var(--pretalx-clr-primary);
}

.modal-header {
	margin-bottom: 10px;
}

.modal-title {
	margin: 0;
	font-size: 1.25em;
	color: var(--pretalx-clr-primary);
}

.modal-body {
	margin-bottom: 20px;
}

.modal-footer {
	display: flex;
	justify-content: flex-end;
	.button {
		cursor:pointer;
		border: 1px solid var(--pretalx-clr-primary)
		padding: 2px 5px;
		border-radius: 5px;
	}
}

.modal-footer button {
	background-color: transparent;
	border: 1px solid #ccc;
	border-radius: 5px;
	padding: 5px 10px;
	cursor: pointer;
}

.sort-icon {
	display: none !important
}

@media (max-width: 480px) {
	.hide-select {
		display: none
	}
    .sort-icon {
      display: flex !important;
      align-items: center;
    padding: 0 !important;
    min-width: 40px !important;
    margin-right: 10px;
    width: 40px !important;
    }

	.sort-icon .bunt-button-text {
		display: flex
		align-items: center
		width: 20px;
	}
	.sort-icon .bunt-button-text svg {
		width: 20px
		height: 20px
		position: absolute
	}
	.dropdown-sort-menu {
		background: white;
		border: 1px solid #ccc;
		border-radius: 4px;
		transform: translate(-7%, 68%);
		min-width: 150px !important;
		display: flex;
		flex-direction: column;
		align-items: flex-start;

	}

}

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

</style>

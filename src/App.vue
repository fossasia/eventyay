<template lang="pug">
.pretalx-schedule(:style="{'--scrollparent-width': scrollParentWidth + 'px', '--schedule-max-width': scheduleMaxWidth + 'px', '--pretalx-sticky-date-offset': days && days.length > 1 ? '48px' : '0px'}", :class="showGrid ? ['grid-schedule'] : ['list-schedule']")
	template(v-if="scheduleError")
		.schedule-error
			.error-message An error occurred while loading the schedule. Please try again later.
	template(v-else-if="schedule && sessions.length")
		.modal-overlay(v-if="showFilterModal", @click.stop="showFilterModal = false")
			.modal-box(@click.stop="")
				h3 Tracks
				.checkbox-line(v-for="track in allTracks", :key="track.value", :style="{'--track-color': track.color}")
					bunt-checkbox(type="checkbox", :label="track.label", :name="track.value + track.label", v-model="track.selected", :value="track.value", @input="onlyFavs = false")
					.track-description(v-if="getLocalizedString(track.description).length") {{ getLocalizedString(track.description) }}
		.settings
			bunt-button.filter-tracks(v-if="this.schedule.tracks.length", @click="showFilterModal=true")
				svg#filter(viewBox="0 0 752 752")
					path(d="m401.57 264.71h-174.75c-6.6289 0-11.84 5.2109-11.84 11.84 0 6.6289 5.2109 11.84 11.84 11.84h174.75c5.2109 17.523 21.312 30.309 40.727 30.309 18.941 0 35.52-12.785 40.254-30.309h43.098c6.6289 0 11.84-5.2109 11.84-11.84 0-6.6289-5.2109-11.84-11.84-11.84h-43.098c-5.2109-17.523-21.312-30.309-40.254-30.309-19.414 0-35.516 12.785-40.727 30.309zm58.723 11.84c0 10.418-8.5234 18.469-18.469 18.469s-18.469-8.0508-18.469-18.469 8.5234-18.469 18.469-18.469c9.4727-0.003906 18.469 8.0469 18.469 18.469z")
					path(d="m259.5 359.43h-32.676c-6.6289 0-11.84 5.2109-11.84 11.84s5.2109 11.84 11.84 11.84h32.676c5.2109 17.523 21.312 30.309 40.727 30.309 18.941 0 35.52-12.785 40.254-30.309h185.17c6.6289 0 11.84-5.2109 11.84-11.84s-5.2109-11.84-11.84-11.84h-185.17c-5.2109-17.523-21.312-30.309-40.254-30.309-19.418 0-35.52 12.785-40.73 30.309zm58.723 11.84c0 10.418-8.5234 18.469-18.469 18.469-9.9453 0-18.469-8.0508-18.469-18.469s8.5234-18.469 18.469-18.469c9.9453 0 18.469 8.0508 18.469 18.469z")
					path(d="m344.75 463.61h-117.92c-6.6289 0-11.84 5.2109-11.84 11.84s5.2109 11.84 11.84 11.84h117.92c5.2109 17.523 21.312 30.309 40.727 30.309 18.941 0 35.52-12.785 40.254-30.309h99.926c6.6289 0 11.84-5.2109 11.84-11.84s-5.2109-11.84-11.84-11.84h-99.926c-5.2109-17.523-21.312-30.309-40.254-30.309-19.418 0-35.52 12.785-40.727 30.309zm58.723 11.84c0 10.418-8.5234 18.469-18.469 18.469s-18.469-8.0508-18.469-18.469 8.5234-18.469 18.469-18.469 18.469 8.0508 18.469 18.469z")
				| Filter
				template(v-if="filteredTracks.length") ({{ filteredTracks.length }})
			bunt-button.fav-toggle(v-if="favs.length", @click="onlyFavs = !onlyFavs; if (onlyFavs) resetFilteredTracks()", :class="onlyFavs ? ['active'] : []")
				svg#star(viewBox="0 0 24 24")
					polygon(
						:style="{fill: '#FFA000', stroke: '#FFA000'}"
						points="14.43,10 12,2 9.57,10 2,10 8.18,14.41 5.83,22 12,17.31 18.18,22 15.83,14.41 22,10"
					)
				| {{ favs.length }}
			template(v-if="!inEventTimezone")
				bunt-select.timezone-item(name="timezone", :options="[{id: schedule.timezone, label: schedule.timezone}, {id: userTimezone, label: userTimezone}]", v-model="currentTimezone", @blur="saveTimezone")
			template(v-else)
				div.timezone-label.timezone-item.bunt-tab-header-item {{ schedule.timezone }}
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
			@unfav="unfav($event)")
	bunt-progress-circular(v-else, size="huge", :page="true")
	.error-messages(v-if="errorMessages.length")
		.error-message(v-for="message in errorMessages", :key="message")
			.btn.btn-danger(@click="errorMessages = errorMessages.filter(m => m !== message)") x
			div.message {{ message }}
	#bunt-teleport-target(ref="teleportTarget")
	dialog#session-modal(ref="detailsModal", @click.stop="$refs.detailsModal?.close()")
		.dialog-inner(@click.stop="")
			button.close-button(@click="$refs.detailsModal?.close()") ✕
			template(v-if="modalContent && modalContent.contentType === 'session'")
				h3 {{ modalContent.contentObject.title }}
				.card-content
					.facts
						.time
							span {{ modalContent.contentObject.start.toLocaleString({ weekday: 'long', day: 'numeric', month: 'long' }) }}, {{ getSessionTime(modalContent.contentObject, currentTimezone, locale, hasAmPm).time }}
							span.ampm(v-if="getSessionTime(modalContent.contentObject, currentTimezone, locale, hasAmPm).ampm") {{ getSessionTime(modalContent.contentObject, currentTimezone, locale, hasAmPm).ampm }}
						.room(v-if="modalContent.contentObject.room") {{ getLocalizedString(modalContent.contentObject.room.name) }}
						.track(v-if="modalContent.contentObject.track", :style="{ color: modalContent.contentObject.track.color }") {{ getLocalizedString(modalContent.contentObject.track.name) }}
					.text-content
						.abstract(v-if="modalContent.contentObject.abstract", v-html="markdownIt.renderInline(modalContent.contentObject.abstract)")
						template(v-if="modalContent.contentObject.isLoading")
							bunt-progress-circular(size="big", :page="true")
						template(v-else)
							hr(v-if="modalContent.contentObject.abstract?.length && modalContent.contentObject.description?.length")
							.description(v-if="modalContent.contentObject.description", v-html="markdownIt.render(modalContent.contentObject.description)")
				.speakers(v-if="modalContent.contentObject.speakers")
					a.speaker.inner-card(v-for="speaker in modalContent.contentObject.speakers", @click="showSpeakerDetails(speaker, $event)", :href="`#speaker/${speaker.code}`", :key="speaker.code")
						.img-wrapper
							img(v-if="speaker.avatar", :src="speaker.avatar", :alt="speaker.name")
							.avatar-placeholder(v-else)
								svg(viewBox="0 0 24 24")
									path(fill="currentColor", d="M12,1A5.8,5.8 0 0,1 17.8,6.8A5.8,5.8 0 0,1 12,12.6A5.8,5.8 0 0,1 6.2,6.8A5.8,5.8 0 0,1 12,1M12,15C18.63,15 24,17.67 24,21V23H0V21C0,17.67 5.37,15 12,15Z")
						.inner-card-content {{ speaker.name }}
			template(v-if="modalContent && modalContent.contentType === 'speaker'")
				.speaker-details
					h3 {{ modalContent.contentObject.name }}
					.speaker-content.card-content
						.text-content
							template(v-if="modalContent.contentObject.isLoading")
								bunt-progress-circular(size="big", :page="true")
							template(v-else)
								.biography(v-if="modalContent.contentObject.biography", v-html="markdownIt.render(modalContent.contentObject.biography)")
						.img-wrapper
							img(v-if="modalContent.contentObject.avatar", :src="modalContent.contentObject.avatar", :alt="modalContent.contentObject.name")
							.avatar-placeholder(v-else)
								svg(viewBox="0 0 24 24")
									path(fill="currentColor", d="M12,1A5.8,5.8 0 0,1 17.8,6.8A5.8,5.8 0 0,1 12,12.6A5.8,5.8 0 0,1 6.2,6.8A5.8,5.8 0 0,1 12,1M12,15C18.63,15 24,17.67 24,21V23H0V21C0,17.67 5.37,15 12,15Z")
				.speaker-sessions
					session(
						v-for="session in modalContent.contentObject.sessions",
						:session="session",
						:showDate="true",
						:now="now",
						:timezone="currentTimezone",
						:locale="locale",
						:hasAmPm="hasAmPm",
						:faved="favs.includes(session.id)",
						:onHomeServer="onHomeServer",
						@fav="fav(session.id)",
						@unfav="unfav(session.id)",
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
import Session from '~/components/Session'
import { findScrollParent, getLocalizedString, getSessionTime } from '~/utils'

const markdownIt = MarkdownIt({
	linkify: true,
	breaks: true
})

export default {
	name: 'PretalxSchedule',
	components: { LinearSchedule, GridScheduleWrapper, Session },
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
			showFilterModal: false,
			favs: [],
			allTracks: [],
			onlyFavs: false,
			scheduleError: false,
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
		speakersLookup () {
			if (!this.schedule) return {}
			return this.schedule.speakers.reduce((acc, s) => { acc[s.code] = s; return acc }, {})
		},
		sessions () {
			if (!this.schedule || !this.currentTimezone) return
			const sessions = []
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
					room: this.roomsLookup[session.room]
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
		pruneFavs (favs, schedule) {
			const talks = schedule.talks || []
			const talkIds = talks.map(e => e.code)
			// we're not pushing the changed list to the server, as if a talk vanished but will appear again,
			// we want it to still be faved
			return favs.filter(e => talkIds.includes(e))
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
		async showSpeakerDetails(speaker, ev) {
			ev.preventDefault()

			// Find speaker in schedule data
			const speakerObj = this.schedule.speakers.find(s => s.code === speaker.code)

			const speakerSessions = this.sessions.filter(session =>
				session.speakers?.some(s => s.code === speaker.code)
			)

			// Show speaker immediately with loading state
			this.modalContent = {
				contentType: 'speaker',
				contentObject: {
					...speakerObj,
					sessions: speakerSessions,
					biography: speakerObj.apiContent?.biography,
					isLoading: !speakerObj.apiContent
				}
			}
			this.$refs.detailsModal?.showModal()

			// Fetch additional data if needed
			if (!speakerObj.apiContent) {
				try {
					speakerObj.apiContent = await this.remoteApiRequest(`speakers/${speaker.code}/`, 'GET')
					// Update content with fetched biography
					this.modalContent = {
						contentType: 'speaker',
						contentObject: {
							...speakerObj,
							sessions: speakerSessions,
							biography: speakerObj.apiContent.biography,
							isLoading: false
						}
					}
				} catch (e) {
					console.error('Failed to fetch speaker details:', e)
					this.modalContent.contentObject.isLoading = false
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
					description: talk.apiContent?.description,
					isLoading: !talk.apiContent
				}
			}
			this.$refs.detailsModal?.showModal()

			// Fetch additional data if needed
			if (!talk.apiContent) {
				try {
					talk.apiContent = await this.remoteApiRequest(`submissions/${session.id}/`, 'GET')
					// Update content with fetched description
					this.modalContent = {
						contentType: 'session',
						contentObject: {
							...session,
							description: talk.apiContent.description,
							isLoading: false
						}
					}
				} catch (e) {
					console.error('Failed to fetch session details:', e)
					this.modalContent.contentObject.isLoading = false
				}
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

.pretalx-schedule, dialog#session-modal
	color: rgb(13 15 16)

.pretalx-schedule
	display: flex
	flex-direction: column
	min-height: 0
	height: 100%
	font-size: 14px
	&.grid-schedule
		min-width: min-content
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
		align-self: flex-start
		display: flex
		align-items: center
		z-index: 100
		width: min(calc(100% - 36px), var(--schedule-max-width))
		.fav-toggle
			margin-right: 8px
			display: flex
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
			margin: 0 8px
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
			max-width: 300px
			padding-right: 8px
		.timezone-label
			cursor: default
			color: $clr-secondary-text-light
		.timezone-item
			margin-left: auto
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

#session-modal
	padding: 0
	border-radius: 8px
	border: 0
	box-shadow: 0 -2px 4px rgba(0,0,0,0.06),
		0 1px 3px rgba(0,0,0,0.12),
		0 8px 24px rgba(0,0,0,0.15),
		0 16px 32px rgba(0,0,0,0.09)
	width: calc(100vw - 32px)
	max-width: 848px
	max-height: calc(100vh - 64px)
	overflow-y: auto
	font-size: 16px

	.dialog-inner
		padding: 16px 24px
		margin: 0

	.close-button
		position: absolute
		top: 0
		right: 4px
		background: none
		border: none
		cursor: pointer
		padding: 8px
		color: $clr-grey-600
		font-size: 22px
		font-weight: bold
		&:hover
			color: $clr-grey-900

	h3
		margin: 8px 0

	.ampm
		margin-left: 4px

	.facts
		display: flex
		flex-wrap: wrap
		color: $clr-grey-600
		margin-bottom: 8px
		border-bottom: 1px solid $clr-grey-300
		&>*
			margin-right: 4px
			margin-bottom: 8px
			&:not(:last-child):after
				content: ','

	.card-content
			display: flex
			flex-direction: column

	.text-content
			padding: 8px 0
			margin-bottom: 8px
			.abstract
				font-weight: bold
			p
				font-size: 16px
			hr
				color: #ced4da
				height: 0
				border: 0
				border-top: 1px solid #e0e0e0
				margin: 16px 0

	.inner-card
		display: flex
		margin-bottom: 12px
		cursor: pointer
		border-radius: 6px
		padding: 12px
		border-radius: 6px
		border: 1px solid #ced4da
		min-height: 96px
		align-items: flex-start
		padding: 8px
		text-decoration: none
		color: var(--pretalx-clr-primary)

		.inner-card-content
			margin-top: 8px
			margin-left: 8px

	.img-wrapper
		padding: 4px 16px 4px 4px
		width: 100px
		height: 100px
		img, .avatar-placeholder
			width: 100px
			height: 100px
			border-radius: 50%
		img
			object-fit: cover
		.avatar-placeholder
			background: rgba(0,0,0,0.1)
			display: flex
			align-items: center
			justify-content: center
			svg
				width: 60%
				height: 60%
				color: rgba(0,0,0,0.3)

	.speaker-details
		h3
			margin-bottom: 0
		.speaker-content
			display: flex
			flex-direction: row
			align-items: flex-start
			justify-content: space-between
			margin-bottom: 16px

			.biography
					margin-top: 8px
</style>

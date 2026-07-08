<template lang="pug">
.c-featured-speakers(v-if="featuredSpeakers.length")
	h3#featured-speakers-heading {{ t.featured_speakers }}
	.featured-speakers-grid
		.featured-speaker-column(v-for="speaker in featuredSpeakers", :key="speaker.code")
			details.featured-speaker-card
				summary.featured-speaker-summary
					.thumbnail
						img(
							v-if="speaker.avatar_thumbnail_default || speaker.avatar || speaker.avatar_url",
							:src="speaker.avatar_thumbnail_default || speaker.avatar || speaker.avatar_url",
							:alt="speaker.name || t.speaker_fallback",
							loading="lazy"
						)
						.avatar-placeholder(v-else)
							svg(viewBox="0 0 24 24")
								path(fill="currentColor", d="M12,1A5.8,5.8 0 0,1 17.8,6.8A5.8,5.8 0 0,1 12,12.6A5.8,5.8 0 0,1 6.2,6.8A5.8,5.8 0 0,1 12,1M12,15C18.63,15 24,17.67 24,21V23H0V21C0,17.67 5.37,15 12,15Z")
						.caption.text-center
							h4 {{ speaker.name || t.speaker_fallback }}
							markdown-content.featured-speaker-preview-bio(v-if="speaker.biography", :markdown="speaker.biography")
				.featured-speaker-details
					template(v-if="speaker.sessions && speaker.sessions.length")
						hr.featured-speaker-divider
						.featured-speaker-sessions
							h4 {{ t.sessions }}
							.featured-speaker-session(
								v-for="session in speaker.sessions",
								:key="session.id",
								:class="{'featured-speaker-session-pending': isTalkSchedulePending(session)}"
							)
								small.featured-speaker-session-time {{ isTalkSchedulePending(session) ? t.schedule_pending : formatSessionDateTime(session) }}
								a.featured-speaker-session-link(
									:href="getSessionLink(session)",
									:style="getSessionStyle(session)",
									@click="onSessionClick($event, session)"
								)
									span.featured-speaker-session-slot(v-if="!isTalkSchedulePending(session)") {{ formatSessionSlot(session) }}
									span.featured-speaker-session-title {{ getLocalizedString(session.title) }}
					.featured-speaker-profile-link
						a(:href="getSpeakerLink(speaker)", @click="onSpeakerClick($event, speaker)") {{ t.view_profile }}
	p.featured-speakers-more(v-if="showMoreSpeakersLink")
		a.more-link(:href="moreSpeakersUrl") {{ t.more_speakers }}
</template>

<script>
import { getLocalizedString, compareFeaturedSpeakers, talksToScheduleSessions, buildSessionsBySpeaker, sessionsForSpeaker, sortSessionsByStart, isTalkSchedulePending } from '../utils'
import moment from 'moment-timezone'
import MarkdownContent from './MarkdownContent'

export default {
	name: 'FeaturedSpeakers',
	components: { MarkdownContent },
	inject: {
		scheduleData: { default: null },
		eventUrl: { default: '' },
		generateSpeakerLinkUrl: {
			default() {
				return ({speaker}) => `#speakers/${speaker.code}`
			}
		},
		onSpeakerLinkClick: {
			default() {
				return () => {}
			}
		},
		onSessionLinkClick: {
			default() {
				return () => {}
			}
		},
		translationMessages: { default: () => ({}) },
		speakersListPublic: { default: null },
	},
	props: {
		showAll: {
			type: Boolean,
			default: false
		}
	},
	data() {
		return {
			getLocalizedString,
			isTalkSchedulePending,
		}
	},
	computed: {
		t() {
			const m = this.translationMessages || {}
			return {
				featured_speakers: this.showAll ? (m.speakers || 'Speakers') : (m.featured_speakers || 'Featured Speakers'),
				speaker_fallback: m.speaker_fallback || 'Speaker',
				sessions: m.sessions || 'Sessions',
				view_profile: m.view_profile || 'View speaker profile',
				more_speakers: m.more_speakers || 'More speakers',
				schedule_pending: m.schedule_pending_secondary || 'Coming soon',
			}
		},
		moreSpeakersUrl() {
			const base = (this.eventUrl || '').replace(/\/?$/, '/')
			return `${base}speakers/`
		},
		showMoreSpeakersLink() {
			if (this.speakersListPublic === false) return false
			const schedule = this.scheduleData?.schedule
			if (!schedule?.speakers_list_public) return false
			if (schedule.exports_disabled) return false
			return true
		},
		trackById() {
			const schedule = this.scheduleData?.schedule
			return (schedule?.tracks || []).reduce((acc, track) => {
				if (track?.id != null) acc[track.id] = track
				return acc
			}, {})
		},
		featuredSpeakers() {
			const schedule = this.scheduleData?.schedule
			const resolvedSessions = this.scheduleData?.sessions || []
			const rawTalks = schedule?.talks || []
			const timezone = this.scheduleData?.timezone || schedule?.timezone
			if (!schedule?.speakers?.length) return []
			const featured = schedule.speakers
				.filter(s => this.showAll || s?.is_featured)
				.slice()
				.sort((a, b) => compareFeaturedSpeakers(a, b, { featuredFirst: this.showAll }))

			const speakerByCode = (schedule.speakers || []).reduce((acc, s) => {
				if (s?.code) acc[s.code] = s
				return acc
			}, {})
			const tracksLookup = this.trackById
			const roomsLookup = (schedule.rooms || []).reduce((acc, r) => {
				if (r?.id != null) acc[r.id] = r
				return acc
			}, {})

			const normalizedRawSessions = talksToScheduleSessions(rawTalks, {
				timezone,
				speakersLookup: speakerByCode,
				tracksLookup,
				roomsLookup,
			}).filter(session => session.schedule_pending || (session.start && session.end))
			const sessionsPool = resolvedSessions.length ? resolvedSessions : normalizedRawSessions
			const sessionsBySpeaker = resolvedSessions.length && this.scheduleData?.sessionsBySpeaker
				? this.scheduleData.sessionsBySpeaker
				: buildSessionsBySpeaker(sessionsPool, { lowercaseKeys: false })

			return featured.map(speaker => {
				const speakerSessions = sortSessionsByStart(sessionsForSpeaker(sessionsBySpeaker, speaker.code))
				return {
					...speaker,
					sessions: speakerSessions,
				}
			})
		},
	},
	methods: {
		getSpeakerLink(speaker) {
			if (this.eventUrl) {
				const base = (this.eventUrl || '').replace(/\/?$/, '/')
				return `${base}speakers/${speaker.code}/`
			}
			return this.generateSpeakerLinkUrl({speaker})
		},
		onSpeakerClick(event, speaker) {
			this.onSpeakerLinkClick(event, speaker)
		},
		getSessionLink(session) {
			const base = (this.eventUrl || '').replace(/\/?$/, '/')
			return session?.id ? `${base}talk/${session.id}/` : '#'
		},
		onSessionClick(event, session) {
			this.onSessionLinkClick(event, session)
		},
		getSessionStyle(session) {
			const track = typeof session?.track === 'object'
				? session.track
				: this.trackById[session?.track]
			return {
				'--session-color': track?.color || 'var(--pretalx-clr-primary)'
			}
		},
		formatSessionSlot(session) {
			const tz = this.scheduleData?.timezone
			const hasAmPm = this.scheduleData?.hasAmPm
			if (!tz || !session?.start || !session?.end) return ''
			const start = moment.isMoment(session.start) ? session.start : moment.tz(session.start, tz)
			const end = moment.isMoment(session.end) ? session.end : moment.tz(session.end, tz)
			const fmt = hasAmPm ? 'h:mm A' : 'HH:mm'
			return `${start.clone().tz(tz).format(fmt)} - ${end.clone().tz(tz).format(fmt)}`
		},
		formatSessionDateTime(session) {
			const tz = this.scheduleData?.timezone
			const hasAmPm = this.scheduleData?.hasAmPm
			if (!tz || !session?.start) return ''
			const start = moment.isMoment(session.start) ? session.start : moment.tz(session.start, tz)
			const fmt = hasAmPm ? 'MMM D, YYYY h:mm A' : 'MMM D, YYYY HH:mm'
			return start.clone().tz(tz).format(fmt)
		}
	}
}
</script>

<style lang="stylus">
.c-featured-speakers

	h3#featured-speakers-heading
		margin-top: 0px
		font-family: inherit
		font-size: 24px
		font-weight: 500
		line-height: 1.1
		color: inherit

	.featured-speakers-grid
		display: flex
		flex-wrap: wrap
		justify-content: center
		gap: 18px

	.featured-speaker-column
		/* Default for smaller devices */
		width: 400px
		max-width: 100%

		/* Desktop and large / mid tablets: use 350px */
		@media (min-width: 768px)
			width: 360px
			max-width: 100%

	.featured-speaker-card
		margin: 0
		border-radius: 6px
		overflow: hidden
		background: $clr-white
		border: 1px solid $clr-grey-300

	.featured-speaker-summary
		cursor: pointer
		list-style: none
		&::-webkit-details-marker
			display: none

		.thumbnail
			margin: 0
			padding: 0
			border: none
			background: transparent
			img
				width: 100%
				aspect-ratio: 1 / 1
				object-fit: cover
				border-radius: 6px
				display: block
			.caption
				padding: 10px 6px 12px
				h4
					margin: 8px 0 0
					color: $clr-primary-text-light
					font-size: 18px
					font-weight: 500
					line-height: 1.3
				.featured-speaker-preview-bio
					margin: 4px 0 0
					color: $clr-secondary-text-light
					font-size: 12px
					line-height: 1.35
					display: -webkit-box
					-webkit-line-clamp: 2
					line-clamp: 2
					-webkit-box-orient: vertical
					overflow: hidden
					overflow-wrap: anywhere
					text-overflow: ellipsis
					&.c-markdown-content
						font-size: inherit
						line-height: inherit
						color: inherit
						p, ul, ol, table, pre
							margin-top: 0.25em
							margin-bottom: 0.25em
							&:first-child
								margin-top: 0
							&:last-child
								margin-bottom: 0

	.featured-speaker-card[open] .featured-speaker-summary .thumbnail .caption .featured-speaker-preview-bio
		display: block
		-webkit-line-clamp: unset
		line-clamp: unset
		-webkit-box-orient: unset
		overflow: visible
		white-space: normal
		text-overflow: clip
		&.c-markdown-content
			display: block

	.avatar-placeholder
		width: 100%
		aspect-ratio: 1 / 1
		display: flex
		align-items: center
		justify-content: center
		background: $clr-grey-100
		color: $clr-grey-500
		svg
			width: 45%
			height: 45%

	.featured-speaker-details
		margin-top: 8px
		padding: 12px
		background: $clr-grey-100
		border-top: 1px solid $clr-grey-300

	.featured-speaker-divider
		margin: 12px 0 8px
		border-color: $clr-grey-300

	.featured-speaker-sessions
		margin-top: 0
		padding: 0
		h4
			margin: 0 0 10px
			color: $clr-primary-text-light
			font-size: 16px
			font-weight: 600

	.featured-speaker-session
		margin-bottom: 12px
		&:last-child
			margin-bottom: 0

	.featured-speaker-session-pending
		.featured-speaker-session-time
			color: var(--pretalx-clr-primary, var(--clr-primary))

	.featured-speaker-session-time
		display: block
		color: $clr-secondary-text-light
		margin-bottom: 4px
		font-size: 13px
		line-height: 1.35
		font-weight: 600

	.featured-speaker-session-link
		display: block
		background-color: var(--session-color, var(--pretalx-clr-primary))
		color: $clr-white
		border-radius: 4px
		padding: 9px 11px
		text-decoration: none
		&:hover
			opacity: 0.92
			text-decoration: none

	.featured-speaker-session-slot
		display: block
		font-size: 12px
		line-height: 1.2
		margin-bottom: 2px
		opacity: 0.92

	.featured-speaker-session-title
		display: block
		font-size: 14px
		font-weight: 600
		line-height: 1.3

	.featured-speaker-profile-link
		margin-top: 12px
		text-align: right
		a
			color: var(--pretalx-clr-primary, var(--clr-primary))
			text-decoration: none
			&:hover
				text-decoration: underline

	.featured-speakers-more
		margin-top: 12px
		text-align: center
		.more-link
			color: var(--pretalx-clr-primary, var(--clr-primary))
			text-decoration: none
			font-weight: 600
			&:hover
				text-decoration: underline
</style>

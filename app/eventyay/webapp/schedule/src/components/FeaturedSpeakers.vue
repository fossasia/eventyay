<template lang="pug">
.c-featured-speakers(v-if="featuredSpeakers.length")
	h3#featured-speakers-heading {{ t.featured_speakers }}
	.featured-speakers-grid
		.featured-speaker-column(v-for="speaker in featuredSpeakers", :key="speaker.code")
			details.featured-speaker-card
				summary.featured-speaker-summary
					.thumbnail
						img(
							v-if="speaker.avatar || speaker.avatar_url",
							:src="speaker.avatar || speaker.avatar_url",
							:alt="speaker.name || t.speaker_fallback",
							loading="lazy"
						)
						.avatar-placeholder(v-else)
							svg(viewBox="0 0 24 24")
								path(fill="currentColor", d="M12,1A5.8,5.8 0 0,1 17.8,6.8A5.8,5.8 0 0,1 12,12.6A5.8,5.8 0 0,1 6.2,6.8A5.8,5.8 0 0,1 12,1M12,15C18.63,15 24,17.67 24,21V23H0V21C0,17.67 5.37,15 12,15Z")
						.caption.text-center
							h4 {{ speaker.name || t.speaker_fallback }}
							p(v-if="speaker.biography") {{ speaker.biography }}
				.featured-speaker-details
					.featured-speaker-bio(v-if="speaker.biography") {{ speaker.biography }}
					template(v-if="speaker.sessions && speaker.sessions.length")
						hr.featured-speaker-divider
						.featured-speaker-sessions
							h4 {{ t.sessions }}
							.featured-speaker-session(v-for="session in speaker.sessions", :key="session.id")
								small.featured-speaker-session-time {{ formatSessionDateTime(session) }}
								a.featured-speaker-session-link(
									:href="getSessionLink(session)",
									:style="getSessionStyle(session)",
									@click="onSessionClick($event, session)"
								)
									span.featured-speaker-session-slot {{ formatSessionSlot(session) }}
									span.featured-speaker-session-title {{ getLocalizedString(session.title) }}
					.featured-speaker-profile-link
						a(:href="getSpeakerLink(speaker)", @click="onSpeakerClick($event, speaker)") {{ t.view_profile }}
	p.featured-speakers-more
		a.more-link(:href="moreSpeakersUrl") {{ t.more_speakers }}
</template>

<script>
import moment from 'moment-timezone'
import { getLocalizedString } from '../utils'

export default {
	name: 'FeaturedSpeakers',
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
		translationMessages: { default: () => ({}) }
	},
	data() {
		return {
			getLocalizedString,
		}
	},
	computed: {
		t() {
			const m = this.translationMessages || {}
			return {
				featured_speakers: m.featured_speakers || 'Featured Speakers',
				speaker_fallback: m.speaker_fallback || 'Speaker',
				sessions: m.sessions || 'Sessions',
				view_profile: m.view_profile || 'View speaker profile',
				more_speakers: m.more_speakers || 'More speakers',
			}
		},
		moreSpeakersUrl() {
			const base = (this.eventUrl || '').replace(/\/?$/, '/')
			return `${base}speakers/`
		},
		featuredSpeakers() {
			const schedule = this.scheduleData?.schedule
			const resolvedSessions = this.scheduleData?.sessions || []
			const rawTalks = schedule?.talks || []
			const timezone = this.scheduleData?.timezone || schedule?.timezone
			if (!schedule?.speakers?.length) return []
			const speakerCodeFromAny = (sp) => {
				if (!sp) return null
				if (typeof sp === 'string') return sp
				return sp.code || null
			}
			const featured = schedule.speakers
				.filter(s => s?.is_featured)
				.slice()
				.sort((a, b) => {
					const ap = Number.isFinite(a.featured_position) ? a.featured_position : 1e9
					const bp = Number.isFinite(b.featured_position) ? b.featured_position : 1e9
					if (ap !== bp) return ap - bp
					return (a.name || '').localeCompare(b.name || '')
				})

			const speakerByCode = (schedule.speakers || []).reduce((acc, s) => {
				if (s?.code) acc[s.code] = s
				return acc
			}, {})
			const trackById = (schedule.tracks || []).reduce((acc, t) => {
				if (t?.id != null) acc[t.id] = t
				return acc
			}, {})
			const roomById = (schedule.rooms || []).reduce((acc, r) => {
				if (r?.id != null) acc[r.id] = r
				return acc
			}, {})

			const normalizeRawTalk = (talk) => {
				const start = talk?.start && timezone ? moment.tz(talk.start, timezone) : null
				const end = talk?.end && timezone ? moment.tz(talk.end, timezone) : null
				const speakerCodes = (talk?.speakers || []).map(speakerCodeFromAny).filter(Boolean)
				return {
					id: talk?.code,
					title: talk?.title,
					start,
					end,
					speakers: speakerCodes
						.map(code => speakerByCode[code] || { code })
						.filter(Boolean),
					track: trackById[talk?.track],
					room: roomById[talk?.room],
					content_locale: talk?.content_locale,
				}
			}

			return featured.map(speaker => {
				let speakerSessions
				if (resolvedSessions.length) {
					speakerSessions = resolvedSessions
						.filter(sess => (sess.speakers || []).some(sp => speakerCodeFromAny(sp) === speaker.code))
						.slice()
						.sort((a, b) => (a.start && b.start ? a.start.diff(b.start) : 0))
				} else {
					speakerSessions = rawTalks
						.filter(t => (t?.speakers || []).some(sp => speakerCodeFromAny(sp) === speaker.code))
						.map(normalizeRawTalk)
						.filter(t => t?.start && t?.end)
						.sort((a, b) => a.start.diff(b.start))
				}
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
			const schedule = this.scheduleData?.schedule
			const track = typeof session?.track === 'object'
				? session.track
				: (schedule?.tracks || []).find(t => t?.id === session?.track)
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
	padding: 12px 0

	h3#featured-speakers-heading
		margin: 0 0 18px
		font-size: 20px
		font-weight: 600

	.featured-speakers-grid
		display: flex
		flex-wrap: wrap
		justify-content: center
		gap: 18px

	.featured-speaker-column
		width: 320px
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
					font-size: 22px
					font-weight: 600
					line-height: 1.2
				p
					margin: 4px 0 0
					color: $clr-secondary-text-light
					font-size: 12px
					line-height: 1.35
					display: -webkit-box
					-webkit-line-clamp: 3
					-webkit-box-orient: vertical
					overflow: hidden

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

	.featured-speaker-bio
		color: $clr-primary-text-light
		font-size: 13px
		line-height: 1.55
		white-space: pre-wrap

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

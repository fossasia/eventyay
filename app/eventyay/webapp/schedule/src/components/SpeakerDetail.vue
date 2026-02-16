<template lang="pug">
.c-speaker-detail(v-scrollbar.y="")
	.speaker-wrapper(v-if="resolvedSpeaker")
		.speaker-header
			.speaker-avatar
				img(v-if="resolvedSpeaker.avatar || resolvedSpeaker.avatar_url", :src="resolvedSpeaker.avatar || resolvedSpeaker.avatar_url", :alt="resolvedSpeaker.name")
				.avatar-placeholder(v-else)
					svg(viewBox="0 0 24 24")
						path(fill="currentColor", d="M12,1A5.8,5.8 0 0,1 17.8,6.8A5.8,5.8 0 0,1 12,12.6A5.8,5.8 0 0,1 6.2,6.8A5.8,5.8 0 0,1 12,1M12,15C18.63,15 24,17.67 24,21V23H0V21C0,17.67 5.37,15 12,15Z")
			.speaker-title
				h2 {{ resolvedSpeaker.name || 'Speaker' }}
				a.btn-ical(v-if="icalUrl", :href="icalUrl", download)
					svg(viewBox="0 0 16 16", width="16", height="16", fill="currentColor")
						path(d="M11 6.5a.5.5 0 0 1 .5-.5h1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-1a.5.5 0 0 1-.5-.5v-1zm-3 0a.5.5 0 0 1 .5-.5h1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-1a.5.5 0 0 1-.5-.5v-1zm-5 3a.5.5 0 0 1 .5-.5h1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-1a.5.5 0 0 1-.5-.5v-1zm3 0a.5.5 0 0 1 .5-.5h1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-1a.5.5 0 0 1-.5-.5v-1z")
						path(d="M3.5 0a.5.5 0 0 1 .5.5V1h8V.5a.5.5 0 0 1 1 0V1h1a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V3a2 2 0 0 1 2-2h1V.5a.5.5 0 0 1 .5-.5zM1 4v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V4H1z")
					|  iCal
		markdown-content.biography(v-if="resolvedSpeaker.biography", :markdown="resolvedSpeaker.biography")
		.speaker-sessions(v-if="resolvedSessions && resolvedSessions.length")
			h3 Sessions
			session(
				v-for="s in resolvedSessions",
				:key="s.id",
				:session="s",
				:showDate="true",
				:now="resolvedNow",
				:timezone="resolvedTimezone",
				:locale="locale",
				:hasAmPm="resolvedHasAmPm",
				:faved="s.id && resolvedFavs.includes(s.id)",
				:onHomeServer="onHomeServer",
				@fav="onFav(s.id)",
				@unfav="onUnfav(s.id)"
			)
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>

<script>
import moment from 'moment-timezone'
import MarkdownContent from './MarkdownContent.vue'
import Session from './Session.vue'

export default {
	name: 'SpeakerDetail',
	components: { MarkdownContent, Session },
	inject: {
		eventUrl: { default: null },
		scheduleData: { default: null },
		scheduleFav: { default: null },
		scheduleUnfav: { default: null },
		generateSessionLinkUrl: {
			default() {
				return ({session}) => `#talk/${session.id}`
			}
		},
		onSessionLinkClick: {
			default() {
				return () => {}
			}
		}
	},
	props: {
		speaker: Object,
		speakerId: String,
		sessions: {
			type: Array,
			default: () => []
		},
		now: Object,
		timezone: String,
		locale: String,
		hasAmPm: {
			type: Boolean,
			default: false
		},
		favs: {
			type: Array,
			default: () => []
		},
		onHomeServer: Boolean
	},
	emits: ['fav', 'unfav'],
	computed: {
		resolvedSpeaker() {
			if (this.speaker) return this.speaker
			if (this.speakerId && this.scheduleData) {
				const schedule = this.scheduleData.schedule
				if (schedule?.speakers) {
					return schedule.speakers.find(s => s.code === this.speakerId) || null
				}
				const sessions = this.scheduleData.sessions || []
				for (const session of sessions) {
					if (!session.speakers) continue
					const found = session.speakers.find(s => s.code === this.speakerId)
					if (found) return found
				}
			}
			return null
		},
		resolvedSessions() {
			if (this.sessions?.length) return this.sessions
			const id = this.speakerId || this.speaker?.code
			if (id && this.scheduleData) {
				return (this.scheduleData.sessions || []).filter(s =>
					s.speakers?.some(sp => sp.code === id)
				)
			}
			return []
		},
		resolvedFavs() {
			if (this.favs?.length) return this.favs
			return this.scheduleData?.favs || []
		},
		resolvedNow() {
			return this.now || this.scheduleData?.now || moment()
		},
		resolvedTimezone() {
			return this.timezone || this.scheduleData?.timezone || moment.tz.guess()
		},
		resolvedHasAmPm() {
			if (this.hasAmPm !== undefined && this.hasAmPm !== false) return this.hasAmPm
			if (this.scheduleData?.hasAmPm !== undefined) return this.scheduleData.hasAmPm
			return new Intl.DateTimeFormat(undefined, {hour: 'numeric'}).resolvedOptions().hour12
		},
		icalUrl() {
			const code = this.speakerId || this.speaker?.code || this.resolvedSpeaker?.code
			if (!code || !this.eventUrl) return null
			return `${this.eventUrl}speakers/${code}/talks.ics`
		}
	},
	methods: {
		onFav(id) {
			if (this.scheduleFav) this.scheduleFav(id)
			this.$emit('fav', id)
		},
		onUnfav(id) {
			if (this.scheduleUnfav) this.scheduleUnfav(id)
			this.$emit('unfav', id)
		}
	}
}
</script>

<style lang="stylus">
.c-speaker-detail
	display: flex
	flex-direction: column
	min-height: 0
	background-color: $clr-white
	.speaker-wrapper
		flex: auto
		display: flex
		flex-direction: column
		max-width: 800px
		margin: 0 auto
		padding: 16px
		width: 100%
	.speaker-header
		display: flex
		align-items: center
		gap: 16px
		margin-bottom: 16px
		h2
			margin: 0
	.speaker-title
		display: flex
		flex-direction: column
		gap: 8px
		h2
			margin: 0
	.btn-ical
		display: inline-flex
		align-items: center
		gap: 6px
		padding: 6px 14px
		border: 1px solid $clr-grey-400
		border-radius: 4px
		font-size: 14px
		color: $clr-primary-text-light
		text-decoration: none
		cursor: pointer
		background: transparent
		align-self: flex-start
		&:hover
			border-color: var(--pretalx-clr-primary, $clr-primary)
			color: var(--pretalx-clr-primary, $clr-primary)
	.speaker-avatar
		flex-shrink: 0
		width: 128px
		height: 128px
		img, .avatar-placeholder
			width: 128px
			height: 128px
			border-radius: 50%
			object-fit: cover
			box-shadow: rgba(0, 0, 0, 0.12) 0px 1px 3px 0px, rgba(0, 0, 0, 0.24) 0px 1px 2px 0px
		.avatar-placeholder
			background: rgba(0,0,0,0.1)
			display: flex
			align-items: center
			justify-content: center
			svg
				width: 60%
				height: 60%
				color: rgba(0,0,0,0.3)
	.biography
		margin-bottom: 16px
		font-size: 16px
	.speaker-sessions
		h3
			margin-bottom: 8px
		.c-linear-schedule-session
			box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.08)
			border-radius: 6px
			margin: 8px 0
	@media (max-width: 768px)
		.speaker-header
			flex-direction: column
			align-items: flex-start
		.speaker-avatar
			width: 96px
			height: 96px
			img, .avatar-placeholder
				width: 96px
				height: 96px
</style>

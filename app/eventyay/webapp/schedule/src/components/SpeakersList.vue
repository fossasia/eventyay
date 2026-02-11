<template lang="pug">
.c-speakers-list(v-scrollbar.y="")
	.speakers-grid(v-if="sortedSpeakers.length")
		a.speaker-card(
			v-for="speaker in sortedSpeakers",
			:key="speaker.code",
			:href="getSpeakerLink(speaker)",
			@click="onSpeakerClick($event, speaker)"
		)
			.speaker-avatar
				img(v-if="speaker.avatar || speaker.avatar_url", :src="speaker.avatar || speaker.avatar_url", :alt="speaker.name")
				.avatar-placeholder(v-else)
					svg(viewBox="0 0 24 24")
						path(fill="currentColor", d="M12,1A5.8,5.8 0 0,1 17.8,6.8A5.8,5.8 0 0,1 12,12.6A5.8,5.8 0 0,1 6.2,6.8A5.8,5.8 0 0,1 12,1M12,15C18.63,15 24,17.67 24,21V23H0V21C0,17.67 5.37,15 12,15Z")
			.speaker-info
				.name {{ speaker.name || 'Speaker' }}
				.biography(v-if="speaker.biography") {{ speaker.biography }}
				.sessions-list(v-if="speaker.sessions && speaker.sessions.length")
					span.session-title(v-for="(session, idx) in speaker.sessions", :key="session.id")
						| {{ getLocalizedString(session.title) }}
						span.separator(v-if="idx < speaker.sessions.length - 1") ,&nbsp;
	.empty(v-else)
		| No speakers found.
</template>

<script>
import { getLocalizedString } from '../utils'

export default {
	name: 'SpeakersList',
	inject: {
		scheduleData: { default: null },
		generateSpeakerLinkUrl: {
			default() {
				return ({speaker}) => `#speaker/${speaker.code}`
			}
		},
		onSpeakerLinkClick: {
			default() {
				return () => {}
			}
		}
	},
	props: {
		speakers: {
			type: Array,
			default: () => []
		}
	},
	data() {
		return {
			getLocalizedString
		}
	},
	computed: {
		resolvedSpeakers() {
			if (this.speakers?.length) return this.speakers
			if (this.scheduleData) {
				const schedule = this.scheduleData.schedule
				const sessions = this.scheduleData.sessions || []
				return (schedule?.speakers || []).map(speaker => ({
					...speaker,
					sessions: sessions.filter(s =>
						s.speakers?.some(sp => sp.code === speaker.code)
					)
				}))
			}
			return []
		},
		sortedSpeakers() {
			return [...this.resolvedSpeakers].sort((a, b) =>
				(a.name || '').localeCompare(b.name || '')
			)
		}
	},
	methods: {
		getSpeakerLink(speaker) {
			return this.generateSpeakerLinkUrl({speaker})
		},
		onSpeakerClick(event, speaker) {
			this.onSpeakerLinkClick(event, speaker)
		}
	}
}
</script>

<style lang="stylus">
.c-speakers-list
	display: flex
	flex-direction: column
	min-height: 0
	.speakers-grid
		display: flex
		flex-direction: column
		padding: 16px
		gap: 12px
	.speaker-card
		display: flex
		align-items: flex-start
		gap: 12px
		padding: 12px
		border: 1px solid $clr-grey-300
		border-radius: 6px
		text-decoration: none
		color: $clr-primary-text-light
		cursor: pointer
		&:hover
			background-color: $clr-grey-100
			.name
				color: var(--pretalx-clr-primary, var(--clr-primary))
				text-decoration: underline
	.speaker-avatar
		flex-shrink: 0
		width: 64px
		height: 64px
		img, .avatar-placeholder
			width: 64px
			height: 64px
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
	.speaker-info
		flex: 1
		min-width: 0
		.name
			font-weight: 600
			font-size: 16px
			margin-bottom: 4px
		.biography
			font-size: 14px
			color: $clr-secondary-text-light
			display: -webkit-box
			-webkit-line-clamp: 3
			-webkit-box-orient: vertical
			overflow: hidden
			margin-bottom: 4px
		.sessions-list
			font-size: 13px
			color: $clr-secondary-text-light
			.session-title
				font-style: italic
	.empty
		padding: 32px
		text-align: center
		color: $clr-secondary-text-light
</style>

<template lang="pug">
.c-speaker-detail(v-scrollbar.y="")
	.speaker-wrapper(v-if="speaker")
		.speaker-header
			.speaker-avatar
				img(v-if="speaker.avatar || speaker.avatar_url", :src="speaker.avatar || speaker.avatar_url", :alt="speaker.name")
				.avatar-placeholder(v-else)
					svg(viewBox="0 0 24 24")
						path(fill="currentColor", d="M12,1A5.8,5.8 0 0,1 17.8,6.8A5.8,5.8 0 0,1 12,12.6A5.8,5.8 0 0,1 6.2,6.8A5.8,5.8 0 0,1 12,1M12,15C18.63,15 24,17.67 24,21V23H0V21C0,17.67 5.37,15 12,15Z")
			h2 {{ speaker.name || 'Speaker' }}
		markdown-content.biography(v-if="speaker.biography", :markdown="speaker.biography")
		.speaker-sessions(v-if="sessions && sessions.length")
			h3 Sessions
			session(
				v-for="s in sessions",
				:key="s.id",
				:session="s",
				:showDate="true",
				:now="now",
				:timezone="timezone",
				:locale="locale",
				:hasAmPm="hasAmPm",
				:faved="s.id && favs.includes(s.id)",
				:onHomeServer="onHomeServer",
				@fav="$emit('fav', s.id)",
				@unfav="$emit('unfav', s.id)"
			)
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>

<script>
import MarkdownContent from './MarkdownContent.vue'
import Session from './Session.vue'

export default {
	name: 'SpeakerDetail',
	components: { MarkdownContent, Session },
	props: {
		speaker: Object,
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
	emits: ['fav', 'unfav']
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

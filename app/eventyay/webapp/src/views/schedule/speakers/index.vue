<template lang="pug">
.c-schedule-speakers
	h1 {{ $t('schedule/speakers/index:header') }}
	bunt-progress-circular(v-if="!speakers || !schedule", size="huge", :page="true")
	scrollbars(v-else, y="")
		.speakers
			router-link.speaker(v-for="speaker of speakers", :to="speaker.attendee ? {name: '', params: {}} : { name: 'schedule:speaker', params: { speakerId: speaker.code } }")
				img.avatar(v-if="speaker.avatar || speaker.avatar_url", :src="speaker.avatar || speaker.avatar_url")
				identicon(v-else, :user="{id: speaker.code, profile: {display_name: speaker.name || 'Speaker'}}")
				.content
					.name(:class="{'no-name': !speaker.name}") {{ speaker.name || 'Speaker name not provided' }}
					p.biography {{ speaker.biography }}
					.sessions(v-if="speaker.sessions.length && speaker.sessions.some(s => s)")
						h2 {{ $t('schedule/speakers/index:speaker-sessions:header') }}:
						.session(v-for="session of speaker.sessions")
							.title {{ session.title }}
</template>
<script>
// TODOs
// search
import { mapGetters, mapState } from 'vuex'
import Identicon from 'components/Identicon'

export default {
	components: { Identicon },
	data() {
		return {
			speakers: null
		}
	},
	computed: {
		...mapState('schedule', ['schedule']),
		...mapGetters('schedule', ['sessions', 'sessionsLookup'])
	},
	async created() {
		this.$watch('schedule', (schedule) => {
			if (!schedule) return
			this.speakers = schedule.speakers.map(speaker => ({
				...speaker,
				sessions: this.sessions.filter(session => 
					session.speakers && session.speakers.some(s => s && s.code === speaker.code)
				)
			})).sort((a, b) => (a.name || '\uFFFF').localeCompare(b.name || '\uFFFF'))
		}, { immediate: true })
	}
}
</script>
<style lang="stylus">
.c-schedule-speakers
	flex: auto
	min-height: 0
	display: flex
	flex-direction: column
	align-items: center
	.scroll-content
		display: flex
		flex-direction: column
		max-height: 88vh
		align-items: center
		> *
			width: @css{min(920px, 100%)}
	.speaker
		color: $clr-primary-text-light
		display: flex
		gap: 16px
		cursor: pointer
		padding: 8px
		border-left: border-separator()
		border-right: border-separator()
		border-bottom: border-separator()
		&:first-child
			border-top: border-separator()
		&:hover
			background-color: $clr-grey-200
		img
			flex: none
			border-radius: 50%
			height: 92px
			width: @height
			object-fit: cover
		.name
			font-weight: 500
			font-size: 16px
			&.no-name
				color: $clr-secondary-text-light
				font-style: italic
		.biography
			display: -webkit-box
			-webkit-box-orient: vertical
			-webkit-line-clamp: 3
			overflow: hidden
	.sessions
		display: flex
		flex-direction: column
		gap: 8px
		margin-bottom: 8px
		h2
			font-weight: 500
			font-size: 16px
			margin: 0
</style>

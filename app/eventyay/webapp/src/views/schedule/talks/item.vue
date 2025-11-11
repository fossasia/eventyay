<template lang="pug">
.c-schedule-talk(v-scrollbar.y="")
	.talk-wrapper(v-if="talk")
		.talk
			h1 {{ talk.title }}
			//- TODO choose locale
			.info {{ datetime }} {{ roomName }}
			markdown-content.abstract(:markdown="talk.abstract")
			markdown-content.description(:markdown="talk.description")
			.downloads(v-if="talk.resources && talk.resources.length > 0")
				h2 {{ $t("schedule/talks:downloads-headline:text") }}
				a.download(v-for="{resource, description} of talk.resources", :href="getAbsoluteResourceUrl(resource)", target="_blank")
					.mdi(:class="`mdi-${getIconByFileEnding(resource)}`")
					.filename {{ description }}
			bunt-link-button.btn-create.router-link.stage(v-if="getRoomIdByName(roomName)", :to="{name: 'room', params: {roomId: getRoomIdByName(roomName)}}") Join room
		.speakers(v-if="talk.speakers.length > 0")
			.header {{ $t('schedule/talks/item:speakers:header', {count: talk.speakers.length})}}
			.speakers-list
				.speaker(v-for="speaker of talk.speakers")
					router-link.speaker-link(:to="{name: 'schedule:speaker', params: {speakerId: speaker.code}}")
						img.avatar-circle(v-if="speaker.avatar || speaker.avatar_url", :src="speaker.avatar || speaker.avatar_url")
						identicon.avatar-circle(v-else, :user="{id: speaker.code, profile: {display_name: speaker.name || 'Speaker'}}")
						.name(:class="{'no-name': !speaker.name}") {{ speaker.name || 'Speaker name not provided' }}
					markdown-content.biography(:markdown="speaker.biography")
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import { mapGetters, mapState } from 'vuex'
import moment from 'lib/timetravelMoment'
import MarkdownContent from 'components/MarkdownContent'
import Identicon from 'components/Identicon'
import { getIconByFileEnding } from 'lib/filetypes'

export default {
	components: {MarkdownContent, Identicon},
	props: {
		talkId: String
	},
	data() {
		return {
			talk: null
		}
	},
	computed: {
		...mapState(['rooms']),
		...mapGetters('schedule', ['pretalxApiBaseUrl', 'sessions']),
		datetime() {
			if (!this.talk) { return '' }
			return moment(this.talk.start).format('L LT') + ' - ' + moment(this.talk.end).format('LT')
		},
		roomName() {
			if (!this.talk) { return '' }
			return this.$localize(this.talk.room?.name || this.talk.room)
		}
	},
	watch: {
		sessions: {
			handler() {
				if (!this.sessions) return
				if (this.talk) return
				this.talk = this.sessions.find(session => session.id === this.talkId)
			},
			immediate: true
		}
	},
	mounted() {
		this.$nextTick(() => {
		})
	},
	methods: {
		getIconByFileEnding,
		getAbsoluteResourceUrl(resource) {
			if (!this.pretalxApiBaseUrl) return resource
			const base = (new URL(this.pretalxApiBaseUrl)).origin
			return new URL(resource, base)
		},
		getRoomIdByName(roomName) {
			const room = this.rooms.find(r => r.name === roomName)
			return room ? room.id : null
		}
	}
}
</script>
<style lang="stylus">
// TODO larger font size for body text?
.c-schedule-talk
	display: flex
	flex-direction: column
	background-color: $clr-white
	.talk-wrapper
		flex: auto
		display: flex
		justify-content: center
	.talk
		flex: none
		margin: 16px 0 16px 16px
		max-width: 720px
		h1
			margin-bottom: 0
		.info
			font-size: 18px
			color: $clr-secondary-text-light
		.abstract
			margin: 16px 0 0 0
			font-size: 16px
			font-weight: 600
	.downloads
		border: border-separator()
		border-radius: 4px
		display: flex
		flex-direction: column
		margin-top: 16px
		h2
			margin: 4px 8px
		.download
			display: flex
			align-items: center
			height: 56px
			font-weight: 600
			font-size: 16px
			border-top: border-separator()
			&:hover
				background-color: $clr-grey-100
				text-decoration: underline
			.mdi
				font-size: 36px
				margin: 0 4px
	.btn-create
		themed-button-primary()
	.speakers
		width: 280px
		margin: 32px 16px
		display: flex
		flex-direction: column
		border: border-separator()
		border-radius: 4px
		align-self: flex-start
		.header
			border-bottom: border-separator()
			padding: 8px
		.speaker
			padding: 8px
			display: flex
			flex-direction: column
			.speaker-link
				display: flex
				align-items: center
				gap: 8px
				text-decoration: none
				color: $clr-primary-text-light
				&:hover
					.name
						color: var(--clr-primary)
						text-decoration: underline
			.avatar-circle
				border-radius: 50%
				height: 32px
				width: 32px
				flex-shrink: 0
				object-fit: cover
			.name
				font-weight: 600
				&.no-name
					color: $clr-secondary-text-light
					font-style: italic
	+below('m')
		.talk-wrapper
			display: block
		.speakers
			width: auto
		.talk
			max-width: 100%
			margin: 16px
</style>

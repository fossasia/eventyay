<template lang="pug">
.c-talk-detail(v-scrollbar.y="")
	.talk-wrapper(v-if="resolvedTalk")
		.talk
			.talk-header
				h1 {{ getLocalizedString(resolvedTalk.title) }}
				.header-actions
					export-dropdown.talk-export(v-if="talkExportOptions.length", :options="talkExportOptions")
					.button-container(:class="isFaved ? 'faved' : ''")
						fav-button(@toggleFav="toggleFav")
			.info {{ datetime }} {{ roomName }}
			markdown-content.abstract(v-if="resolvedTalk.abstract", :markdown="resolvedTalk.abstract")
			markdown-content.description(v-if="resolvedTalk.description", :markdown="resolvedTalk.description")
			.downloads(v-if="resolvedTalk.resources && resolvedTalk.resources.length > 0")
				h2 {{ t.downloads }}
				a.download(v-for="{resource, description} of resolvedTalk.resources", :href="getAbsoluteResourceUrl(resource)", target="_blank")
					.mdi(:class="`mdi-${getIconByFileEnding(resource)}`")
					.filename {{ description }}

			slot(name="actions")
				a.join-room-btn(v-if="showJoinRoom && computedJoinRoomLink", :href="computedJoinRoomLink", @click="onJoinRoomClick") {{ t.join_room }}
		.speakers(v-if="resolvedTalk.speakers && resolvedTalk.speakers.length > 0")
			.header {{ t.speakers }} ({{ resolvedTalk.speakers.length }})
			.speakers-list
				.speaker(v-for="speaker of resolvedTalk.speakers", :key="speaker.code")
					a.speaker-link(:href="getSpeakerLink(speaker)", @click="onSpeakerClick($event, speaker)")
						img.avatar-circle(v-if="speaker.avatar || speaker.avatar_url", :src="speaker.avatar || speaker.avatar_url")
						.avatar-placeholder.avatar-circle(v-else)
							svg(viewBox="0 0 24 24")
								path(fill="currentColor", d="M12,1A5.8,5.8 0 0,1 17.8,6.8A5.8,5.8 0 0,1 12,12.6A5.8,5.8 0 0,1 6.2,6.8A5.8,5.8 0 0,1 12,1M12,15C18.63,15 24,17.67 24,21V23H0V21C0,17.67 5.37,15 12,15Z")
						.name(:class="{'no-name': !speaker.name}") {{ speaker.name || t.speaker_name_not_provided }}
					markdown-content.biography(v-if="speaker.biography", :markdown="speaker.biography")
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>

<script>
import moment from 'moment-timezone'
import { getLocalizedString, getIconByFileEnding } from '../utils'
import MarkdownContent from './MarkdownContent.vue'
import FavButton from './FavButton.vue'
import ExportDropdown from './ExportDropdown.vue'

export default {
	name: 'TalkDetail',
	components: { MarkdownContent, FavButton, ExportDropdown },
	inject: {
		scheduleData: { default: null },
		scheduleFav: {
			default() {
				return () => {}
			}
		},
		scheduleUnfav: {
			default() {
				return () => {}
			}
		},
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
		showJoinRoom: { default: false },
		getJoinRoomLink: { default: () => () => '' },
		translationMessages: { default: () => ({}) }
	},
	props: {
		talk: Object,
		talkId: String,
		baseUrl: {
			type: String,
			default: ''
		}
	},
	emits: ['joinRoom'],
	data() {
		return {
			getLocalizedString,
			getIconByFileEnding
		}
	},
	computed: {
		t() {
			const m = this.translationMessages || {}
			return {
				join_room: m.join_room || 'Join room',
				speaker_name_not_provided: m.speaker_name_not_provided || 'Speaker name not provided',
				downloads: m.downloads || 'Downloads',
				speakers: m.speakers || 'Speakers',
			}
		},
		resolvedTalk() {
			if (this.talk) return this.talk
			if (this.talkId && this.scheduleData) {
				const sessions = this.scheduleData.sessions || []
				return sessions.find(s => s.id === this.talkId) || null
			}
			return null
		},
		computedJoinRoomLink() {
			if (!this.resolvedTalk) return ''
			return this.getJoinRoomLink(this.resolvedTalk) || ''
		},
		isFaved() {
			if (!this.resolvedTalk) return false
			const favs = this.scheduleData?.favs || []
			return favs.includes(this.resolvedTalk.id)
		},
		datetime() {
			if (!this.resolvedTalk) return ''
			return moment(this.resolvedTalk.start).format('L LT') + ' - ' + moment(this.resolvedTalk.end).format('LT')
		},
		roomName() {
			if (!this.resolvedTalk) return ''
			const room = this.resolvedTalk.room
			if (!room) return ''
			if (typeof room === 'string') return room
			return getLocalizedString(room.name || room)
		},
		talkExportOptions() {
			const exporters = this.resolvedTalk?.exporters
			if (!exporters) return []
			const qr = exporters.qrcodes || {}
			const items = [
				{ id: 'google_calendar', label: 'Add to Google Calendar', url: exporters.google_calendar, icon: 'fa-google', qrcode_svg: qr.google_calendar },
				{ id: 'webcal', label: 'Add to Other Calendar', url: exporters.webcal, icon: 'fa-calendar', qrcode_svg: qr.webcal },
				{ id: 'ics', label: 'iCal', url: exporters.ics, icon: 'fa-calendar', qrcode_svg: qr.ics },
				{ id: 'json', label: 'JSON (frab compatible)', url: exporters.json, icon: 'fa-code', qrcode_svg: qr.json },
				{ id: 'xml', label: 'XML (frab compatible)', url: exporters.xml, icon: 'fa-code', qrcode_svg: qr.xml },
				{ id: 'xcal', label: 'XCal (frab compatible)', url: exporters.xcal, icon: 'fa-calendar', qrcode_svg: qr.xcal },
			].filter(o => o.url)

			return items
		}
	},
	methods: {
		getAbsoluteResourceUrl(resource) {
			if (!this.baseUrl) return resource
			try {
				const base = (new URL(this.baseUrl)).origin
				return new URL(resource, base).href
			} catch {
				return resource
			}
		},
		getSpeakerLink(speaker) {
			return this.generateSpeakerLinkUrl({speaker})
		},
		onSpeakerClick(event, speaker) {
			this.onSpeakerLinkClick(event, speaker)
		},
		onJoinRoomClick(event) {
			this.$emit('joinRoom', event)
		},
		toggleFav() {
			if (!this.resolvedTalk) return
			if (this.isFaved) {
				this.scheduleUnfav(this.resolvedTalk.id)
			} else {
				this.scheduleFav(this.resolvedTalk.id)
			}
		}
	}
}
</script>

<style lang="stylus">
.c-talk-detail
	display: flex
	flex-direction: column
	background-color: $clr-white
	.talk-wrapper
		flex: auto
		display: flex
		flex-direction: column
		align-items: center
	.talk
		flex: none
		margin: 16px
		max-width: 720px
		width: 100%
		.talk-header
			display: flex
			align-items: flex-start
			gap: 8px
			h1
				flex: 1
				margin-bottom: 0
			.header-actions
				display: flex
				align-items: center
				gap: 4px
				flex-shrink: 0
				margin-top: 4px
			.button-container
				flex-shrink: 0
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
			text-decoration: none
			color: $clr-primary-text-light
			&:hover
				background-color: $clr-grey-100
				text-decoration: underline
			.mdi
				font-size: 36px
				margin: 0 4px

	.join-room-btn
		display: inline-block
		margin-top: 16px
		padding: 8px 24px
		border-radius: 4px
		font-weight: 600
		text-decoration: none
		color: $clr-white
		background-color: var(--clr-primary)
		&:hover
			opacity: 0.9
	.speakers
		max-width: 720px
		width: 100%
		margin: 0 16px 32px
		display: flex
		flex-direction: column
		border: border-separator()
		border-radius: 4px
		align-self: center
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
			.avatar-placeholder.avatar-circle
				background: rgba(0,0,0,0.1)
				display: flex
				align-items: center
				justify-content: center
				svg
					width: 60%
					height: 60%
					color: rgba(0,0,0,0.3)
			.name
				font-weight: 600
				&.no-name
					color: $clr-secondary-text-light
					font-style: italic
	@media (max-width: 768px)
		.speakers
			margin: 0 16px 16px
		.talk
			max-width: 100%
</style>

<template lang="pug">
dialog.pretalx-modal#session-modal(ref="modal", @click.stop="close()")
	.dialog-inner(@click.stop="")
		button.close-button(@click="close()") ✕
		template(v-if="modalContent && modalContent.contentType === 'session'")
			h3 {{ modalContent.contentObject.title }}
				.button-container(:class="isFaved ? 'faved' : ''")
					fav-button(@toggleFav="$emit('toggleFav', modalContent.contentObject.id)")

			.card-content
				.facts
					.time
						span {{ modalContent.contentObject.start.clone().tz(currentTimezone).format('dddd, D MMMM') }}, {{ getSessionTime(modalContent.contentObject, currentTimezone, locale, hasAmPm).time }}
						span.ampm(v-if="getSessionTime(modalContent.contentObject, currentTimezone, locale, hasAmPm).ampm") {{ getSessionTime(modalContent.contentObject, currentTimezone, locale, hasAmPm).ampm }}
					.room(v-if="modalContent.contentObject.room") {{ getLocalizedString(modalContent.contentObject.room.name) }}
					.track(v-if="modalContent.contentObject.track", :style="{ color: modalContent.contentObject.track.color }") {{ getLocalizedString(modalContent.contentObject.track.name) }}
					export-dropdown.session-export-area(v-if="talkExportOptions.length", :options="talkExportOptions")
				.text-content
					.recording-embed(v-if="modalContent.contentObject.recording_iframe", v-html="modalContent.contentObject.recording_iframe")
					.abstract(v-if="modalContent.contentObject.abstract", v-html="markdownIt.render(modalContent.contentObject.abstract)")
					template(v-if="modalContent.contentObject.isLoading")
						bunt-progress-circular(size="big", :page="true")
					template(v-else)
						hr(v-if="(modalContent.contentObject.abstract?.length > 0) && (modalContent.contentObject.apiContent?.description?.length > 0)")
						.description(v-if="modalContent.contentObject.apiContent?.description?.length > 0", v-html="markdownIt.render(modalContent.contentObject.apiContent.description)")
						template(v-if="shortAnswers.length > 0 || iconAnswers.length > 0")
							hr
							.answers
								.icon-group(v-if="iconAnswers.length > 0")
									.icon-link(v-for="answer in iconAnswers", :key="answer.id")
										a(:href="answer.answer", target="_blank", rel="noopener noreferrer")
											img(v-if="answer.question.icon && remoteApiUrl", :src="`${remoteApiUrl}questions/${answer.question.id}/icon/`", :alt="getLocalizedString(answer.question.question)", width="16", height="16")
											span(v-else) {{ getLocalizedString(answer.question.question) }}
								.inline-answer(v-for="answer in shortAnswers", :key="answer.id")
									span.question
										strong {{ getLocalizedString(answer.question.question) }}:
									span.answer(v-if="answer.question.variant === 'file'")
										i.fa.fa-file-o
										a(v-if="answer.answer_file", :href="answer.answer_file.url") {{ answer.answer_file }}
										span(v-else) {{ t.no_file_provided }}
									span.answer(v-else-if="answer.question.variant === 'boolean'") {{ answer.answer ? t.yes : t.no }}
									span.answer(v-else-if="answer.answer", v-html="markdownIt.render(answer.answer)")
									span.answer(v-else) {{ t.no_response }}
						.downloads(v-if="modalContent.contentObject.resources && modalContent.contentObject.resources.length > 0")
							hr
							h4 {{ t.downloads }}
							a.download(v-for="{resource, description} of modalContent.contentObject.resources", :href="resource", target="_blank")
								.mdi(:class="`mdi-${getIconByFileEnding(resource)}`")
								.filename {{ description }}
						a.join-room-btn(v-if="showJoinRoom && computedJoinRoomLink", :href="computedJoinRoomLink", @click="$emit('joinRoom', $event)") {{ t.join_room }}
			.speakers(v-if="modalContent.contentObject.speakers")
				a.speaker.inner-card(v-for="speaker in modalContent.contentObject.speakers", @click="handleSpeakerClick(speaker, $event)", :href="`#speakers/${speaker.code}`", :key="speaker.code")
					.img-wrapper
						img(v-if="speaker.avatar", :src="speaker.avatar", :alt="speaker.name")
						.avatar-placeholder(v-else)
							svg(viewBox="0 0 24 24")
								path(fill="currentColor", d="M12,1A5.8,5.8 0 0,1 17.8,6.8A5.8,5.8 0 0,1 12,12.6A5.8,5.8 0 0,1 6.2,6.8A5.8,5.8 0 0,1 12,1M12,15C18.63,15 24,17.67 24,21V23H0V21C0,17.67 5.37,15 12,15Z")
					.inner-card-content
						span {{ speaker.name }}
						p.biography(v-if="speaker.apiContent?.biography?.length > 0", v-html="markdownIt.render(speaker.apiContent.biography)")
		template(v-if="modalContent && modalContent.contentType === 'speaker'")
			.speaker-details
				.speaker-header
					.speaker-avatar
						img(v-if="modalContent.contentObject.avatar", :src="modalContent.contentObject.avatar", :alt="modalContent.contentObject.name")
						.avatar-placeholder(v-else)
							svg(viewBox="0 0 24 24")
								path(fill="currentColor", d="M12,1A5.8,5.8 0 0,1 17.8,6.8A5.8,5.8 0 0,1 12,12.6A5.8,5.8 0 0,1 6.2,6.8A5.8,5.8 0 0,1 12,1M12,15C18.63,15 24,17.67 24,21V23H0V21C0,17.67 5.37,15 12,15Z")
					.speaker-title
						h3 {{ modalContent.contentObject.name }}
						export-dropdown.speaker-export(v-if="speakerExportOptions.length", :options="speakerExportOptions")
				.speaker-content.card-content
					template(v-if="modalContent.contentObject.isLoading")
						bunt-progress-circular(size="big", :page="true")
					template(v-else)
						.biography(v-if="modalContent.contentObject.apiContent?.biography?.length > 0", v-html="markdownIt.render(modalContent.contentObject.apiContent.biography)")
						.answers(v-if="shortAnswers.length > 0 || iconAnswers.length > 0")
							hr
							.icon-group(v-if="iconAnswers.length > 0")
								.icon-link(v-for="answer in iconAnswers", :key="answer.id")
									a(:href="answer.answer", target="_blank", rel="noopener noreferrer")
										img(v-if="answer.question.icon && remoteApiUrl", :src="`${remoteApiUrl}questions/${answer.question.id}/icon/`", :alt="getLocalizedString(answer.question.question)", width="16", height="16")
										span(v-else) {{ getLocalizedString(answer.question.question) }}
							.inline-answer(v-for="answer in shortAnswers", :key="answer.id")
								template(v-if="answer.question.variant === 'url' && answer.answer")
									strong.question
										a(:href="answer.answer", target="_blank", rel="noopener noreferrer") {{ getLocalizedString(answer.question.question) }}
								template(v-else)
									span.question
										strong {{ getLocalizedString(answer.question.question) }}:
									span.answer(v-if="answer.question.variant === 'file'")
										i.fa.fa-file-o
										a(v-if="answer.answer_file", :href="answer.answer_file.url") {{ answer.answer_file }}
										span(v-else) {{ t.no_file_provided }}
									span.answer(v-else-if="answer.question.variant === 'boolean'") {{ answer.answer ? t.yes : t.no }}
									span.answer(v-else-if="answer.answer", v-html="markdownIt.render(answer.answer)")
									span.answer(v-else) {{ t.no_response }}
			.speaker-sessions
				session(
					v-for="session in modalContent.contentObject.sessions",
					:session="session",
					:showDate="true",
					:now="now",
					:timezone="currentTimezone",
					:locale="locale",
					:hasAmPm="hasAmPm",
					:faved="session.faved",
					:onHomeServer="onHomeServer",
					@fav="$emit('fav', session.id)",
					@unfav="$emit('unfav', session.id)",
				)
</template>

<script>
import MarkdownIt from 'markdown-it'
import { getLocalizedString, getSessionTime, getIconByFileEnding } from '../utils'
import FavButton from './FavButton.vue'
import Session from './Session.vue'
import ExportDropdown from './ExportDropdown.vue'

const markdownIt = MarkdownIt({
	linkify: false,
	breaks: true
})

export default {
	name: 'SessionModal',
	components: { FavButton, Session, ExportDropdown },
	inject: {
		remoteApiUrl: { default: '' },
		eventUrl: { default: '' },
		showJoinRoom: { default: false },
		getJoinRoomLink: { default: () => () => '' },
		translationMessages: { default: () => ({}) }
	},
	props: {
		modalContent: Object,
		currentTimezone: String,
		locale: String,
		hasAmPm: Boolean,
		now: Object,
		onHomeServer: Boolean,
		favs: {
			type: Array,
			default: () => []
		}
	},
	emits: ['toggleFav', 'showSpeaker', 'fav', 'unfav', 'joinRoom'],
	data () {
		return {
			markdownIt,
			getLocalizedString,
			getSessionTime,
			getIconByFileEnding
		}
	},
	computed: {
		t() {
			const m = this.translationMessages || {}
			return {
				yes: m.yes || 'Yes',
				no: m.no || 'No',
				join_room: m.join_room || 'Join room',
				downloads: m.downloads || 'Downloads',
				no_file_provided: m.no_file_provided || 'No file provided',
				no_response: m.no_response || 'No response',
				ical: m.ical || 'iCal',
			}
		},
		isFaved () {
			const obj = this.modalContent?.contentObject
			if (!obj) return false
			return this.favs.includes(obj.id)
		},
		computedJoinRoomLink () {
			const obj = this.modalContent?.contentObject
			if (!obj) return ''
			return this.getJoinRoomLink(obj) || ''
		},
		talkExportOptions () {
			const exporters = this.modalContent?.contentObject?.exporters
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
		},
		speakerExportOptions () {
			const obj = this.modalContent?.contentObject
			if (!obj || this.modalContent.contentType !== 'speaker') return []
			const exporters = obj.exporters
			const base = `${this.eventUrl || ''}speakers/${obj.code}`
			// Need either inline exporters data or a base URL to build URLs
			if (!exporters && !this.eventUrl) return []
			const qr = exporters?.qrcodes || {}
			const items = [
				{ id: 'google_calendar', label: 'Add to Google Calendar', url: exporters?.google_calendar || `${base}/talks/export/google-calendar`, icon: 'fa-google', qrcode_svg: qr.google_calendar },
				{ id: 'webcal', label: 'Add to Other Calendar', url: exporters?.webcal || `${base}/talks/export/webcal`, icon: 'fa-calendar', qrcode_svg: qr.webcal },
				{ id: 'ics', label: 'iCal', url: exporters?.ics || `${base}/talks.ics`, icon: 'fa-calendar', qrcode_svg: qr.ics },
				{ id: 'json', label: 'JSON (frab compatible)', url: exporters?.json || `${base}/talks.json`, icon: 'fa-code', qrcode_svg: qr.json },
				{ id: 'xml', label: 'XML (frab compatible)', url: exporters?.xml || `${base}/talks.xml`, icon: 'fa-code', qrcode_svg: qr.xml },
				{ id: 'xcal', label: 'XCal (frab compatible)', url: exporters?.xcal || `${base}/talks.xcal`, icon: 'fa-calendar', qrcode_svg: qr.xcal },
			].filter(o => o.url)

			return items
		},
		shortAnswers () {
			const apiContent = this.modalContent.contentObject.apiContent
			if (!apiContent || !apiContent.answers || !apiContent.answers.length) return []
			return apiContent.answers.filter((answer) => {
				// Exclude text answers and URL answers with icons (those go to iconAnswers)
				return answer.question.variant !== 'text' && !(answer.question.variant === 'url' && answer.question.icon)
			})
		},
		iconAnswers () {
			const apiContent = this.modalContent.contentObject.apiContent
			if (!apiContent || !apiContent.answers || !apiContent.answers.length) return []
			return apiContent.answers.filter((answer) => answer.question.variant === 'url' && answer.question.icon)
		}
	},
	methods: {
		showModal () {
			this.$refs.modal?.showModal()
		},
		close () {
			this.$refs.modal?.close()
		},
		handleSpeakerClick (speaker, event) {
			this.$emit('showSpeaker', speaker, event)
		}
	}
}
</script>

<style lang="stylus">
.pretalx-modal
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
		display: flex
		align-items: center

	.ampm
		margin-left: 4px

	.facts
		display: flex
		flex-wrap: wrap
		color: $clr-grey-600
		margin-bottom: 8px
		border-bottom: 1px solid $clr-grey-300
		align-items: center
		&>*
			margin-right: 4px
			margin-bottom: 8px
			&:not(:last-child):not(.session-export-area):after
				content: ','
		.session-export-area
			margin-left: auto

	.card-content
			display: flex
			flex-direction: column

			.downloads
				margin-top: 8px
				h4
					margin: 4px 0
				.download
					display: flex
					align-items: center
					height: 40px
					font-weight: 600
					font-size: 14px
					text-decoration: none
					color: var(--pretalx-clr-text)
					&:hover
						text-decoration: underline
					.mdi
						font-size: 24px
						margin-right: 4px
					.filename
						flex: 1
			.join-room-btn
				display: inline-block
				margin-top: 12px
				padding: 8px 24px
				border-radius: 4px
				font-weight: 600
				text-decoration: none
				color: $clr-white
				background-color: var(--pretalx-clr-primary, var(--clr-primary))
				width: fit-content
				&:hover
					opacity: 0.9

	.text-content
			margin-bottom: 8px
			.recording-embed
				margin-bottom: 16px
				iframe
					width: 100%
					aspect-ratio: 16 / 9
					border: none
					border-radius: 4px
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

	.answers
		.icon-group
			display: flex
			flex-wrap: wrap
			gap: 8px
			margin-top: 2px
			margin-bottom: 0

			.icon-link
				display: inline-flex
				align-items: center
				margin-right: 8px
				&:last-child
					margin-right: 0

				a
					display: flex
					align-items: center
					text-decoration: none
					color: var(--pretalx-clr-primary)
					&:hover
						text-decoration: underline

					img
						margin-right: 4px

		.inline-answer
			display: block
			margin-bottom: 8px

			.question
				color: var(--pretalx-clr-text)
				margin-right: 4px
				strong
					font-weight: 600

			.answer
				color: var(--pretalx-clr-text)

				p
					margin: 0
					display: inline

				.fa
					margin-right: 4px

				a
					color: var(--pretalx-clr-primary)
					text-decoration: none
					&:hover
						text-decoration: underline

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
			p
				color: var(--pretalx-clr-text)
				font-size: 14px

		.img-wrapper
			width: 100px
			height: 100px
			img, .avatar-placeholder
				width: 100px
				height: 100px

	.img-wrapper
		padding: 4px 16px 4px 4px
		width: 140px
		height: 140px
		img, .avatar-placeholder
			width: 140px
			height: 140px
			border-radius: 50%
			box-shadow: rgba(0, 0, 0, 0.12) 0px 1px 3px 0px, rgba(0, 0, 0, 0.24) 0px 1px 2px 0px

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
			margin: 0
		.speaker-header
			display: flex
			align-items: center
			gap: 16px
			margin-bottom: 16px
		.speaker-avatar
			flex-shrink: 0
			width: 100px
			height: 100px
			img, .avatar-placeholder
				width: 100px
				height: 100px
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
		.speaker-title
			display: flex
			flex-direction: column
			gap: 8px
		.speaker-export
			align-self: flex-start
		.speaker-content
			margin-bottom: 16px

			.biography
				margin-top: 8px
</style>

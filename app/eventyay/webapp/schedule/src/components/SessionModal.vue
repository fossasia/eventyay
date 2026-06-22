<template lang="pug">
dialog.pretalx-modal#session-modal(ref="modal", @click.stop="close()")
	.dialog-inner(@click.stop="")
		button.close-button(@click="close()") ✕
		template(v-if="modalContent && modalContent.contentType === 'session'")
			h3 {{ modalContent.contentObject.title }}
				.button-container(v-if="loggedIn", :class="isFaved ? 'faved' : ''")
					fav-button(@toggleFav="$emit('toggleFav', modalContent.contentObject.id)")

			.card-content
				.facts
					.time
						span {{ modalContent.contentObject.start.clone().tz(currentTimezone).format('dddd, D MMMM') }}, {{ getSessionTime(modalContent.contentObject, currentTimezone, locale, hasAmPm).time }}
						span.ampm(v-if="getSessionTime(modalContent.contentObject, currentTimezone, locale, hasAmPm).ampm") {{ getSessionTime(modalContent.contentObject, currentTimezone, locale, hasAmPm).ampm }}
					.room(v-if="modalContent.contentObject.room") {{ getLocalizedString(modalContent.contentObject.room.name) }}
					.track(v-if="modalContent.contentObject.track", :style="{ color: modalContent.contentObject.track.color }") {{ getLocalizedString(modalContent.contentObject.track.name) }}
					export-dropdown.session-export-area(v-if="talkExportOptions.length || exportsDisabled", :options="talkExportOptions", :qrcodesUrl="talkQrcodesUrl", :disabled="exportsDisabled")
				.text-content
					.recording-embed(v-if="modalContent.contentObject.recording_iframe", v-html="modalContent.contentObject.recording_iframe")
					.field-section(v-if="modalContent.contentObject.abstract")
						h4.field-heading Abstract
						.field-content(v-html="renderRichText(modalContent.contentObject.abstract)")
					.field-section(v-if="modalContent.contentObject.apiContent?.description?.length > 0 || modalContent.contentObject.description?.length > 0")
						h4.field-heading Description
						.field-content(v-html="renderRichText(modalContent.contentObject.apiContent?.description || modalContent.contentObject.description)")
					template(v-if="modalContent.contentObject.isLoading")
						bunt-progress-circular(size="big", :page="true")
					template(v-else)
						template(v-if="textAnswers.length > 0")
							.field-section(v-for="answer in textAnswers", :key="answer.id || answer.question_id")
								h4.field-heading {{ getLocalizedString(answer.question.question) }}
								.field-content(v-html="renderRichText(answer.answer)")
						template(v-if="publicScheduleAnswers.length > 0")
							.field-section(v-for="answer in publicScheduleAnswers", :key="answer.question_id")
								h4.field-heading {{ answer.question }}
								.field-content(v-html="renderRichText(answer.answer)")
						template(v-if="shortAnswers.length > 0 || iconAnswers.length > 0")
							hr
							.answers
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
										span.answer(v-else-if="answer.question.variant === 'boolean'") {{ parseBooleanAnswer(answer.answer) ? t.yes : t.no }}
										span.answer(v-else-if="answer.answer", v-html="renderRichText(answer.answer)")
										span.answer(v-else) {{ t.no_response }}
						.downloads(v-if="displayResources.length > 0")
							hr
							h4 {{ t.downloads }}
							a.download(v-for="{resource, description} of displayResources", :href="resource", target="_blank")
								svg.download-icon(viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px; flex-shrink: 0; opacity: 0.7;")
									path(d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71")
									path(d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71")
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
						p.biography(v-if="(speaker.apiContent?.biography || speaker.biography)?.length > 0", v-html="renderRichText(speaker.apiContent?.biography || speaker.biography)")
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
						export-dropdown.speaker-export(v-if="speakerExportOptions.length || exportsDisabled", :options="speakerExportOptions", :qrcodesUrl="speakerQrcodesUrl", :disabled="exportsDisabled")
				.speaker-content.card-content
					.biography(v-if="(modalContent.contentObject.apiContent?.biography || modalContent.contentObject.biography)?.length > 0", v-html="renderRichText(modalContent.contentObject.apiContent?.biography || modalContent.contentObject.biography)")
					template(v-if="modalContent.contentObject.isLoading")
						bunt-progress-circular(size="big", :page="true")
					template(v-else)
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
									span.answer(v-else-if="answer.question.variant === 'boolean'") {{ parseBooleanAnswer(answer.answer) ? t.yes : t.no }}
									span.answer(v-else-if="answer.answer", v-html="renderRichText(answer.answer)")
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
import { getLocalizedString, getSessionTime, getIconByFileEnding, buildExportMenuItems, computeSpeakerExporters, parseBooleanAnswer, buildQrcodesUrl } from '../utils'
import { renderEventyayRichText } from '../utils/eventyayRichText'
import FavButton from './FavButton.vue'
import Session from './Session.vue'
import ExportDropdown from './ExportDropdown.vue'

export default {
	name: 'SessionModal',
	components: { FavButton, Session, ExportDropdown },
	inject: {
		remoteApiUrl: { default: '' },
		eventUrl: { default: '' },
		loggedIn: { default: false },
		showJoinRoom: { default: false },
		getJoinRoomLink: { default: () => () => '' },
		translationMessages: { default: () => ({}) },
		exportsDisabled: { default: false },
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
			getLocalizedString,
			getSessionTime,
			getIconByFileEnding,
			parseBooleanAnswer,
		}
	},
	computed: {
		displayResources() {
			const obj = this.modalContent?.contentObject
			if (!obj) return []
			const resources = obj.apiContent?.resources ?? obj.resources ?? []
			return resources.map(r => {
				const resPath = r.resource || r.link
				if (resPath && resPath.toLowerCase().endsWith('.pdf')) {
					return {
						...r,
						resource: r.resource ? `${r.resource}#resource` : undefined,
						link: r.link ? `${r.link}#resource` : undefined
					}
				}
				return r
			})
		},
		talkQrcodesUrl() {
			const id = this.modalContent?.contentObject?.id
			return buildQrcodesUrl(this.eventUrl, 'talk', id)
		},
		speakerQrcodesUrl() {
			const code = this.modalContent?.contentObject?.code
			return buildQrcodesUrl(this.eventUrl, 'speaker', code)
		},
		favSet () {
			return new Set(this.favs || [])
		},
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
			return this.favSet.has(obj.id)
		},
		computedJoinRoomLink () {
			const obj = this.modalContent?.contentObject
			if (!obj) return ''
			return this.getJoinRoomLink(obj) || ''
		},
		talkExportOptions () {
			return buildExportMenuItems(this.modalContent?.contentObject?.exporters)
		},
		speakerExportOptions () {
			const obj = this.modalContent?.contentObject
			if (!obj || this.modalContent.contentType !== 'speaker') return []
			if (!obj.exporters && !this.eventUrl) return []
			const base = `${this.eventUrl || ''}speakers/${obj.code}`
			const merged = { ...computeSpeakerExporters(base), ...(obj.exporters || {}) }
			return buildExportMenuItems(merged)
		},
		shortAnswers () {
			const apiContent = this.modalContent.contentObject.apiContent
			if (!apiContent || !apiContent.answers || !apiContent.answers.length) return []
			return apiContent.answers.filter((answer) => {
				// Exclude text/string answers (those go to textAnswers) and URL answers with icons (iconAnswers)
				return answer.question.variant !== 'text' && answer.question.variant !== 'string' && !(answer.question.variant === 'url' && answer.question.icon)
			})
		},
		iconAnswers () {
			const apiContent = this.modalContent.contentObject.apiContent
			if (!apiContent || !apiContent.answers || !apiContent.answers.length) return []
			return apiContent.answers.filter((answer) => answer.question.variant === 'url' && answer.question.icon)
		},
		textAnswers () {
			const apiContent = this.modalContent.contentObject.apiContent
			if (!apiContent || !apiContent.answers || !apiContent.answers.length) return []
			return apiContent.answers.filter((answer) => answer.question.variant === 'text' || answer.question.variant === 'string')
		},
		publicScheduleAnswers () {
			const apiContent = this.modalContent?.contentObject?.apiContent
			if (apiContent && apiContent.answers && apiContent.answers.length > 0) return []
			const answers = this.modalContent?.contentObject?.answers
			if (!answers || !answers.length) return []
			if (!this.displayResources.length && !(this.modalContent?.contentObject?.resources?.length)) return answers

			const downloadsLabel = (this.t.downloads || '').trim().toLowerCase()
			return answers.filter((answer) => (answer.question || '').trim().toLowerCase() !== downloadsLabel)
		}
	},
	methods: {
		renderRichText (text) {
			return renderEventyayRichText(text || '')
		},
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
					transition: color 0.2s ease
					&:hover
						color: var(--pretalx-clr-primary)
						.download-icon
							opacity: 1
							color: var(--pretalx-clr-primary)
					.download-icon
						margin-right: 6px
						flex-shrink: 0
						opacity: 0.7
						transition: opacity 0.2s ease, color 0.2s ease
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
			.field-section
				margin-bottom: 12px
				.field-heading
					margin: 0 0 4px 0
					font-size: 14px
					font-weight: 700
					color: $clr-grey-600
				.field-content
					padding: 8px 12px
					p
						margin: 0.25em 0
						&:first-child
							margin-top: 0
						&:last-child
							margin-bottom: 0
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

<template lang="pug">
.c-talk-detail
	.talk-wrapper(v-if="resolvedTalk")
		.talk
			.talk-header(:class="{'has-actions': talkExportOptions.length || loggedIn}")
				h1 {{ getLocalizedString(resolvedTalk.title) }}
				.header-actions
					export-dropdown.talk-export(v-if="talkExportOptions.length", :options="talkExportOptions", :qrcodesUrl="talkQrcodesUrl")
					.button-container(v-if="loggedIn", :class="isFaved ? 'faved' : ''")
						fav-button(@toggleFav="toggleFav")
			.info
				span.info-main {{ datetime }} {{ roomName }}
				span.session-language(v-if="sessionLanguageLabel")  · {{ t.session_language }}: {{ sessionLanguageLabel }}
			.field-section.abstract-section(v-if="resolvedTalk.abstract")
				h2.field-heading Abstract
				.field-content
					markdown-content(:markdown="resolvedTalk.abstract")
			.field-section.description-section(v-if="resolvedTalk.description")
				h2.field-heading Description
				.field-content
					markdown-content(:markdown="resolvedTalk.description")
			.field-section(v-for="answer in longAnswers", :key="answer.id")
				h2.field-heading {{ getLocalizedString(answer.question.question) || String(answer.question.question) }}
				.field-content
					markdown-content(:markdown="answer.answer")
			.field-section(v-for="answer in inlineAnswers", :key="answer.id")
				h2.field-heading {{ getLocalizedString(answer.question.question) || String(answer.question.question) }}
				.field-content
					a.answer-link(v-if="(answer.question.variant === 'url' || answer.question.variant === 'file') && (answer.answer_file && answer.answer_file.url || answer.answer)", :href="answer.answer_file && answer.answer_file.url || answer.answer", target="_blank", rel="noopener noreferrer") {{ answer.answer || (answer.answer_file && answer.answer_file.url) }}
					span(v-else-if="answer.question.variant === 'boolean'") {{ answer.answer ? t.yes : t.no }}
					span(v-else-if="answer.answer") {{ answer.answer }}
			.field-section(v-for="answer in publicScheduleAnswers", :key="answer.question_id")
				h2.field-heading {{ answer.question }}
				.field-content
					markdown-content(:markdown="answer.answer")
			.downloads(v-if="displayResources.length > 0")
				h2 {{ t.downloads }}
				a.download(v-for="{resource, link, description} of displayResources", :href="getAbsoluteResourceUrl(resource || link)", target="_blank", rel="noopener noreferrer")
					.mdi(:class="`mdi-${getIconByFileEnding(resource || link)}`")
					.filename {{ description }}
			.video-stream(v-if="resolvedTalk.stream_url && computedJoinRoomLink && isLive")
				a.view-video-btn(:href="computedJoinRoomLink")
					svg(viewBox="0 0 24 24", width="18", height="18", fill="currentColor")
						path(d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z")
					span {{ t.view_video }}
			slot(name="actions")
				a.join-room-btn(v-if="showJoinRoom && computedJoinRoomLink", :href="computedJoinRoomLink", @click="onJoinRoomClick") {{ t.join_room }}
		.speakers(v-if="resolvedTalk.speakers && resolvedTalk.speakers.length > 0")
			.header {{ t.speakers }} ({{ resolvedTalk.speakers.length }})
			.speakers-list
				.speaker(v-for="speaker of resolvedTalk.speakers", :key="speaker.code")
					a.speaker-link(:href="getSpeakerLink(speaker)", @click="onSpeakerClick($event, speaker)")
						img.avatar-circle(
							v-if="speaker.avatar_thumbnail_default || speaker.avatar || speaker.avatar_url",
							:src="speaker.avatar_thumbnail_default || speaker.avatar || speaker.avatar_url",
							loading="lazy",
							decoding="async"
						)
						.avatar-placeholder.avatar-circle(v-else)
							svg(viewBox="0 0 24 24")
								path(fill="currentColor", d="M12,1A5.8,5.8 0 0,1 17.8,6.8A5.8,5.8 0 0,1 12,12.6A5.8,5.8 0 0,1 6.2,6.8A5.8,5.8 0 0,1 12,1M12,15C18.63,15 24,17.67 24,21V23H0V21C0,17.67 5.37,15 12,15Z")
						.name(:class="{'no-name': !speaker.name}") {{ speaker.name || t.speaker_name_not_provided }}
					markdown-content.biography(v-if="speaker.biography", :markdown="speaker.biography")
		.downloads(v-if="resolvedTalk.resources && resolvedTalk.resources.length > 0")
			.header {{ t.downloads }}
			.downloads-list
				a.download(v-for="{resource, link, description} of resolvedTalk.resources", :href="getAbsoluteResourceUrl(resource || link)", target="_blank", rel="noopener noreferrer")
					.mdi(:class="`mdi-${getIconByFileEnding(resource || link)}`")
					.filename {{ description }}
		.starrers(v-if="popularityFeatureEnabled && loggedIn && starrers && starrers.total > 0")
			.header
				span {{ t.starred_by }} ({{ starrers.total }})
				button.expand-toggle(type="button", @click="toggleStarrersExpanded") {{ starrersExpanded ? t.hide_list : t.view_all }}
			.avatars-line
				template(v-for="u of starrersInlineItems", :key="u.code")
					a.starrer(v-if="starrerUrl(u)", :href="starrerUrl(u)", @click="onStarrerClick($event, u)", :title="starrerTitle(u)")
						img.avatar-circle(v-if="u.avatar_url", :src="u.avatar_url", :alt="starrerTitle(u)")
						.avatar-placeholder.avatar-circle(v-else)
							svg(viewBox="0 0 24 24")
								path(fill="currentColor", d="M12,1A5.8,5.8 0 0,1 17.8,6.8A5.8,5.8 0 0,1 12,12.6A5.8,5.8 0 0,1 6.2,6.8A5.8,5.8 0 0,1 12,1M12,15C18.63,15 24,17.67 24,21V23H0V21C0,17.67 5.37,15 12,15Z")
					span.starrer(v-else, :title="t.anonymous_attendee")
						.avatar-placeholder.avatar-circle
							svg(viewBox="0 0 24 24")
								path(fill="currentColor", d="M12,1A5.8,5.8 0 0,1 17.8,6.8A5.8,5.8 0 0,1 12,12.6A5.8,5.8 0 0,1 6.2,6.8A5.8,5.8 0 0,1 12,1M12,15C18.63,15 24,17.67 24,21V23H0V21C0,17.67 5.37,15 12,15Z")
				button.more-chip(v-if="starrersOverflowCount > 0", type="button", @click="toggleStarrersExpanded") +{{ starrersOverflowCount }}
			.starrers-expanded(v-if="starrersExpanded")
				.starrers-list
					template(v-for="u of starrers.items", :key="u.code")
						a.starrer-row(v-if="starrerUrl(u)", :href="starrerUrl(u)", @click="onStarrerClick($event, u)")
							img.avatar-circle(v-if="u.avatar_url", :src="u.avatar_url", :alt="starrerTitle(u)")
							.avatar-placeholder.avatar-circle(v-else)
								svg(viewBox="0 0 24 24")
									path(fill="currentColor", d="M12,1A5.8,5.8 0 0,1 17.8,6.8A5.8,5.8 0 0,1 12,12.6A5.8,5.8 0 0,1 6.2,6.8A5.8,5.8 0 0,1 12,1M12,15C18.63,15 24,17.67 24,21V23H0V21C0,17.67 5.37,15 12,15Z")
							span.name {{ starrerTitle(u) }}
						span.starrer-row(v-else)
							.avatar-placeholder.avatar-circle
								svg(viewBox="0 0 24 24")
									path(fill="currentColor", d="M12,1A5.8,5.8 0 0,1 17.8,6.8A5.8,5.8 0 0,1 12,12.6A5.8,5.8 0 0,1 6.2,6.8A5.8,5.8 0 0,1 12,1M12,15C18.63,15 24,17.67 24,21V23H0V21C0,17.67 5.37,15 12,15Z")
							span.name {{ t.anonymous_attendee }}
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>

<script>
import moment from 'moment-timezone'
import { getLocalizedString, getIconByFileEnding, computeTalkExporters, buildExportMenuItems } from '../utils'
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
		generateStarrerLinkUrl: { default: () => (user) => user.url || '' },
		onStarrerLinkClick: { default: () => () => {} },
		loggedIn: { default: false },
		translationMessages: { default: () => ({}) },
		remoteApiUrl: { default: null }
	},
	props: {
		talk: Object,
		talkId: String,
		baseUrl: {
			type: String,
			default: ''
		},
		apiContent: {
			type: Object,
			default: null
		}
	},
	emits: ['joinRoom'],
	data() {
		return {
			getLocalizedString,
			getIconByFileEnding,
			starrers: { total: 0, public_total: 0, items: [] },
			starrersLoading: false,
			starrersExpanded: false,
			fetchedApiContent: null,
			fetchedSubmission: null,
		}
	},
	computed: {
		talkQrcodesUrl() {
			if (!this.baseUrl || !this.resolvedTalk?.id) return ''
			const base = this.baseUrl.replace(/\/?$/, '/')
			return `${base}schedule/widgets/qrcodes/talk/${this.resolvedTalk.id}.json`
		},
		t() {
			const m = this.translationMessages || {}
			return {
				join_room: m.join_room || 'Join room',
				speaker_name_not_provided: m.speaker_name_not_provided || 'Speaker name not provided',
				downloads: m.downloads || 'Downloads',
				speakers: m.speakers || 'Speakers',
				view_video: m.view_video || 'View Video',
				starred_by: m.starred_by || 'Starred by',
				anonymous_attendee: m.anonymous_attendee || 'Anonymous (name not shared)',
				view_all: m.view_all || 'View all',
				hide_list: m.hide_list || 'Hide',
				session_language: m.session_language || 'Language',
				yes: m.yes || 'Yes',
				no: m.no || 'No',
			}
		},
		uiLocale () {
			if (typeof document === 'undefined') return 'en'
			return (document.documentElement.lang || 'en').trim().split(',')[0] || 'en'
		},
		sessionLanguageLabel () {
			const code = this.resolvedTalk?.content_locale
			if (!code || typeof code !== 'string') return ''
			const tag = code.replace(/_/g, '-')
			try {
				return new Intl.DisplayNames([this.uiLocale], { type: 'language' }).of(tag) || code
			} catch {
				try {
					const primary = tag.split('-')[0] || tag
					return new Intl.DisplayNames([this.uiLocale], { type: 'language' }).of(primary) || code
				} catch {
					return code
				}
			}
		},
		inlineStarrersLimit() {
			return 15
		},
		starrersInlineItems() {
			const items = this.starrers?.items || []
			return items.slice(0, this.inlineStarrersLimit)
		},
		starrersOverflowCount() {
			if (this.starrersExpanded) return 0
			const total = this.starrers?.total || 0
			return Math.max(0, total - this.starrersInlineItems.length)
		},
		popularityFeatureEnabled() {
			return !!this.scheduleData?.schedule?.feature_flags?.session_popularity_enabled
		},
		resolvedTalk() {
			if (this.talk) return this.talk
			if (this.talkId && this.scheduleData) {
				const lu = this.scheduleData.sessionsLookup
				if (lu && lu[this.talkId]) return lu[this.talkId]
				const sessions = this.scheduleData.sessions || []
				for (let i = 0; i < sessions.length; i++) {
					if (sessions[i].id === this.talkId) return sessions[i]
				}
				return null
			}
			if (this.fetchedSubmission) return this.fetchedSubmission
			return null
		},
		computedJoinRoomLink() {
			if (!this.resolvedTalk) return ''
			return this.getJoinRoomLink(this.resolvedTalk) || ''
		},
		isFaved() {
			if (!this.resolvedTalk) return false
			const favSet = this.scheduleData?.favSet
			if (favSet && typeof favSet.has === 'function') return favSet.has(this.resolvedTalk.id)
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
		isLive() {
			const now = this.scheduleData?.now
			if (!now || !this.resolvedTalk) return false
			return this.resolvedTalk.start < now && this.resolvedTalk.end > now
		},
		effectiveApiContent() {
			return this.apiContent || this.fetchedApiContent
		},
		computedApiBaseUrl() {
			if (this.remoteApiUrl) return this.remoteApiUrl
			if (!this.baseUrl) return null
			try {
				const url = new URL(this.baseUrl, window.location.origin)
				const segments = url.pathname.split('/').filter(s => s.length > 0)
				const slug = segments[segments.length - 1] || ''
				return `${url.origin}/api/v1/events/${slug}/`
			} catch {
				return null
			}
		},
		longAnswers() {
			const answers = this.effectiveApiContent?.answers
			if (!Array.isArray(answers)) return []
			return answers.filter(a => a.question && a.question.is_public !== false &&
				(a.question.variant === 'text' || a.question.variant === 'string'))
		},
		inlineAnswers() {
			const answers = this.effectiveApiContent?.answers
			if (!Array.isArray(answers)) return []
			return answers.filter(a => a.question && a.question.is_public !== false &&
				a.question.variant !== 'text' && a.question.variant !== 'string')
		},
		publicScheduleAnswers() {
			if (this.effectiveApiContent?.answers?.length) return []
			return this.resolvedTalk?.answers || []
		},
		displayAnswers() {
			return this.publicScheduleAnswers
		},
		displayResources() {
			return this.effectiveApiContent?.resources ?? this.resolvedTalk?.resources ?? []
		},
		talkExportOptions() {
			const exporters = this.resolvedTalk?.exporters ||
				(this.baseUrl && this.resolvedTalk?.id ? computeTalkExporters(this.baseUrl, this.resolvedTalk.id) : null)
			return buildExportMenuItems(exporters)
		}
	},
	watch: {
		talkId: {
			handler() {
				this.fetchedApiContent = null
				this.fetchedSubmission = null
			}
		},
		resolvedTalk: {
			handler() {
				this.starrersExpanded = false
				this.loadStarrers({ limit: this.inlineStarrersLimit })
				if (!this.apiContent) this.fetchApiContent()
			},
			immediate: true
		}
	},
	methods: {
		starrerTitle(user) {
			if (!user || !user.url) return this.t.anonymous_attendee
			return user.name || this.t.anonymous_attendee
		},
		starrerUrl(user) {
			if (!user) return ''
			return this.generateStarrerLinkUrl(user) || user.url || ''
		},
		onStarrerClick(event, user) {
			this.onStarrerLinkClick(event, user)
		},
		getStarrersUrl({ limit } = {}) {
			if (!this.baseUrl || !this.resolvedTalk?.id) return ''
			try {
				const url = new URL(`talk/${this.resolvedTalk.id}/starrers.json`, this.baseUrl)
				if (typeof limit === 'number') url.searchParams.set('limit', String(limit))
				return url.href
			} catch {
				const base = this.baseUrl.replace(/\/$/, '')
				if (typeof limit !== 'number') return `${base}/talk/${this.resolvedTalk.id}/starrers.json`
				return `${base}/talk/${this.resolvedTalk.id}/starrers.json?limit=${encodeURIComponent(String(limit))}`
			}
		},
		async loadStarrers({ limit } = {}) {
			if (!this.popularityFeatureEnabled) return
			const url = this.getStarrersUrl({ limit })
			if (!url) return
			this.starrersLoading = true
			try {
				const response = await fetch(url)
				if (!response.ok) return
				const data = await response.json()
				if (!data || typeof data !== 'object') return
				const items = Array.isArray(data.items) ? data.items : []
				this.starrers = {
					total: Number.isFinite(data.total) ? data.total : 0,
					public_total: Number.isFinite(data.public_total) ? data.public_total : 0,
					items: items.filter(u => u && typeof u === 'object' && u.code)
				}
			} catch {
				// ignore
			} finally {
				this.starrersLoading = false
			}
		},
		async toggleStarrersExpanded() {
			this.starrersExpanded = !this.starrersExpanded
			if (!this.starrersExpanded) return
			if ((this.starrers?.items || []).length < (this.starrers?.total || 0)) {
				await this.loadStarrers({ limit: 0 })
			}
		},
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
		async toggleFav() {
			if (!this.loggedIn) return
			if (!this.resolvedTalk) return
			if (this.isFaved) {
				await this.scheduleUnfav(this.resolvedTalk.id)
			} else {
				await this.scheduleFav(this.resolvedTalk.id)
			}
			await this.loadStarrers({ limit: this.starrersExpanded ? 0 : this.inlineStarrersLimit })
		},
		async fetchApiContent() {
			if (this.apiContent || this.fetchedApiContent !== null) return
			if (!this.computedApiBaseUrl) return
			const id = this.resolvedTalk?.id || this.talkId
			if (!id) return
			try {
				const url = `${this.computedApiBaseUrl}submissions/${id}/?expand=answers.question,resources`
				const response = await fetch(url)
				if (!response.ok) return
				const data = await response.json()
				this.fetchedApiContent = data
				if (!this.talk && !this.scheduleData) this.fetchedSubmission = data
			} catch {
				// silently ignore network / auth errors
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
	.talk
		flex: none
		margin: 16px
		.talk-header
			display: flex
			justify-content: space-between
			align-items: center
			gap: 16px
			margin-bottom: 8px
			h1
				flex: 1
				margin: 0
			.header-actions
				display: flex
				align-items: center
				gap: 8px
				flex-shrink: 0
				.button-container
					flex-shrink: 0
		.info
			font-size: 18px
			color: $clr-secondary-text-light
			.session-language
				white-space: nowrap
		.field-section
			margin: 16px 0 0 0
			.field-heading
				margin: 0 0 6px 0
				font-size: 14px
				font-weight: 700
				color: $clr-secondary-text-light
			.field-content
				padding: 8px 12px
				p
					margin: 0.25em 0
					&:first-child
						margin-top: 0
					&:last-child
						margin-bottom: 0
			&.abstract-section
				.field-content
					font-size: 16px
					font-weight: 600
		.answer-link
			color: var(--clr-primary)
			text-decoration: none
			word-break: break-all
			&:hover
				text-decoration: underline
		.downloads
			border: border-separator()
			border-radius: 4px
			display: flex
			flex-direction: column
			font-size: 16px
			font-weight: 600
		.video-stream
			margin-top: 16px
			.view-video-btn
				display: inline-flex
				align-items: center
				gap: 8px
				padding: 8px 20px
				border-radius: 4px
				font-weight: 600
				text-decoration: none
				color: $clr-white
				background-color: $clr-danger
				&:hover
					opacity: 0.9
				svg
					flex-shrink: 0
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
	.starrers
		margin: 0 16px 32px
		display: flex
		flex-direction: column
		gap: 8px
		.header
			display: flex
			align-items: baseline
			justify-content: space-between
			gap: 8px
			font-weight: 600
			font-size: 16px
			.expand-toggle
				appearance: none
				border: none
				background: transparent
				padding: 0
				font: inherit
				color: var(--clr-primary)
				cursor: pointer
				text-decoration: underline
				font-weight: 600
		.avatars-line
			display: flex
			align-items: center
			flex-wrap: nowrap
			gap: 6px
			overflow-x: auto
			overflow-y: hidden
			.starrer
				display: inline-flex
				text-decoration: none
				flex-shrink: 0
			.avatar-circle
				border-radius: 50%
				height: 36px
				width: 36px
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
			.more-chip
				appearance: none
				border: border-separator()
				background: $clr-white
				color: $clr-primary-text-light
				border-radius: 999px
				padding: 3px 10px
				font-weight: 600
				font-size: 14px
				cursor: pointer
				flex-shrink: 0
				&:hover
					background-color: $clr-grey-100
		.starrers-expanded
			border: border-separator()
			border-radius: 4px
			padding: 8px
			.starrers-list
				display: flex
				flex-direction: column
				gap: 6px
				.starrer-row
					display: flex
					align-items: center
					gap: 8px
					text-decoration: none
					color: $clr-primary-text-light
					&:hover
						.name
							text-decoration: underline
							color: var(--clr-primary)
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
	.speakers
		margin: 0 16px 32px
		display: flex
		flex-direction: column
		border: border-separator()
		border-radius: 4px
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
	.downloads
		margin: 0 16px 32px
		display: flex
		flex-direction: column
		border: border-separator()
		border-radius: 4px
		.header
			border-bottom: border-separator()
			padding: 8px
		.download
			display: flex
			align-items: center
			gap: 8px
			padding: 8px
			text-decoration: none
			color: $clr-primary-text-light
			border-top: border-separator()
			&:first-child
				border-top: none
			&:hover
				background-color: $clr-grey-100
				.filename
					text-decoration: underline
					color: var(--clr-primary)
			.mdi
				font-size: 24px
				flex-shrink: 0
			.filename
				font-weight: 600
	@media (max-width: 768px)
		.speakers
			margin: 0 16px 16px
		.downloads
			margin: 0 16px 16px
		.starrers
			margin: 0 16px 16px
		.talk
			max-width: 100%
	@media (max-width: 480px)
		.talk
			margin: 10px
			.talk-header
				flex-direction: column-reverse
				align-items: flex-end
				h1
					font-size: 20px
				.header-actions
					gap: 4px
			.info
				font-size: 15px
			.abstract
				font-size: 14px
		.speakers
			margin: 0 10px 12px
		.downloads
			margin: 0 10px 12px
		.starrers
			margin: 0 10px 12px
</style>

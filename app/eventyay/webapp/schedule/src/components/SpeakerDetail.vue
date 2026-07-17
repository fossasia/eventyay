<template lang="pug">
.c-speaker-detail
	detail-back-nav(:event-url="eventUrl")
		detail-top-actions(
			:export-options="speakerExportOptions",
			:qrcodes-url="speakerQrcodesUrl")
	.speaker-wrapper(v-if="speakerDetailReady")
		.speaker-header
			.speaker-avatar
				img(v-if="resolvedSpeaker.avatar || resolvedSpeaker.avatar_url", :src="resolvedSpeaker.avatar || resolvedSpeaker.avatar_url", :alt="resolvedSpeaker.name")
				.avatar-placeholder(v-else)
					svg(viewBox="0 0 24 24")
						path(fill="currentColor", d="M12,1A5.8,5.8 0 0,1 17.8,6.8A5.8,5.8 0 0,1 12,12.6A5.8,5.8 0 0,1 6.2,6.8A5.8,5.8 0 0,1 12,1M12,15C18.63,15 24,17.67 24,21V23H0V21C0,17.67 5.37,15 12,15Z")
			.speaker-content-area
				.speaker-title
					h2 {{ resolvedSpeaker.name || t.speaker_fallback }}
				.speaker-social-links(v-if="socialLinks.length")
					a.speaker-social-link(
						v-for="link in socialLinks",
						:key="link.key + link.url",
						:href="link.url",
						:class="'speaker-social-link--' + link.key",
						:style="{ color: link.color || undefined }",
						:aria-label="link.label",
						:title="link.label",
						target="_blank",
						rel="noopener noreferrer")
						span.speaker-social-svg(v-html="socialIconHtml(link)")
		.field-section.biography-section(v-if="resolvedSpeaker.biography")
			h2.field-heading {{ t.biography }}
			.field-content
				markdown-content(:markdown="resolvedSpeaker.biography")
		.field-section(v-for="answer in longAnswers", :key="answer.id")
			h2.field-heading {{ getLocalizedString(answer.question.question) || String(answer.question.question) }}
			.field-content
				markdown-content(:markdown="answer.answer_string || answer.answer")
		.field-section(v-for="answer in inlineAnswers", :key="answer.id")
			h2.field-heading {{ getLocalizedString(answer.question.question) || String(answer.question.question) }}
			.field-content
				a.answer-link(v-if="(answer.question.variant === 'url' || answer.question.variant === 'file') && answer.answer_file && answer.answer_file.url", :href="answer.answer_file.url", target="_blank", rel="noopener noreferrer") {{ answer.answer || answer.answer_file.url }}
				a.answer-link(v-else-if="(answer.question.variant === 'url' || answer.question.variant === 'file') && answer.answer", :href="answer.answer", target="_blank", rel="noopener noreferrer") {{ answer.answer }}
				span(v-else-if="answer.question.variant === 'boolean'") {{ parseBooleanAnswer(answer.answer) ? t.yes : t.no }}
				span(v-else-if="answer.answer_string || answer.answer") {{ answer.answer_string || answer.answer }}
		.speaker-sessions(v-if="resolvedSessions && resolvedSessions.length")
			h3 {{ t.sessions }}
			session(
				v-for="s in resolvedSessions",
				:key="s.id",
				:session="s",
				:showDate="true",
				:now="resolvedNow",
				:timezone="resolvedTimezone",
				:locale="locale",
				:hasAmPm="resolvedHasAmPm",
				:faved="s.id && resolvedFavSet.has(s.id)",
				:onHomeServer="onHomeServer",
				@fav="onFav(s.id)",
				@unfav="onUnfav(s.id)"
			)
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>

<script>
import moment from 'moment-timezone'
import { getLocalizedString, buildExportMenuItems, computeSpeakerExporters, parseBooleanAnswer, buildQrcodesUrl, sessionsForSpeaker } from '../utils'
import MarkdownContent from './MarkdownContent.vue'
import Session from './Session.vue'
import DetailBackNav from './DetailBackNav.vue'
import DetailTopActions from './DetailTopActions.vue'

// Schedule runs as a web component without Font Awesome; use inline SVG icons.
const SOCIAL_ICON_SVG = {
	website: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2a10 10 0 100 20 10 10 0 000-20zm7.9 9h-3.2a15.4 15.4 0 00-1.3-5 8.03 8.03 0 014.5 5zM12 4c.9 0 2.3 1.9 3 5H9c.7-3.1 2.1-5 3-5zM4.1 11h3.2a15.4 15.4 0 011.3-5 8.03 8.03 0 00-4.5 5zM7.3 13H4.1a8.03 8.03 0 004.5 5 15.4 15.4 0 01-1.3-5zm1.7 0h6c-.7 3.1-2.1 5-3 5s-2.3-1.9-3-5zm8.7 0h3.2a8.03 8.03 0 01-4.5 5c.6-1.5 1.1-3.2 1.3-5zM12 20c-.9 0-2.3-1.9-3-5h6c-.7 3.1-2.1 5-3 5z"/></svg>',
	github: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 .3a12 12 0 00-3.8 23.4c.6.1.8-.3.8-.6v-2.2c-3.3.7-4-1.4-4-1.4-.5-1.4-1.3-1.8-1.3-1.8-1.1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1.1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.8-1.6-2.7-.3-5.5-1.3-5.5-6 0-1.3.5-2.4 1.2-3.2-.1-.3-.5-1.5.1-3.2 0 0 1-.3 3.3 1.2a11.5 11.5 0 016 0c2.3-1.5 3.3-1.2 3.3-1.2.6 1.7.2 2.9.1 3.2.8.8 1.2 1.9 1.2 3.2 0 4.7-2.8 5.7-5.5 6 .4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A12 12 0 0012 .3z"/></svg>',
	linkedin: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M4.98 3.5C4.98 4.88 3.86 6 2.5 6S0 4.88 0 3.5 1.12 1 2.5 1s2.48 1.12 2.48 2.5zM.24 8.25h4.52V24H.24V8.25zM8.34 8.25h4.33v2.14h.06c.6-1.14 2.08-2.34 4.28-2.34 4.58 0 5.42 3.01 5.42 6.93V24h-4.52v-6.86c0-1.64-.03-3.74-2.28-3.74-2.28 0-2.63 1.78-2.63 3.62V24H8.34V8.25z"/></svg>',
	x: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M18.9 2H22l-6.8 7.8L23 22h-6.2l-4.9-6.4L6.3 22H3.2l7.3-8.3L1 2h6.3l4.4 5.8L18.9 2zm-1.1 18h1.7L7.3 3.9H5.5L17.8 20z"/></svg>',
	facebook: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M22 12a10 10 0 10-11.6 9.9v-7H7.9V12h2.5V9.8c0-2.5 1.5-3.9 3.8-3.9 1.1 0 2.2.2 2.2.2v2.4h-1.3c-1.2 0-1.6.8-1.6 1.5V12h2.8l-.4 2.9h-2.4v7A10 10 0 0022 12z"/></svg>',
	instagram: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M7 2h10a5 5 0 015 5v10a5 5 0 01-5 5H7a5 5 0 01-5-5V7a5 5 0 015-5zm0 2a3 3 0 00-3 3v10a3 3 0 003 3h10a3 3 0 003-3V7a3 3 0 00-3-3H7zm11 1.8a1.2 1.2 0 110 2.4 1.2 1.2 0 010-2.4zM12 7a5 5 0 110 10 5 5 0 010-10zm0 2a3 3 0 100 6 3 3 0 000-6z"/></svg>',
	youtube: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M23.5 6.2a3 3 0 00-2.1-2.1C19.5 3.5 12 3.5 12 3.5s-7.5 0-9.4.6A3 3 0 00.5 6.2 31.5 31.5 0 000 12a31.5 31.5 0 00.5 5.8 3 3 0 002.1 2.1c1.9.6 9.4.6 9.4.6s7.5 0 9.4-.6a3 3 0 002.1-2.1A31.5 31.5 0 0024 12a31.5 31.5 0 00-.5-5.8zM9.8 15.5v-7l6.3 3.5-6.3 3.5z"/></svg>',
	gitlab: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 21.2L8.2 9.5h7.6L12 21.2zM.7 9.5h5.3L8.2 1.8c.1-.4.7-.4.8 0L12 9.5H.7c-.5 0-.7.6-.4 1L12 23.5 23.7 10.5c.3-.4.1-1-.4-1H18l2.2-7.7c.1-.4.7-.4.8 0L23.3 9.5"/></svg>',
	mastodon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2c-3.3 0-6 1-6 3.5v7.6c0 2.2 1.8 3 3.4 3.3.7.1 1.3.1 1.9.1l-.4 2c-.1.5.3 1 .8 1h.2c2.5 0 4.6-1 5.8-2.7 1-1.4 1.3-3.2 1.3-5.1V5.5C19 3 16.3 2 12 2zm-2.3 10.7c0 .6-.5 1.1-1.1 1.1S7.5 13.3 7.5 12.7V7.8c0-.6.5-1.1 1.1-1.1s1.1.5 1.1 1.1v4.9zm5.1 0c0 .6-.5 1.1-1.1 1.1s-1.1-.5-1.1-1.1V7.8c0-.6.5-1.1 1.1-1.1s1.1.5 1.1 1.1v4.9z"/></svg>',
	telegram: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M9.8 15.7l-.4 5.2c.5 0 .8-.2 1.1-.5l2.6-2.5 5.4 4c1 .5 1.7.3 2-.9L23.9 3.8c.3-1.3-.5-1.9-1.5-1.5L1.5 10.2C.2 10.7.2 11.4 1.3 11.7l5.6 1.7L19.2 5.5c.6-.4 1.2-.2.7.3L9.8 15.7z"/></svg>',
}

export default {
	name: 'SpeakerDetail',
	components: { MarkdownContent, Session, DetailBackNav, DetailTopActions },
	inject: {
		eventUrl: { default: null },
		remoteApiUrl: { default: '' },
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
		},
		translationMessages: { default: () => ({}) },
		isWipPreview: { default: false },
		exportsDisabled: { default: false },
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
	data() {
		return {
			getLocalizedString,
			parseBooleanAnswer,
			fetchedApiContent: null,
			apiContentLoaded: false,
		}
	},
	computed: {
		speakerQrcodesUrl() {
			const code = this.speakerId || this.speaker?.code || this.resolvedSpeaker?.code
			return buildQrcodesUrl(this.eventUrl, 'speaker', code)
		},
		t() {
			const m = this.translationMessages || {}
			return {
				speaker_fallback: m.speaker_fallback || 'Speaker',
				ical: m.ical || 'iCal',
				sessions: m.sessions || 'Sessions',
				export: m.export || 'Exports',
				yes: m.yes || 'Yes',
				no: m.no || 'No',
				biography: m.biography || 'Biography',
			}
		},
		resolvedSpeaker() {
			if (this.speaker) return this.speaker
			if (this.speakerId && this.scheduleData) {
				const lu = this.scheduleData.speakersLookup
				if (lu && lu[this.speakerId]) return lu[this.speakerId]
				const schedule = this.scheduleData.schedule
				if (schedule?.speakers) {
					for (let i = 0; i < schedule.speakers.length; i++) {
						if (schedule.speakers[i].code === this.speakerId) return schedule.speakers[i]
					}
				}
				const bySpeaker = this.scheduleData.sessionsBySpeaker?.[this.speakerId]
				if (bySpeaker?.length) {
					const first = bySpeaker[0]
					const speakers = first.speakers || []
					for (let j = 0; j < speakers.length; j++) {
						if (speakers[j].code === this.speakerId) return speakers[j]
					}
				}
			}
			return null
		},
		resolvedSessions() {
			if (this.sessions?.length) return this.sessions
			const id = this.speakerId || this.speaker?.code
			if (!id) return []
			const fromBySpeaker = sessionsForSpeaker(this.scheduleData?.sessionsBySpeaker, id)
			if (fromBySpeaker.length) return fromBySpeaker
			const list = this.scheduleData?.sessions || []
			const normalizedId = id.toLowerCase()
			return list.filter((session) => (session.speakers || []).some((sp) => {
				const code = typeof sp === 'string' ? sp : sp?.code
				return code && code.toLowerCase() === normalizedId
			}))
		},
		resolvedFavs() {
			if (this.favs?.length) return this.favs
			return this.scheduleData?.favs || []
		},
		resolvedFavSet() {
			const favSet = this.scheduleData?.favSet
			if (favSet && typeof favSet.has === 'function') return favSet
			return new Set(this.resolvedFavs)
		},
		resolvedNow() {
			return this.now || this.scheduleData?.now || moment()
		},
		resolvedTimezone() {
			return this.timezone || this.scheduleData?.timezone || moment.tz.guess()
		},
		resolvedHasAmPm() {
			if (this.hasAmPm !== undefined) return this.hasAmPm
			if (this.scheduleData?.hasAmPm !== undefined) return this.scheduleData.hasAmPm
			return new Intl.DateTimeFormat(undefined, {hour: 'numeric'}).resolvedOptions().hour12
		},
		effectiveSpeakerApiContent() {
			return this.resolvedSpeaker?.apiContent || this.fetchedApiContent
		},
		speakerDetailReady() {
			return this.resolvedSpeaker && (this.effectiveSpeakerApiContent || this.apiContentLoaded || !this.computedApiBaseUrl)
		},
		computedApiBaseUrl() {
			if (this.remoteApiUrl) return this.remoteApiUrl
			if (!this.eventUrl) return null
			try {
				const url = new URL(this.eventUrl, window.location.origin)
				const segments = url.pathname.split('/').filter(s => s.length > 0)
				const slug = segments[segments.length - 1] || ''
				return `${url.origin}/api/v1/events/${slug}/`
			} catch {
				return null
			}
		},
		longAnswers() {
			const answers = this.effectiveSpeakerApiContent?.answers
			if (!Array.isArray(answers)) return []
			return answers.filter(a => a.question && a.question.is_public !== false &&
				(a.question.variant === 'text' || a.question.variant === 'string'))
		},
		inlineAnswers() {
			const answers = this.effectiveSpeakerApiContent?.answers
			if (!Array.isArray(answers)) return []
			return answers.filter(a => a.question && a.question.is_public !== false &&
				a.question.variant !== 'text' && a.question.variant !== 'string')
		},
		socialLinks() {
			const links = this.effectiveSpeakerApiContent?.social_links
			return Array.isArray(links) ? links.filter(link => link && link.url) : []
		},
		speakerBaseUrl() {
			const code = this.speakerId || this.speaker?.code || this.resolvedSpeaker?.code
			if (!code || !this.eventUrl) return null
			return `${this.eventUrl}speakers/${code}`
		},
		speakerExportOptions() {
			if (this.exportsDisabled || !this.resolvedSessions?.length) return []
			const exporters = this.resolvedSpeaker?.exporters
			const base = this.speakerBaseUrl
			if (!exporters && !base) return []
			const merged = base ? { ...computeSpeakerExporters(base), ...(exporters || {}) } : exporters
			return buildExportMenuItems(merged)
		},
	},
	watch: {
		resolvedSpeaker: {
			handler() {
				if (!this.effectiveSpeakerApiContent) this.fetchApiContent()
			},
			immediate: true
		},
		speakerId() {
			this.fetchedApiContent = null
			this.apiContentLoaded = false
		}
	},
	methods: {
		socialIconHtml(link) {
			if (!link) return ''
			if (SOCIAL_ICON_SVG[link.key]) return SOCIAL_ICON_SVG[link.key]
			if (link.icon_svg) return link.icon_svg
			const letter = (link.label || link.key || '?').toString().charAt(0).toUpperCase()
			return (
				`<svg viewBox="0 0 32 32" aria-hidden="true">` +
				`<rect x="1" y="1" width="30" height="30" rx="7" fill="currentColor"></rect>` +
				`<text x="16" y="21" text-anchor="middle" font-size="14" font-family="Arial, sans-serif" font-weight="700" fill="#ffffff">${letter}</text>` +
				`</svg>`
			)
		},
		onFav(id) {
			if (this.scheduleFav) this.scheduleFav(id)
			this.$emit('fav', id)
		},
		onUnfav(id) {
			if (this.scheduleUnfav) this.scheduleUnfav(id)
			this.$emit('unfav', id)
		},
		async fetchApiContent() {
			if (this.effectiveSpeakerApiContent || this.fetchedApiContent !== null || this.apiContentLoaded) return
			if (!this.computedApiBaseUrl) {
				this.apiContentLoaded = true
				return
			}
			const code = this.speakerId || this.resolvedSpeaker?.code
			if (!code) {
				this.apiContentLoaded = true
				return
			}
			try {
				const url = `${this.computedApiBaseUrl}speakers/${code}/?expand=answers.question`
				const response = await fetch(url)
				if (!response.ok) {
					console.warn('[SpeakerDetail] API response not ok:', response.status, url)
					return
				}
				const data = await response.json()
				this.fetchedApiContent = data
			} catch (e) {
				console.warn('[SpeakerDetail] fetch failed:', e)
			} finally {
				this.apiContentLoaded = true
			}
		}
	}
}
</script>

<style lang="stylus">
.c-speaker-detail
	display: flex
	flex-direction: column
	background-color: $clr-white
	.speaker-wrapper
		flex: auto
		display: flex
		flex-direction: column
		padding: 16px
	.speaker-header
		display: flex
		align-items: center
		gap: 16px
		margin-bottom: 16px
		position: relative
		h2
			margin: 0
	.speaker-content-area
		flex: 1
		min-width: 0
	.speaker-title
		width: 100%
		display: flex
		flex-direction: column
		h2
			margin: 0
			text-align: left
	.speaker-social-links
		display: flex
		flex-wrap: wrap
		gap: 8px
		margin-top: 8px
	.speaker-social-link
		display: inline-flex
		align-items: center
		justify-content: center
		width: 32px
		height: 32px
		border-radius: 6px
		background: rgba(0, 0, 0, 0.06)
		color: inherit
		text-decoration: none
		font-size: 16px
		transition: background-color 0.15s ease, transform 0.15s ease
		&:hover, &:focus-visible
			background: rgba(0, 0, 0, 0.12)
			transform: translateY(-1px)
		.speaker-social-svg
			display: inline-flex
			width: 18px
			height: 18px
			svg
				width: 18px
				height: 18px
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
		&.biography-section
			.field-content
				font-size: 16px
	.answer-link
		color: var(--pretalx-clr-primary, var(--clr-primary))
		text-decoration: none
		word-break: break-all
		&:hover
			text-decoration: underline
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
			align-items: center
			text-align: center
			.speaker-content-area
				width: 100%
				flex-direction: column
				align-items: center
				gap: 4px
				.speaker-title h2
					text-align: center
		.speaker-avatar
			width: 96px
			height: 96px
			img, .avatar-placeholder
				width: 96px
				height: 96px
	@media (max-width: 480px)
		.speaker-wrapper
			padding: 10px
		.speaker-avatar
			width: 72px
			height: 72px
			img, .avatar-placeholder
				width: 72px
				height: 72px
		.biography
			font-size: 14px
</style>

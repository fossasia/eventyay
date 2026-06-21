<template lang="pug">
.c-speaker-detail
	detail-back-nav(destination="speakers")
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
import { getLocalizedString, buildExportMenuItems, computeSpeakerExporters, parseBooleanAnswer, buildQrcodesUrl } from '../utils'
import MarkdownContent from './MarkdownContent.vue'
import Session from './Session.vue'
import DetailBackNav from './DetailBackNav.vue'
import DetailTopActions from './DetailTopActions.vue'

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
		isWipPreview: { default: false }
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
			if (id && this.scheduleData?.sessionsBySpeaker?.[id]) {
				return this.scheduleData.sessionsBySpeaker[id]
			}
			if (id && this.scheduleData) {
				const list = this.scheduleData.sessions || []
				const out = []
				for (let i = 0; i < list.length; i++) {
					const s = list[i]
					const spk = s.speakers
					if (!spk) continue
					for (let j = 0; j < spk.length; j++) {
						if (spk[j] && spk[j].code === id) {
							out.push(s)
							break
						}
					}
				}
				return out
			}
			return []
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
		speakerBaseUrl() {
			const code = this.speakerId || this.speaker?.code || this.resolvedSpeaker?.code
			if (!code || !this.eventUrl) return null
			return `${this.eventUrl}speakers/${code}`
		},
		speakerExportOptions() {
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

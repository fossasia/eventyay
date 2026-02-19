<template lang="pug">
.c-speaker-detail(v-scrollbar.y="")
	.speaker-wrapper(v-if="resolvedSpeaker")
		.speaker-header
			.speaker-avatar
				img(v-if="resolvedSpeaker.avatar || resolvedSpeaker.avatar_url", :src="resolvedSpeaker.avatar || resolvedSpeaker.avatar_url", :alt="resolvedSpeaker.name")
				.avatar-placeholder(v-else)
					svg(viewBox="0 0 24 24")
						path(fill="currentColor", d="M12,1A5.8,5.8 0 0,1 17.8,6.8A5.8,5.8 0 0,1 12,12.6A5.8,5.8 0 0,1 6.2,6.8A5.8,5.8 0 0,1 12,1M12,15C18.63,15 24,17.67 24,21V23H0V21C0,17.67 5.37,15 12,15Z")
			.speaker-title
				h2 {{ resolvedSpeaker.name || t.speaker_fallback }}
			export-dropdown.speaker-export(v-if="speakerExportOptions.length", :options="speakerExportOptions")
		markdown-content.biography(v-if="resolvedSpeaker.biography", :markdown="resolvedSpeaker.biography")
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
				:faved="s.id && resolvedFavs.includes(s.id)",
				:onHomeServer="onHomeServer",
				@fav="onFav(s.id)",
				@unfav="onUnfav(s.id)"
			)
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>

<script>
import moment from 'moment-timezone'
import MarkdownContent from './MarkdownContent.vue'
import Session from './Session.vue'
import ExportDropdown from './ExportDropdown.vue'

export default {
	name: 'SpeakerDetail',
	components: { MarkdownContent, Session, ExportDropdown },
	inject: {
		eventUrl: { default: null },
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
		translationMessages: { default: () => ({}) }
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
	computed: {
		t() {
			const m = this.translationMessages || {}
			return {
				speaker_fallback: m.speaker_fallback || 'Speaker',
				ical: m.ical || 'iCal',
				sessions: m.sessions || 'Sessions',
				export: m.export || 'Exports',
			}
		},
		resolvedSpeaker() {
			if (this.speaker) return this.speaker
			if (this.speakerId && this.scheduleData) {
				const schedule = this.scheduleData.schedule
				if (schedule?.speakers) {
					return schedule.speakers.find(s => s.code === this.speakerId) || null
				}
				const sessions = this.scheduleData.sessions || []
				for (const session of sessions) {
					if (!session.speakers) continue
					const found = session.speakers.find(s => s.code === this.speakerId)
					if (found) return found
				}
			}
			return null
		},
		resolvedSessions() {
			if (this.sessions?.length) return this.sessions
			const id = this.speakerId || this.speaker?.code
			if (id && this.scheduleData) {
				return (this.scheduleData.sessions || []).filter(s =>
					s.speakers?.some(sp => sp.code === id)
				)
			}
			return []
		},
		resolvedFavs() {
			if (this.favs?.length) return this.favs
			return this.scheduleData?.favs || []
		},
		resolvedNow() {
			return this.now || this.scheduleData?.now || moment()
		},
		resolvedTimezone() {
			return this.timezone || this.scheduleData?.timezone || moment.tz.guess()
		},
		resolvedHasAmPm() {
			if (this.hasAmPm !== undefined && this.hasAmPm !== false) return this.hasAmPm
			if (this.scheduleData?.hasAmPm !== undefined) return this.scheduleData.hasAmPm
			return new Intl.DateTimeFormat(undefined, {hour: 'numeric'}).resolvedOptions().hour12
		},
		speakerBaseUrl() {
			const code = this.speakerId || this.speaker?.code || this.resolvedSpeaker?.code
			if (!code || !this.eventUrl) return null
			return `${this.eventUrl}speakers/${code}`
		},
		speakerExportOptions() {
			const exporters = this.resolvedSpeaker?.exporters
			const base = this.speakerBaseUrl
			// Need either inline exporters data or a base URL to build URLs
			if (!exporters && !base) return []
			const qr = exporters?.qrcodes || {}
			const items = [
				{ id: 'google_calendar', label: 'Add to Google Calendar', url: exporters?.google_calendar || (base && `${base}/talks/export/google-calendar`), icon: 'fa-google', qrcode_svg: qr.google_calendar },
				{ id: 'webcal', label: 'Add to Other Calendar', url: exporters?.webcal || (base && `${base}/talks/export/webcal`), icon: 'fa-calendar', qrcode_svg: qr.webcal },
				{ id: 'ics', label: 'iCal', url: exporters?.ics || (base && `${base}/talks.ics`), icon: 'fa-calendar', qrcode_svg: qr.ics },
				{ id: 'json', label: 'JSON (frab compatible)', url: exporters?.json || (base && `${base}/talks.json`), icon: 'fa-code', qrcode_svg: qr.json },
				{ id: 'xml', label: 'XML (frab compatible)', url: exporters?.xml || (base && `${base}/talks.xml`), icon: 'fa-code', qrcode_svg: qr.xml },
				{ id: 'xcal', label: 'XCal (frab compatible)', url: exporters?.xcal || (base && `${base}/talks.xcal`), icon: 'fa-calendar', qrcode_svg: qr.xcal },
			].filter(o => o.url)

			return items
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
		}
	}
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
	.speaker-title
		flex: 1
		display: flex
		flex-direction: column
		gap: 8px
		h2
			margin: 0
	.speaker-export
		flex-shrink: 0
		align-self: center
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
		.c-linear-schedule-session
			box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.08)
			border-radius: 6px
			margin: 8px 0
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

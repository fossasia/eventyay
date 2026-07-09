<template lang="pug">
.c-landing-page(v-scrollbar.y="", :style="landingStyle")
	.hero(:class="{'has-no-image': !hasHeroVisual}")
		.hero-content
			img.hero-logo(v-if="heroImage", :src="heroImage", :alt="eventTitle")
			.hero-copy(v-if="eventTitle || eventStartLine || eventEndLine")
				.hero-text(v-if="eventTitle") {{ eventTitle }}
			p.hero-time(v-if="eventStartLine") {{ eventStartLine }}
			p.hero-time(v-if="eventEndLine") {{ eventEndLine }}
	.content-container(v-if="hasContent")
		.content
			rich-text-content(v-if="mainContentIsRichText", :content="mainContent")
			markdown-content(v-else-if="mainContentIsMarkdown", :content="mainContent")
			.split-layout
				.split-left(v-if="(featuredSessions && featuredSessions.length) || (nextSessions && nextSessions.length)")
					template(v-if="featuredSessions && featuredSessions.length")
						.header
							h3 {{ $t('LandingPage:sessions:featured:header') }}
							bunt-link-button(:to="{name: 'schedule'}") {{ $t('LandingPage:sessions:featured:link') }}
						.sessions
							session(
								v-for="session of featuredSessions",
								:session="session",
								:now="now",
								:faved="favs.includes(session.id)",
								@fav="$store.dispatch('schedule/fav', $event)",
								@unfav="$store.dispatch('schedule/unfav', $event)"
							)
					template(v-if="nextSessions && nextSessions.length")
						.header
							h3 {{ $t('LandingPage:sessions:next:header') }}
							bunt-link-button(:to="{name: 'schedule'}") {{ $t('LandingPage:sessions:next:link') }}
						.sessions
							session(
								v-for="session of nextSessions",
								:session="session",
								:now="now",
								:faved="favs.includes(session.id)",
								@fav="$store.dispatch('schedule/fav', $event)",
								@unfav="$store.dispatch('schedule/unfav', $event)"
							)
				.split-right
					template(v-if="activeRooms && activeRooms.length")
						.header
							h3 {{ $t('LandingPage:rooms:header') }}
						.active-rooms.active-rooms-list
							router-link.room-card(v-for="item of activeRooms", :key="item.room.id", :to="{name: 'room', params: {roomId: item.room.id}}")
								.room-info
									.room-name {{ item.room.name }}
									.current-session(v-if="item.session")
										span.live-badge(v-if="item.isLive") {{ $t('LandingPage:rooms:live') }}
										span {{ item.session.title }}
								svg.room-arrow(viewBox="0 0 24 24", stroke="currentColor", stroke-width="2", fill="none")
									path(d="M5 12h14M12 5l7 7-7 7")
					.speakers-section(v-if="schedule && schedule.speakers && schedule.speakers.length")
						.header
							h3 {{ $t('LandingPage:speakers:header') }}
							bunt-link-button(:to="{name: 'schedule:speakers'}") {{ $t('LandingPage:speakers:link') }}
						speakers-list(:hideToolbar="true", :speakers="schedule.speakers")
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import moment from 'lib/timetravelMoment'
import config from 'config'
import Session from '@schedule/components/Session.vue'
import SpeakersList from '@schedule/components/SpeakersList.vue'
import MarkdownContent from 'components/MarkdownContent'
import RichTextContent from 'components/RichTextContent'

export default {
	components: { MarkdownContent, Session, RichTextContent, SpeakersList },
	props: {
		module: Object
	},
	data() {
		return {
			moment,
			eventMeta: null
		}
	},
	computed: {
		...mapState(['now', 'rooms', 'world', 'userTimezone']),
		...mapState('schedule', ['schedule']),
		...mapGetters('schedule', ['sessions', 'favs', 'currentSessionPerRoom']),
		landingConfig() {
			return this.module?.config || {}
		},
		mainContent() {
			return this.landingConfig.main_content ?? this.landingConfig.content ?? null
		},
		mainContentIsRichText() {
			const content = this.mainContent
			if (!content || typeof content !== 'object') return false
			if (Array.isArray(content)) {
				return content.some(op => typeof op?.insert === 'string' && op.insert.trim() !== '')
			}
			if (Array.isArray(content.ops)) {
				return content.ops.some(op => typeof op?.insert === 'string' && op.insert.trim() !== '')
			}
			return false
		},
		mainContentIsMarkdown() {
			return typeof this.mainContent === 'string' && this.mainContent.trim().length > 0
		},
		hasContent() {
			return this.mainContentIsRichText ||
				this.mainContentIsMarkdown ||
				(this.activeRooms && this.activeRooms.length > 0) ||
				(this.featuredSessions && this.featuredSessions.length > 0) ||
				(this.nextSessions && this.nextSessions.length > 0) ||
				(this.schedule && this.schedule.speakers && this.schedule.speakers.length > 0)
		},
		mediaBaseUrl() {
			const apiBase = config?.api?.base
			if (!apiBase) return '/media/'
			try {
				return new URL('/media/', apiBase).toString()
			} catch {
				return '/media/'
			}
		},
		heroImage() {
			return this.resolveMediaUrl(
				this.landingConfig.header_image
				|| this.world?.visible_logo_url
				|| config?.theme?.logo?.url
			)
		},
		heroBackgroundImage() {
			return this.resolveMediaUrl(
				this.landingConfig.header_background_image
				|| this.world?.visible_header_image_url
			)
		},
		hasHeroVisual() {
			return !!(this.heroImage || this.heroBackgroundImage)
		},
		landingStyle() {
			return {
				'--landing-hero-background-color': this.landingConfig.header_background_color || 'var(--clr-primary)',
				'--landing-hero-background-image': this.heroBackgroundImage ? `url("${this.heroBackgroundImage}")` : 'none'
			}
		},
		eventTitle() {
			if (this.world?.title) return this.world.title
			const name = this.eventMeta?.name
			if (typeof name === 'string') return name
			if (name && typeof name === 'object') {
				return name[this.$i18n?.language] || name.en || Object.values(name)[0] || ''
			}
			return ''
		},
		eventDateRange() {
			if (this.sessions?.length) {
				const start = this.sessions[0].start
				const end = this.sessions.reduce((latest, session) => session.end.isAfter(latest) ? session.end : latest, this.sessions[0].end)
				return { start, end }
			}
			if (this.eventMeta?.date_from) {
				const timezone = this.world?.timezone || this.userTimezone || moment.tz.guess()
				return {
					start: moment.tz(this.eventMeta.date_from, timezone),
					end: moment.tz(this.eventMeta.date_to || this.eventMeta.date_from, timezone)
				}
			}
			return null
		},
		eventStartLine() {
			if (!this.eventDateRange) return ''
			return this.formatEventDateTime(this.eventDateRange.start)
		},
		eventEndLine() {
			if (!this.eventDateRange) return ''
			return this.$t('LandingPage:dateRange:to', { date: this.formatEventDateTime(this.eventDateRange.end) })
		},
		featuredSessions() {
			if (!this.sessions) return
			return this.sessions.filter(session => session.featured)
		},
		nextSessions() {
			if (!this.sessions) return []
			// current or next sessions per room
			const sessions = []
			for (const session of this.sessions) {
				if (!session.room || !session.id) continue
				if (session.end.isBefore(this.now) || sessions.reduce((acc, s) => s.room === session.room ? ++acc : acc, 0) >= 2) continue
				sessions.push(session)
			}
			return sessions
		},
		activeRooms() {
			if (!this.rooms) return []
			// Shared list used for both the inclusion filter and the hasVideo flag.
			// Using the same constant avoids the bug where rooms with only
			// livestream.youtube / livestream.iframe are shown as active but
			// not marked as having video.
			const videoModuleTypes = [
				'livestream.native',
				'livestream.youtube',
				'livestream.iframe',
				'call.bigbluebutton',
				'call.zoom',
				'call.janus'
			]
			return this.rooms.filter(r => r.schedule_data || r.modules?.some(m => videoModuleTypes.includes(m.type))).map(room => {
				const sessionInfo = this.currentSessionPerRoom?.[room.id]
				const session = sessionInfo?.session
				const hasVideo = room.modules && room.modules.some(m => videoModuleTypes.includes(m.type))
				const isLive = !!session && hasVideo
				return { room, session, hasVideo, isLive }
			})
		},
	},
	async mounted() {
		await this.fetchEventMeta()
	},
	methods: {
		toMediaUrl(pathValue) {
			const cleaned = String(pathValue || '').replace(/^\/+/, '')
			if (!cleaned) return ''
			if (this.mediaBaseUrl.endsWith('/')) {
				return `${this.mediaBaseUrl}${cleaned}`
			}
			return `${this.mediaBaseUrl}/${cleaned}`
		},
		resolveMediaUrl(rawValue) {
			let value = typeof rawValue === 'string'
				? rawValue.trim()
				: (rawValue && typeof rawValue.url === 'string' ? rawValue.url.trim() : '')
			if (!value) return ''
			value = value.replace(/^['"]|['"]$/g, '')

			if (value.startsWith('public:')) {
				return this.toMediaUrl(value.slice(7))
			}
			if (value.startsWith('file://')) {
				return this.toMediaUrl(value.slice(7))
			}
			if (value.startsWith('data:') || value.startsWith('blob:')) {
				return value
			}
			if (/^(https?:)?\/\//.test(value)) {
				return value
			}
			if (value.startsWith('/')) {
				return value
			}

			return this.toMediaUrl(value)
		},
		formatEventDateTime(value) {
			const timezoneLabel = this.world?.timezone || this.userTimezone || 'UTC'
			return `${value.clone().tz(timezoneLabel).format('dddd, D MMMM YYYY h:mm A')} (${timezoneLabel})`
		},
		async fetchEventMeta() {
			if (!config?.api?.base) return
			try {
				const token = this.$store?.state?.token
				const clientId = this.$store?.state?.clientId
				const headers = {
					Accept: 'application/json'
				}
				if (token) {
					headers.Authorization = `Bearer ${token}`
				} else if (clientId) {
					headers.Authorization = `Client ${clientId}`
				}

				const response = await fetch(config.api.base, {
					method: 'GET',
					headers,
					credentials: 'same-origin'
				})
				if (!response.ok) return
				this.eventMeta = await response.json()
			} catch (error) {
				console.error('Failed to load landing page event metadata:', error)
			}
		},
	}
}
</script>
<style lang="stylus">
.c-landing-page
	flex: auto
	background-color: $clr-grey-50
	.hero
		height: 245px
		display: flex
		align-items: center
		justify-content: center
		padding: 3rem 0 0 0
		background-color: var(--landing-hero-background-color)
		background-image: var(--landing-hero-background-image)
		background-repeat: no-repeat
		background-size: cover
		background-position: center
		position: relative
		&::before
			content: ''
			position: absolute
			inset: 0
			background: linear-gradient(180deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.35) 40%, rgba(0,0,0,0.15) 100%)
			pointer-events: none
			z-index: 0
		&.has-no-image::before
			display: none
		> *
			position: relative
			z-index: 1
		&.has-no-image
			height: auto
			padding: 22px 0
			background-color: var(--clr-primary)
			color: $clr-primary-text-dark
		.hero-content
			width: 100%
			max-width: 1400px
			margin: 0 auto
			padding: 0 24px
			display: flex
			flex-direction: row
			align-items: center
			gap: 2rem
			position: relative
			z-index: 1
		.hero-copy
			display: flex
			flex-direction: column
			gap: 6px
			color: $clr-primary-text-dark
		.hero-text
			font-size: 3rem
			font-weight: 700
			line-height: 1.2
			word-break: break-word
			overflow-wrap: break-word
			min-width: 0
			text-align: left
			margin: 0
		.hero-time
			font-size: 16px
			line-height: 1.3
			margin: 0
		.hero-logo
			height: auto
			max-height: 140px
			width: auto
			object-fit: contain
	.content-container
		display: flex
		flex-direction: column
		align-items: center
		gap: 32px
		padding: 0 24px
		width: 100%
		max-width: 1400px
		margin: 0 auto
		box-sizing: border-box
	.content
		display: flex
		flex-direction: column
		width: 100%
		.header
			padding: 0 8px
	.rich-text-content, .c-markdown-content
		max-width: 960px
		margin: 0 auto
	.header
		display: flex
		justify-content: space-between
		align-items: baseline
		height: 56px
		h3
			margin: 0
			line-height: 56px
		.bunt-link-button
			themed-button-primary()

	.split-layout
		display: grid
		grid-template-columns: 1fr
		gap: 32px
		margin-top: 24px
		@media (min-width: 900px)
			grid-template-columns: 1fr 1fr
		.split-left
			display: flex
			flex-direction: column
			gap: 24px
		.split-right
			display: flex
			flex-direction: column
			gap: 24px

	.active-rooms-list
		display: flex
		flex-direction: column
		gap: 12px
		padding: 0 8px
		margin-bottom: 24px
		.room-card
			display: flex
			flex-direction: row
			align-items: center
			justify-content: space-between
			background: $clr-white
			border: border-separator()
			border-radius: 6px
			padding: 16px
			text-decoration: none
			color: inherit
			transition: background-color 0.2s
			&:hover
				background-color: $clr-grey-100
			.room-info
				flex: 1
				min-width: 0
			.room-name
				font-size: 18px
				font-weight: 600
				margin-bottom: 8px
			.current-session
				font-size: 14px
				color: $clr-secondary-text-light
				white-space: nowrap
				overflow: hidden
				text-overflow: ellipsis
				display: flex
				align-items: center
				.live-badge
					background-color: $clr-danger
					color: $clr-white
					font-size: 10px
					font-weight: 700
					padding: 2px 6px
					border-radius: 4px
					margin-right: 8px
			.room-arrow
				width: 20px
				height: 20px
				color: $clr-secondary-text-light
				margin-left: 12px
				flex-shrink: 0

	+below('m')
		.hero
			height: auto
			padding: 14px 0
			.hero-content
				flex-direction: column
				align-items: flex-start
				gap: 10px
				padding: 0 12px
			.hero-text
				font-size: 24px
			.hero-time
				font-size: 14px
			.hero-logo
				max-width: min(72vw, 280px)
				max-height: 120px
		.content-container
			flex-direction: column
			align-items: center
			padding: 0 8px
			> *
				max-width: 100%
</style>

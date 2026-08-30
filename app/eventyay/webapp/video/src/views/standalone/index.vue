<template lang="pug">
#standalone-app(:class="{fullscreen}", :style="[style, themeVariables]")
	.fatal-indicator.mdi.mdi-alert-octagon(v-if="currentFatalError || fatalConnectionError", :title="errorMessage")
	template(v-else-if="world")
		// Match platform AppBar: full viewport width, fixed 48px height
		.standalone-header
			.left
				.logo
					img(:src="brandLogoUrl", alt="Eventyay")
				.identity(v-if="eventTitle || room")
					.meta-stack(v-if="eventTitle")
						span.meta-label {{ $t('Event') }}
						span.meta-value {{ eventTitle }}
					.meta-divider(v-if="eventTitle && room", aria-hidden="true")
					.meta-stack(v-if="room")
						span.meta-label {{ $t('Room') }}
						span.meta-value(v-html="$emojify(room.name)")
		.stage-wrap
			.presentation-stage
				.presentation-content(v-if="room")
					router-view(:room="room", :config="config")
				.room-missing(v-else-if="roomsLoaded")
					i.mdi.mdi-door-closed-lock
					h2 {{ $t('Room not found') }}
					p {{ $t('This presentation link does not match a room in this event.') }}
				bunt-progress-circular(v-else, size="huge")
	bunt-progress-circular(v-else, size="small")
	ReactionsOverlay(v-if="$route.name === 'standalone:kiosk' && config.show_reactions !== false")
</template>
<script>
import { mapState } from 'vuex'
import config from 'config'
import { themeVariables, DEFAULT_LOGO } from 'theme'
import ReactionsOverlay from 'components/ReactionsOverlay.vue'

const SLIDE_WIDTH = 960
const SLIDE_HEIGHT = 700
const APP_BAR_HEIGHT = 48

export default {
	components: { ReactionsOverlay },
	props: {
		roomId: String
	},
	data() {
		return {
			fullscreen: false,
			themeVariables,
			scale: 1
		}
	},
	computed: {
		...mapState(['fatalConnectionError', 'fatalError', 'connected', 'user', 'world', 'rooms', 'roomFatalErrors']),
		currentFatalError() {
			const roomId = this.room?.id
			if (roomId && this.roomFatalErrors?.[roomId]) {
				return this.roomFatalErrors[roomId]
			}
			return this.fatalError?.roomId ? (roomId && this.fatalError.roomId === roomId ? this.fatalError : null) : this.fatalError
		},
		errorMessage() {
			return this.fatalConnectionError?.code || this.currentFatalError?.message || this.currentFatalError?.code || this.fatalError?.message
		},
		room() {
			const roomId = this.$route.params.roomId
			return this.rooms?.find(room => String(room.id) === String(roomId))
		},
		roomsLoaded() {
			return Array.isArray(this.rooms) && this.rooms.length > 0
		},
		config() {
			return this.user?.profile ?? {}
		},
		eventTitle() {
			return this.world?.title || window.eventyay?.eventTitle || ''
		},
		brandLogoUrl() {
			const basePath = config?.basePath ?? ''
			if (!basePath || basePath === '/') {
				return DEFAULT_LOGO.url || '/eventyay-video-logo.png'
			}
			const normalized = basePath.endsWith('/') ? basePath.slice(0, -1) : basePath
			return `${normalized}/eventyay-video-logo.png`
		},
		style() {
			return {
				'--scale': this.scale.toFixed(2)
			}
		}
	},
	watch: {
		room(newRoom, oldRoom) {
			if (newRoom === oldRoom) return
			this.$store.dispatch('changeRoom', this.room)
		}
	},
	created() {
		this.$store.dispatch('changeRoom', this.room)
		// Always use the full viewport — do not lock kiosk/presentation into a scaled 960×700 box.
		if (this.$route.query.fullscreen != null) {
			this.fullscreen = String(this.$route.query.fullscreen) === 'true'
		} else {
			this.fullscreen = false
		}
	},
	mounted() {
		window.addEventListener('resize', this.computeScale)
		this.computeScale()
	},
	beforeUnmount() {
		window.removeEventListener('resize', this.computeScale)
	},
	methods: {
		computeScale() {
			if (!this.fullscreen) {
				this.scale = 1
				return
			}
			const width = document.body.offsetWidth || window.innerWidth
			const height = (document.body.offsetHeight || window.innerHeight) - APP_BAR_HEIGHT
			if (!width || !height) {
				this.scale = 1
				return
			}
			this.scale = Math.max(0.25, Math.min(width / SLIDE_WIDTH, height / SLIDE_HEIGHT))
			this.$store.commit('reportMediaSourcePlaceholderRect', this.$el.getBoundingClientRect())
		}
	}
}
</script>
<style lang="stylus">
#standalone-app
	height: 100%
	width: 100%
	display: flex
	flex-direction: column
	font-size: 16px
	background-color: #ffffff
	color: #1e2327
	overflow: hidden
	--mediasource-placeholder-height: 100vh
	--mediasource-placeholder-width: 100vw
	> .bunt-progress-circular, > .fatal-indicator
		position: fixed
		top: 100%
		left: 0
		transform: translate(4px, calc(-100% - 4px))
	> .fatal-indicator
		color: $clr-danger
		font-size: 1vw

	// Match platform AppBar; event + room sit beside the logo once
	> .standalone-header
		--app-bar-background: var(--clr-navigation-background, var(--color-header-background, var(--clr-primary)))
		--app-bar-text: var(--clr-navigation-text-primary, var(--color-header-text, #fff))
		flex: 0 0 48px
		height: 48px
		width: 100%
		display: flex
		align-items: center
		padding: 0 12px
		box-sizing: border-box
		background-color: var(--app-bar-background)
		color: var(--app-bar-text)
		overflow: hidden
		z-index: 120
		.left
			display: flex
			align-items: center
			gap: 14px
			min-width: 0
			flex: 1 1 auto
		.logo
			flex: none
			height: 40px
			display: flex
			align-items: center
			img
				height: 100%
				max-width: 120px
				width: auto
				object-fit: contain
		.identity
			display: flex
			align-items: center
			gap: 14px
			min-width: 0
			flex: 1 1 auto
			overflow: hidden
			.meta-stack
				display: flex
				flex-direction: column
				justify-content: center
				gap: 1px
				min-width: 0
				max-width: 46%
			.meta-divider
				flex: none
				width: 1px
				height: 28px
				background: rgba(255, 255, 255, 0.35)
			.meta-label
				font-size: 10px
				font-weight: 700
				letter-spacing: 0.06em
				text-transform: uppercase
				opacity: 0.75
				line-height: 1.1
			.meta-value
				min-width: 0
				overflow: hidden
				text-overflow: ellipsis
				white-space: nowrap
				font-size: 14px
				font-weight: 700
				line-height: 1.2
				color: var(--app-bar-text)

	> .stage-wrap
		flex: 1 1 auto
		min-height: 0
		min-width: 0
		width: 100%
		display: flex
		flex-direction: column
		background-color: #ffffff
		overflow: hidden

		.presentation-stage
			flex: 1 1 auto
			min-height: 0
			min-width: 0
			width: 100%
			display: flex
			flex-direction: column
			overflow: hidden

		.presentation-content
			display: flex
			flex: 1 1 auto
			min-height: 0
			min-width: 0
			width: 100%
			justify-content: flex-start
			align-items: stretch
			background-color: #ffffff
			overflow: auto
			> *
				flex: 1 1 auto
				min-width: 0
				min-height: 0
				width: 100%
				max-width: 100%

		.room-missing
			display: flex
			flex: 1 1 auto
			flex-direction: column
			align-items: center
			justify-content: center
			text-align: center
			padding: 32px
			color: #4b5563
			background: #ffffff
			i.mdi
				font-size: 48px
				color: var(--clr-primary, #2185d0)
				margin-bottom: 12px
			h2
				margin: 0 0 8px
				color: #1e2327
			p
				margin: 0
				max-width: 360px

	&.fullscreen
		> .stage-wrap
			align-items: center
			justify-content: flex-start
			.presentation-stage
				transform: scale(var(--scale))
				transform-origin: top center
				width: 960px
				height: 700px
				flex: none
				.presentation-content
					overflow: hidden
					align-items: flex-start
					justify-content: flex-start

	.c-reactions-overlay
		bottom: 0
		right: 0
		.reaction
			height: calc(28px * var(--scale))
			width: @height
			bottom: calc(-32px * var(--scale))

@media (max-width: 600px)
	#standalone-app > .standalone-header
		padding: 0 8px
		.logo img
			max-width: 100px
		.identity
			gap: 8px
			.meta-divider
				height: 24px
			.meta-label
				font-size: 9px
			.meta-value
				font-size: 12px
</style>

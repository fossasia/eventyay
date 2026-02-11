<template lang="pug">
.v-app(:key="`${userLocale}-${userTimezone}`", :class="{'has-background-room': backgroundRoom, 'override-sidebar-collapse': overrideSidebarCollapse}", :style="[browserhackStyle, mediaConstraintsStyle]")
	.fatal-connection-error(v-if="fatalConnectionError")
		template(v-if="fatalConnectionError.code === 'world.unknown_world'")
			.mdi.mdi-help-circle
			h1 {{ $t('App:fatal-connection-error:world.unknown_world:headline') }}
		template(v-else-if="fatalConnectionError.code === 'connection.replaced'")
			.mdi.mdi-alert-octagon
			h1 {{ $t('App:fatal-connection-error:connection.replaced:headline') }}
			bunt-button(@click="reload") {{ $t('App:fatal-connection-error:connection.replaced:action') }}
		template(v-else-if="['auth.denied', 'auth.invalid_token', 'auth.missing_token', 'auth.expired_token'].includes(fatalConnectionError.code)")
			.mdi.mdi-alert-octagon
			h1 {{ $t('App:fatal-connection-error:' + fatalConnectionError.code + ':headline') }}
				br
				small {{ $t('App:fatal-connection-error:' + fatalConnectionError.code + ':text') }}
			bunt-button(v-if="fatalConnectionError.code != 'auth.missing_token'", @click="clearTokenAndReload") {{ $t('App:fatal-connection-error:' + fatalConnectionError.code + ':action') }}
		template(v-else)
			h1 {{ $t('App:fatal-connection-error:else:headline') }}
		p.code error code: {{ fatalConnectionError.code }}
	template(v-else-if="world")
		// AppBar stays fixed; only main content shifts
		app-bar(:show-actions="true", :show-user="true", @toggle-sidebar="toggleSidebar")
		transition(name="backdrop")
			.sidebar-backdrop(v-if="showSidebar", @click="showSidebar = false")
		.app-content(:class="{'sidebar-open': showSidebar}", role="main", tabindex="-1")
			// router-view no longer carries role=main; main landmark is the scroll container
			router-view(:key="!$route.path.startsWith('/admin') ? $route.fullPath : null")
			//- defining keys like this keeps the playing dom element alive for uninterupted transitions
			//- Single MediaSource for room streaming (persists across navigation to prevent stream restart)
			media-source(v-if="streamingRoom && user.profile.greeted && !hasFatalError(streamingRoom)", ref="mediaSource", :room="streamingRoom", :background="isStreamInBackground", :key="streamingRoom.id", :role="isStreamInBackground ? null : 'main'", @close="backgroundRoom = null")
			media-source(v-if="call", ref="channelCallSource", :call="call", :background="call.channel !== $route.params.channelId", :key="call.id", @close="$store.dispatch('chat/leaveCall')")
			#media-source-iframes
			notifications(:hasBackgroundMedia="isStreamInBackground")
			.disconnected-warning(v-if="!connected") {{ $t('App:disconnected-warning:text') }}
			transition(name="prompt")
				greeting-prompt(v-if="!user.profile.greeted")
			.native-permission-blocker(v-if="askingPermission")
		rooms-sidebar(:show="showSidebar", @close="showSidebar = false")
	.connecting(v-else-if="!currentFatalError")
		bunt-progress-circular(size="huge")
		.details(v-if="socketCloseCode == 1006") {{ $t('App:error-code:1006') }}
		.details(v-if="socketCloseCode") {{ $t('App:error-code:text') }}: {{ socketCloseCode }}
	.fatal-error(v-if="currentFatalError") {{ currentFatalError.message || currentFatalError.code }}
</template>
<script>
import { mapState } from 'vuex'
import { computed, reactive } from 'vue'
import moment from 'lib/timetravelMoment'
import api from 'lib/api'
import config from 'config'
import QRCode from 'qrcode'
import AppBar from 'components/AppBar'
import RoomsSidebar from 'components/RoomsSidebar'
import MediaSource from 'components/MediaSource'
import Notifications from 'components/notifications'
import GreetingPrompt from 'components/profile/GreetingPrompt'

const mediaModules = ['livestream.native', 'livestream.youtube', 'livestream.iframe', 'call.bigbluebutton', 'call.janus', 'call.zoom']
const stageToolModules = ['livestream.native', 'livestream.youtube', 'livestream.iframe', 'call.janus']
const chatbarModules = ['chat.native', 'question', 'poll']

export default {
	components: { AppBar, RoomsSidebar, MediaSource, GreetingPrompt, Notifications },
	provide() {
		return {
			scheduleData: reactive({
				schedule: computed(() => this.$store.state.schedule?.schedule),
				sessions: computed(() => this.$store.getters['schedule/sessions']),
				rooms: computed(() => this.$store.getters['schedule/rooms']),
				days: computed(() => this.$store.getters['schedule/days']),
				favs: computed(() => this.$store.getters['schedule/favs'] || []),
				now: computed(() => this.$store.state.now),
				timezone: localStorage.getItem('userTimezone') || moment.tz.guess(),
				hasAmPm: new Intl.DateTimeFormat(undefined, {hour: 'numeric'}).resolvedOptions().hour12,
				errorLoading: computed(() => this.$store.state.schedule?.errorLoading),
			}),
			scheduleFav: (id) => this.$store.dispatch('schedule/fav', id),
			scheduleUnfav: (id) => this.$store.dispatch('schedule/unfav', id),
			scheduleDoExport: (option) => this.doScheduleExport(option),
			exportBaseUrl: config.api.base + 'export-talk?export_type=',
			qrCodeModule: QRCode,
			linkTarget: '_blank',
			generateSessionLinkUrl: ({session}) => {
				if (session.url) return session.url
				return this.$router.resolve(this.getSessionRoute(session)).href
			},
			onSessionLinkClick: async (event, session) => {
				if (!session.url) {
					event.preventDefault()
					await this.$router.push(this.getSessionRoute(session))
				}
			},
			generateSpeakerLinkUrl: ({speaker}) => {
				return this.$router.resolve({name: 'schedule:speaker', params: {speakerId: speaker.code}}).href
			},
			onSpeakerLinkClick: async (event, speaker) => {
				event.preventDefault()
				await this.$router.push({name: 'schedule:speaker', params: {speakerId: speaker.code}})
			}
		}
	},
	data() {
		return {
			backgroundRoom: null,
			showSidebar: false,
			windowHeight: null
		}
	},
	computed: {
		...mapState(['fatalConnectionError', 'fatalError', 'connected', 'socketCloseCode', 'world', 'rooms', 'user', 'mediaSourcePlaceholderRect', 'userLocale', 'userTimezone', 'roomFatalErrors']),
		...mapState('notifications', ['askingPermission']),
		...mapState('chat', ['call']),
		currentFatalError() {
			if (this.room && this.roomFatalErrors?.[this.room.id]) {
				return this.roomFatalErrors[this.room.id]
			}
			if (!this.room && this.$route?.name && this.roomFatalErrors) {
				const backgroundFatal = this.backgroundRoom && this.roomFatalErrors[this.backgroundRoom.id]
				if (backgroundFatal) return backgroundFatal
			}
			return this.fatalError?.roomId ? (this.room && this.fatalError.roomId === this.room.id ? this.fatalError : null) : this.fatalError
		},
		room() {
			const routeName = this.$route?.name
			if (!routeName) return
			if (routeName.startsWith && routeName.startsWith('admin')) return
			if (routeName === 'home') return this.rooms?.[0]
			return this.rooms?.find(room => room.id === this.$route.params.roomId)
		},
		// TODO since this is used EVERYWHERE, use provide/inject?
		modules() {
			return this.room?.modules.reduce((acc, module) => {
				acc[module.type] = module
				return acc
			}, {})
		},
		roomHasMedia() {
			if (this.hasFatalError(this.room)) return false
			return this.room?.modules.some(module => mediaModules.includes(module.type))
		},
		// Single source of truth for which room should be streaming
		// Returns the current room if it has media, otherwise the background room
		streamingRoom() {
			if (this.roomHasMedia) return this.room
			if (this.backgroundRoom && !this.hasFatalError(this.backgroundRoom)) return this.backgroundRoom
			return null
		},
		// Determines if the streaming room should be shown in background (mini-window) mode
		// True when we have a background room that's different from the current room
		isStreamInBackground() {
			return this.backgroundRoom && this.room !== this.backgroundRoom
		},
		stageStreamCollapsed() {
			if (this.$mq.above.m) return false
			return this.mediaSourceRefs.media?.$refs.livestream ? !this.mediaSourceRefs.media.$refs.livestream.playing : false
		},
		// force open sidebar on medium screens on home page (with no media) so certain people can find the menu
		overrideSidebarCollapse() {
			return this.$mq.below.l &&
				this.$mq.above.m &&
				this.$route.name === 'home' &&
				!this.roomHasMedia
		},
		// safari cleverly includes the address bar cleverly in 100vh
		mediaConstraintsStyle() {
			const hasStageTools = this.room?.modules.some(module => stageToolModules.includes(module.type))
			const hasChatbar = (
				(this.room?.modules.length > 1 && this.room?.modules.some(module => chatbarModules.includes(module.type))) ||
				(this.call && this.call.channel === this.$route.params.channelId)
			)
			const style = {
				'--chatbar-width': hasChatbar ? '380px' : '0px',
				'--mobile-media-height': this.stageStreamCollapsed ? '56px' : hasChatbar ? 'min(56.25vw, 40vh)' : (hasStageTools ? 'calc(var(--vh100) - 48px - 2 * 56px)' : 'calc(var(--vh100) - 48px - 56px)'),
				'--has-stagetools': hasStageTools ? '1' : '0'
			}
			if (this.mediaSourcePlaceholderRect) {
				Object.assign(style, {
					'--mediasource-placeholder-height': this.mediaSourcePlaceholderRect.height + 'px',
					'--mediasource-placeholder-width': this.mediaSourcePlaceholderRect.width + 'px'
				})
			}
			return style
		},
		browserhackStyle() {
			return {
				'--vh100': this.windowHeight + 'px',
				'--vh': this.windowHeight && (this.windowHeight / 100) + 'px'
			}
		},
		// Map the named refs used for media sources into a single object so
		// other computed properties can safely reference them.
		mediaSourceRefs() {
			return {
				media: this.$refs.mediaSource,
				channel: this.$refs.channelCallSource
			}
		}
	},
	watch: {
		world: 'worldChange',
		rooms: 'roomListChange',
		room: 'roomChange',
		call: 'callChange',
		roomFatalErrors: {
			handler() {
				if (this.backgroundRoom && this.hasFatalError(this.backgroundRoom)) {
					this.backgroundRoom = null
				}
			},
			deep: true
		},
		stageStreamCollapsed: {
			handler() {
				this.$store.commit('updateStageStreamCollapsed', this.stageStreamCollapsed)
			},
			immediate: true
		}
	},
	mounted() {
		this.windowHeight = window.innerHeight
		window.addEventListener('resize', this.onResize)
		window.addEventListener('focus', this.onFocus, true)
		window.addEventListener('pointerdown', this.onGlobalPointerDown, true)
		window.addEventListener('keydown', this.onKeydown, true)
	},
	beforeUnmount() {
		window.removeEventListener('resize', this.onResize)
		window.removeEventListener('focus', this.onFocus)
		window.removeEventListener('pointerdown', this.onGlobalPointerDown, true)
		window.removeEventListener('keydown', this.onKeydown, true)
	},
	methods: {
		getSessionRoute(session) {
			if (session.room?.modules) {
				return {name: 'room', params: {roomId: session.room.id}}
			}
			return {name: 'schedule:talk', params: {talkId: session.id}}
		},
		async doScheduleExport(option) {
			try {
				const url = config.api.base + 'export-talk?export_type=' + option.id
				const authHeader = api._config.token ? `Bearer ${api._config.token}` : (api._config.clientId ? `Client ${api._config.clientId}` : null)
				const result = await fetch(url, {
					method: 'GET',
					headers: {
						Accept: 'application/json',
						...(authHeader ? { Authorization: authHeader } : {})
					}
				}).then(r => r.json())
				const a = document.createElement('a')
				document.body.appendChild(a)
				const blob = new Blob([result], {type: 'octet/stream'})
				const downloadUrl = window.URL.createObjectURL(blob)
				a.href = downloadUrl
				a.download = 'schedule-' + option.id + '.' + option.id.replace('my', '')
				a.click()
				window.URL.revokeObjectURL(downloadUrl)
				a.remove()
			} catch (error) {
				console.error('Export failed:', error)
			}
		},
		hasFatalError(room) {
			return !!(room && this.roomFatalErrors?.[room.id])
		},
		onKeydown(e) {
			if ((e.key === 'Escape' || e.key === 'Esc') && this.showSidebar) {
				this.showSidebar = false
				// Prevent the Escape from triggering other handlers if we handled it
				e.stopPropagation()
			}
		},
		onResize() {
			// Only track height for CSS vars; no breakpoint-based sidebar behavior
			this.windowHeight = window.innerHeight
		},
		onFocus() {
			this.$store.dispatch('notifications/clearDesktopNotifications')
		},
		toggleSidebar() {
			this.showSidebar = !this.showSidebar
		},
		onGlobalPointerDown(event) {
			if (!this.showSidebar) return
			const sidebarEl = document.querySelector('.c-rooms-sidebar')
			const hamburgerEl = document.querySelector('.c-app-bar .hamburger')
			if (sidebarEl?.contains(event.target) || hamburgerEl?.contains(event.target)) return
			this.showSidebar = false
		},
		clearTokenAndReload() {
			localStorage.removeItem('token')
			location.reload()
		},
		reload() {
			location.reload()
		},
		worldChange() {
			// initial connect
			document.title = this.world.title
		},
		callChange() {
			if (this.call) {
				// When a DM call starts, all other background media stops
				this.backgroundRoom = null
			}
		},
		roomChange(newRoom, oldRoom) {
			// HACK find out why this is triggered often
			if (newRoom === oldRoom) return
			// TODO non-room urls
			let title = this.world.title
			if (newRoom?.name) {
				title += ` | ${newRoom.name}`
			}
			document.title = title
			if (this.hasFatalError(newRoom)) {
				this.$store.dispatch('changeRoom', newRoom)
				this.backgroundRoom = null
				return
			}
			this.$store.dispatch('changeRoom', newRoom)
			const isExclusive = module => module.type === 'call.bigbluebutton' || module.type === 'call.zoom'
			if (!this.$mq.above.m) return // no background rooms for mobile
			if (this.call) return // When a DM call is running, we never want background media
			const newRoomHasMedia = newRoom && newRoom.modules && newRoom.modules.some(module => mediaModules.includes(module.type))
			// We treat "undefined / not callable" as true to avoid race conditions.
			let primaryWasPlaying = true
			const mediaRef = this.mediaSourceRefs.media
			if (typeof mediaRef?.isPlaying === 'function') {
				const result = mediaRef.isPlaying()
				if (result === false) primaryWasPlaying = false
			}
			if (oldRoom &&
				this.rooms.includes(oldRoom) &&
				!this.backgroundRoom &&
				oldRoom.modules.some(module => mediaModules.includes(module.type)) &&
				!this.hasFatalError(oldRoom) &&
				primaryWasPlaying &&
				// don't background bbb room when switching to new bbb room
				!(newRoom?.modules.some(isExclusive) && oldRoom?.modules.some(isExclusive)) &&
				!newRoomHasMedia
			) {
				this.backgroundRoom = oldRoom
			} else if (newRoomHasMedia) {
				this.backgroundRoom = null
			}
			// returning to room currently playing in background should maximize again
			if (this.backgroundRoom && (
				newRoom === this.backgroundRoom ||
				// close background bbb room if entering new bbb room
				(newRoom?.modules.some(isExclusive) && this.backgroundRoom.modules.some(isExclusive))
			)) {
				this.backgroundRoom = null
			}
		},
		roomListChange() {
			if (this.room && !this.rooms.includes(this.room)) {
				this.$router.push('/').catch(() => {})
			}
			if (!this.backgroundRoom && !this.rooms.includes(this.backgroundRoom)) {
				this.backgroundRoom = null
			}
		}
	}
}
</script>
<style lang="stylus">
.v-app
	flex: auto
	min-height: 0
	display: flex
	flex-direction: column
	--sidebar-width: 280px
	--pretalx-clr-primary: var(--clr-primary)
	.app-content
		flex: 1 1 auto
		min-height: 0
		height: calc(100vh - 48px)
		display: flex
		flex-direction: column
		position: relative
		padding-top: 48px
		z-index: 1
	.sidebar-backdrop
		position: fixed
		top: 0
		left: 0
		right: 0
		bottom: 0
		background-color: rgba(0, 0, 0, 0.5)
		z-index: 105
		&.backdrop-enter-active, &.backdrop-leave-active
			transition: opacity .2s
		&.backdrop-enter-from, &.backdrop-leave-to
			opacity: 0
	.main-content
		grid-area: main
		display: flex
		flex-direction: column
		min-height: var(--vh100)
		min-width: 0
	.c-app-bar
		grid-area: app-bar
	.c-rooms-sidebar
		grid-area: rooms-sidebar
	.c-room-header
		grid-area: main
		height: 100vh
	> .bunt-progress-circular
		position: fixed
		top: 50%
		left: 50%
		transform: translate(-50%, -50%)
	.disconnected-warning, .fatal-error
		position: fixed
		top: 48px
		left: calc(50% - 240px)
		width: 480px
		background-color: $clr-danger
		color: $clr-primary-text-dark
		padding: 16px
		box-sizing: border-box
		text-align: center
		font-weight: 600
		font-size: 20px
		border-radius: 0 0 4px 4px
		z-index: 2000
	.connecting
		display: flex
		height: var(--vh100)
		width: 100vw
		flex-direction: column
		justify-content: center
		align-items: center
		.details
			text-align: center
			max-width: 400px
			margin-top: 30px
			color: var(--clr-text-secondary)
	.fatal-connection-error
		position: fixed
		top: 0
		left: 0
		right: 0
		bottom: 0
		display: flex
		flex-direction: column
		justify-content: center
		align-items: center
		.mdi
			font-size: 10vw
			color: $clr-danger
		h1
			font-size: 3vw
			text-align: center
		.code
			font-family: monospace
		.bunt-button
			themed-button-primary('large')
	.native-permission-blocker
		position: fixed
		top: 48px
		left: 0
		width: 100vw
		height: calc(var(--vh100) - 48px)
		z-index: 2000
		background-color: $clr-secondary-text-light
	#media-source-iframes
		position: absolute
		width: 0
		height: 0
</style>

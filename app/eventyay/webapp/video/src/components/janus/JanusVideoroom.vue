<template lang="pug">
.c-janusvideoroom(:class="'size-' + size")
	.connection-state(v-if="connectionState !== 'connected'")
		.state-inner(v-if="connectionState === 'disconnected'")
			.mdi.mdi-wifi-off.state-icon
			span {{ $t('JanusVideoroom:disconnected:text') }}
		.state-inner.connection-error(v-else-if="connectionState === 'failed'")
			.mdi.mdi-alert-circle-outline.state-icon.state-icon--error
			p {{ $t('JanusVideoroom:connection-error:text') }}
			p.error-detail {{ connectionError }}
			bunt-button.retry-btn(@click="initJanus") Retry
		.state-inner(v-else)
			bunt-progress-circular(size="huge", :page="true")
			span Connecting...

	.room-surface(v-show="connectionState === 'connected'")
		.audio-sinks
			audio(
				v-for="feed in remoteAudioFeeds",
				:key="`audio-sink-${feed.id}`",
				class="remote-audio",
				:data-audio-feed-id="feed.id",
				autoplay
			)
		.gallery(ref="container", :class="{ 'has-screen': hasFocusTile }", :style="gridStyle", v-resize-observer="onResize")
			.video-tile(
				v-for="tile in tiles",
				:key="tile.key",
				:class="{ 'is-local': tile.local && !tile.screen, 'is-screen': tile.screen, 'is-focus': tile.focus, 'is-speaking': tile.speaking }"
			)
				.media-frame(:id="`janus_${tile.key}`")
					video(
						v-if="tile.local && !tile.screen",
						ref="localVideo",
						:class="{ 'is-hidden': !tile.hasVideo }",
						autoplay,
						playsinline,
						muted
					)
					video(
						v-else-if="tile.local && tile.screen",
						ref="localScreenVideo",
						autoplay,
						playsinline,
						muted
					)
					video(
						v-else,
						class="remote-media",
						:class="{ 'is-hidden': !tile.hasVideo }",
						:data-feed-id="tile.videoFeedId || tile.id",
						autoplay,
						playsinline
					)
					.avatar-wrap(v-if="!tile.hasVideo && !tile.screen")
						avatar(v-if="tile.user", :user="tile.user", :size="size === 'tiny' ? 40 : 96")
						.mdi.mdi-account-circle(v-else)
					.tile-gradient
					.tile-top
						.audio-meter(:class="{ active: tile.audioLevel > 0.01 }")
							.audio-meter-fill(:style="audioMeterStyle(tile)")
						.mute-pill(v-if="tile.muted")
							.mdi.mdi-microphone-off
					.tile-bottom
						button.identity(type="button", v-if="tile.user", @click="showUserCard($event, tile.user)")
							avatar(:user="tile.user", :size="28")
							span {{ tile.label }}
						span.identity.identity--plain(v-else)
							.mdi(:class="tile.screen ? 'mdi-monitor-share' : 'mdi-account'")
							span {{ tile.label }}
						.tile-actions
							button.tile-action(type="button", v-if="tile.pinnable", :title="tile.focus ? 'Unpin' : 'Pin'", @click="togglePin(tile)")
								.mdi(:class="tile.focus ? 'mdi-pin-off' : 'mdi-pin'")
							button.tile-action(type="button", v-if="tile.local && tile.screen", :title="$t('JanusVideoroom:tool-screenshare:off')", @click="stopScreenShare")
								.mdi.mdi-monitor-off

			.slow-banner(v-if="downstreamSlowLinkCount > 5 && videoOutput", @click="disableIncomingVideo") {{ $t('JanusVideoroom:slow:text') }}

		.pagination-bar(v-if="paginationTotalPages > 1")
			bunt-button.pagination-button(:disabled="currentVideoPage <= 1", @click="previousVideoPage")
				.mdi.mdi-chevron-left
			span.page-indicator Page {{ currentVideoPage }} of {{ paginationTotalPages }}
			bunt-button.pagination-button(:disabled="currentVideoPage >= paginationTotalPages", @click="nextVideoPage")
				.mdi.mdi-chevron-right

		.info-bar
			.info-message(v-if="!videoOutput") {{ $t('JanusVideoroom:video-output:off') }}
			.info-message.error-message(v-if="publishingError")
				.mdi.mdi-alert
				span {{ publishingError }}
			.info-message.error-message(v-if="screenShareError")
				.mdi.mdi-alert
				span {{ screenShareError }}

		.controlbar
			button.control-button(
				type="button",
				:class="{ muted: micMuted }",
				:title="micMuted ? $t('JanusVideoroom:tool-mute:off') : $t('JanusVideoroom:tool-mute:on')",
				@click="toggleMic"
			)
				.mdi(:class="micMuted ? 'mdi-microphone-off' : 'mdi-microphone'")
			button.control-button(
				type="button",
				:class="{ disabled: !cameraEnabled }",
				:title="cameraEnabled ? $t('JanusVideoroom:tool-video:off') : $t('JanusVideoroom:tool-video:on')",
				@click="toggleCamera"
			)
				.mdi(:class="cameraEnabled ? 'mdi-video' : 'mdi-video-off'")
			button.control-button(
				type="button",
				:class="{ active: screenShareState === 'published', loading: screenShareState === 'publishing' || screenShareState === 'unpublishing' }",
				:disabled="screenShareState === 'publishing' || screenShareState === 'unpublishing'",
				:title="screenShareState === 'published' ? $t('JanusVideoroom:tool-screenshare:off') : $t('JanusVideoroom:tool-screenshare:on')",
				@click="toggleScreenShare"
			)
				.mdi(:class="screenShareState === 'published' ? 'mdi-monitor-off' : 'mdi-monitor-share'")
			button.control-button(type="button", title="Settings", @click="showDevicePrompt = true")
				.mdi.mdi-cog
			button.control-button(type="button", title="Report issue", @click="showFeedbackPrompt = true")
				.mdi.mdi-message-alert-outline
			button.control-button.leave(type="button", :title="$t('JanusVideoroom:tool-hangup:tooltip')", @click="leaveRoom")
				.mdi.mdi-phone-hangup

	chat-user-card(v-if="selectedUser", ref="avatarCard", :user="selectedUser", @close="selectedUser = null")
	transition(name="prompt")
		template
			a-v-device-prompt(v-if="showDevicePrompt", @close="closeDevicePrompt")
			feedback-prompt(v-if="showFeedbackPrompt", module="janus", :collectTrace="collectTrace", @close="showFeedbackPrompt = false")
</template>

<script>
import Janus from 'lib/janus.js'
import adapter from 'webrtc-adapter'
import {mapState} from 'vuex'
import api from 'lib/api'
import ChatUserCard from 'components/ChatUserCard'
import Avatar from 'components/Avatar'
import AVDevicePrompt from 'components/AVDevicePrompt'
import FeedbackPrompt from 'components/FeedbackPrompt'
import {createPopper} from '@popperjs/core'
import SoundMeter from 'lib/webrtc/soundmeter'

const MIN_BITRATE = 150 * 1000
const MAX_BITRATE = 1500 * 1000
const SCREEN_SHARE_DISPLAY = 'venueless screenshare'
const USER_AUDIO_DISPLAY = 'venueless user audio'
const USER_VIDEO_DISPLAY = 'venueless user video'
const AUDIO_LEVEL_INTERVAL = 160
const SPEAKING_THRESHOLD = 0.03
const GRID_PAGE_SIZE = 15
const FOCUS_GRID_PAGE_SIZE = 5
const SIMULCAST_SUBSTREAMS = {
	low: 0,
	medium: 1,
	high: 2,
}
const VIDEO_SIMULCAST_BITRATES = {
	low: 100 * 1000,
	medium: 350 * 1000,
	high: 1200 * 1000,
}
const LOG_ENTRIES = []

const log = (source, level, message) => {
	LOG_ENTRIES.push([source, (new Date()).toISOString(), level, JSON.stringify(message)])
	console.log(`[${level}][${source}]`, message)
}

const janusDebugLogText = () => LOG_ENTRIES
	.map(([source, timestamp, level, message]) => `${timestamp} [${level}] [${source}] ${message}`)
	.join('\n')

const copyTextToClipboard = async (text) => {
	if (navigator.clipboard?.writeText) {
		await navigator.clipboard.writeText(text)
		return text
	}
	const textarea = document.createElement('textarea')
	textarea.value = text
	textarea.setAttribute('readonly', '')
	textarea.style.position = 'fixed'
	textarea.style.left = '-9999px'
	document.body.appendChild(textarea)
	textarea.select()
	document.execCommand('copy')
	document.body.removeChild(textarea)
	return text
}

const summarizeTrack = (track) => track ? ({
	id: track.id,
	kind: track.kind,
	enabled: track.enabled,
	muted: track.muted,
	readyState: track.readyState,
	label: track.label,
}) : null

const summarizeStream = (stream) => stream ? ({
	id: stream.id,
	audioTracks: stream.getAudioTracks().map(summarizeTrack),
	videoTracks: stream.getVideoTracks().map(summarizeTrack),
}) : null

const calculateLayout = (containerWidth, containerHeight, videoCount, aspectRatio, gap) => {
	const count = Math.max(videoCount, 1)
	const minimumCols = count > 2 && containerWidth >= 420 ? 2 : 1
	let bestLayout = {
		area: 0,
		cols: minimumCols,
		rows: count,
		width: containerWidth,
		height: containerHeight
	}
	for (let cols = minimumCols; cols <= count; cols++) {
		const rows = Math.ceil(count / cols)
		const availableWidth = containerWidth - gap * (cols - 1)
		const availableHeight = containerHeight - gap * (rows - 1)
		const widthFromContainer = Math.floor(availableWidth / cols)
		const heightFromWidth = Math.floor(widthFromContainer / aspectRatio)
		const heightFromContainer = Math.floor(availableHeight / rows)
		const widthFromHeight = Math.floor(heightFromContainer * aspectRatio)
		const width = Math.min(widthFromContainer, widthFromHeight)
		const height = Math.min(heightFromWidth, heightFromContainer)
		const area = width * height
		const isBetterShape = area === bestLayout.area && Math.abs(cols - rows) < Math.abs(bestLayout.cols - bestLayout.rows)
		if (area > bestLayout.area || isBetterShape) {
			bestLayout = {area, cols, rows, width, height}
		}
	}
	return bestLayout
}

export default {
	components: {Avatar, AVDevicePrompt, ChatUserCard, FeedbackPrompt},
	props: {
		server: {
			type: String,
			required: true
		},
		token: {
			type: String,
			required: true
		},
		sessionId: {
			type: [Number, String],
			required: true
		},
		audioSessionId: {
			type: [Number, String],
			required: true
		},
		videoSessionId: {
			type: [Number, String],
			required: true
		},
		screenShareSessionId: {
			type: [Number, String],
			required: true
		},
		roomId: {
			type: [Number, String],
			required: true
		},
		iceServers: {
			type: Array,
			required: true
		},
		automute: {
			type: Boolean,
			default: false
		},
		size: {
			type: String,
			default: 'normal'
		},
	},
	emits: ['hangup'],
	data() {
		return {
			connectionState: 'disconnected',
			connectionError: null,
			connectionRetryTimeout: null,
			retryInterval: 1000,
			suppressDestroyedState: false,
			publishingState: 'unpublished',
			screenShareState: 'unpublished',
			publishingError: null,
			screenShareError: null,
			janus: null,
			audioPublisherHandle: null,
			videoPublisherHandle: null,
			screenShareHandle: null,
			ourAudioId: null,
			ourVideoId: null,
			ourPrivateId: null,
			audioPublisherJoined: false,
			videoPublisherJoined: false,
			localAudioStream: null,
			localVideoStream: null,
			screenShareStream: null,
			pendingScreenShareStream: null,
			remoteFeeds: [],
			visibleVideoFeedIdsSnapshot: [],
			pausedVideoFeedIds: [],
			focusTarget: null,
			currentVideoPage: 1,
			subscribingFeedIds: [],
			subscriberRetryTimeouts: {},
			subscriberRetryCounts: {},
			cleaningUp: false,
			cameraEnabled: localStorage.videoRequested !== 'false',
			publishedWithVideo: false,
			audioPublishInProgress: false,
			audioPublishQueued: false,
			audioPublishTimeout: null,
			videoPublishInProgress: false,
			videoPublishQueued: false,
			videoPublishTimeout: null,
			localCameraActive: false,
			localCameraOnAt: null,
			micMuted: this.automute,
			videoInput: localStorage.videoInput || '',
			audioInput: localStorage.audioInput || '',
			videoOutput: localStorage.videoOutput !== 'false',
			automuteApplied: false,
			upstreamBitrate: MAX_BITRATE,
			upstreamSlowLinkCount: 0,
			downstreamSlowLinkCount: 0,
			slowLinkInterval: null,
			audioMeters: {},
			audioLevels: {},
			audioMeterContext: null,
			audioLevelInterval: null,
			layout: {
				area: 0,
				cols: 1,
				rows: 1,
				width: 0,
				height: 0
			},
			showFeedbackPrompt: false,
			showDevicePrompt: false,
			selectedUser: null,
		}
	},
	computed: {
		...mapState(['user']),
		janusRoomId() {
			return Number(this.roomId)
		},
		janusSessionId() {
			return Number(this.sessionId)
		},
		janusAudioSessionId() {
			return Number(this.audioSessionId)
		},
		janusVideoSessionId() {
			return Number(this.videoSessionId)
		},
		janusScreenShareSessionId() {
			return Number(this.screenShareSessionId)
		},
		gridStyle() {
			const w = this.layout.width > 0 ? `${this.layout.width}px` : 'minmax(0, 1fr)'
			const h = this.layout.height > 0 ? `${this.layout.height}px` : 'minmax(0, 1fr)'
			return {
				'--tile-columns': this.layout.cols,
				'--tile-rows': this.layout.rows,
				'--tile-width': w,
				'--tile-height': h,
			}
		},
		hasFocusTile() {
			return Boolean(this.screenShareStream || this.focusTile)
		},
		activeScreenTile() {
			return this.remoteScreenTiles[0] || null
		},
		remoteAudioFeeds() {
			return this.remoteFeeds
				.filter(feed => feed.feedType === 'audio' && feed.stream)
				.map(feed => ({...feed, id: this.normalizeFeedId(feed.id)}))
		},
		focusTile() {
			if (this.activeScreenTile) {
				return {
					...this.activeScreenTile,
					focus: true,
				}
			}
			if (this.screenShareStream) return null
			if (!this.focusTarget) return null
			const tile = this.allParticipantTiles.find(item => item.participantId === this.focusTarget)
			return tile ? {
				...tile,
				focus: true,
				layer: 'high',
			} : null
		},
		remoteScreenTiles() {
			return this.remoteFeeds
				.filter(feed => feed.isScreenShare || feed.feedType === 'screen')
				.filter(feed => feed.attached || feed.hasVideo)
				.map(feed => {
					const id = this.normalizeFeedId(feed.id)
					const level = this.normalizedAudioLevel(id)
					return {
						key: `remote-screen-${id}`,
						id,
						videoFeedId: id,
						audioFeedId: null,
						local: false,
						screen: true,
						pinnable: false,
						user: feed.user,
						label: this.feedLabel(feed),
						hasVideo: feed.hasVideo,
						muted: feed.muted,
						audioLevel: level,
						speaking: this.activeSpeakerId === id
					}
				})
				.sort((a, b) => a.label.localeCompare(b.label))
		},
		allParticipantTiles() {
			const localAudioLevel = this.normalizedAudioLevel('local')
			const localTile = {
				key: 'local',
				id: 'local',
				participantId: `local-${this.user?.id || 'user'}`,
				local: true,
				screen: false,
				focus: false,
				pinnable: true,
				user: this.user,
				label: this.user?.profile?.display_name || 'You',
				hasVideo: this.localCameraActive,
				cameraOn: this.localCameraActive,
				cameraOnAt: this.localCameraOnAt,
				muted: this.micMuted,
				audioLevel: localAudioLevel,
				speaking: this.activeSpeakerId === 'local'
			}
			return [localTile].concat(this.groupedRemoteTiles())
		},
		cameraOnParticipantTiles() {
			const participantTiles = this.allParticipantTiles.filter(tile => tile.cameraOn && tile.cameraOnAt)
			return participantTiles.sort((a, b) => {
				const byCamera = a.cameraOnAt - b.cameraOnAt
				return byCamera || a.label.localeCompare(b.label)
			})
		},
		rankedParticipantTiles() {
			const cameraOnIds = new Set(this.cameraOnParticipantTiles.map(tile => tile.participantId))
			const cameraOffTiles = this.allParticipantTiles
				.filter(tile => !cameraOnIds.has(tile.participantId))
				.sort((a, b) => a.label.localeCompare(b.label))
			return this.cameraOnParticipantTiles.concat(cameraOffTiles)
		},
		gridCandidateTiles() {
			const focusParticipantId = this.focusTile?.screen ? null : this.focusTile?.participantId
			return this.rankedParticipantTiles.filter(tile => tile.participantId !== focusParticipantId)
		},
		focusMode() {
			return Boolean(this.screenShareStream || this.focusTile)
		},
		paginationTotalPages() {
			if (!this.focusMode) {
				return Math.max(Math.ceil(this.gridCandidateTiles.length / GRID_PAGE_SIZE), 1)
			}
			const remainingAfterFirstPage = Math.max(this.gridCandidateTiles.length - FOCUS_GRID_PAGE_SIZE, 0)
			return 1 + Math.ceil(remainingAfterFirstPage / GRID_PAGE_SIZE)
		},
		visibleGridTiles() {
			if (!this.focusMode) {
				const start = (this.currentVideoPage - 1) * GRID_PAGE_SIZE
				return this.gridCandidateTiles.slice(start, start + GRID_PAGE_SIZE)
			}
			if (this.currentVideoPage === 1) {
				return this.gridCandidateTiles.slice(0, FOCUS_GRID_PAGE_SIZE)
			}
			const start = FOCUS_GRID_PAGE_SIZE + ((this.currentVideoPage - 2) * GRID_PAGE_SIZE)
			return this.gridCandidateTiles.slice(start, start + GRID_PAGE_SIZE)
		},
		gridVideoLayer() {
			return this.visibleGridTiles.length <= 4 ? 'medium' : 'low'
		},
		visibleVideoLayerByFeedId() {
			if (!this.videoOutput) return {}
			const layers = {}
			if (!this.screenShareStream && this.focusTile?.videoFeedId && this.focusTile.cameraOn && !this.focusTile.screen) {
				layers[this.normalizeFeedId(this.focusTile.videoFeedId)] = 'high'
			}
			for (const tile of this.visibleGridTiles) {
				if (tile.videoFeedId && tile.cameraOn) {
					layers[this.normalizeFeedId(tile.videoFeedId)] = this.gridVideoLayer
				}
			}
			return layers
		},
		visibleVideoSubscriptionKey() {
			return Object.entries(this.visibleVideoLayerByFeedId)
				.sort(([leftFeedId], [rightFeedId]) => leftFeedId.localeCompare(rightFeedId))
				.map(([feedId, layer]) => `${feedId}:${layer}`)
				.join('|')
		},
		visibleVideoParticipantIds() {
			return Object.keys(this.visibleVideoLayerByFeedId)
		},
		activeSpeakerId() {
			let activeId = null
			let activeLevel = SPEAKING_THRESHOLD
			for (const [id, rawLevel] of Object.entries(this.audioLevels)) {
				const level = Number(rawLevel) || 0
				if (level > activeLevel && !this.isFeedMuted(id)) {
					activeId = id
					activeLevel = level
				}
			}
			return activeId
		},
		tiles() {
			const localTiles = []
			if (this.screenShareStream) {
				localTiles.push({
					key: 'local-screen',
					id: 'local-screen',
					local: true,
					screen: true,
					focus: true,
					user: this.user,
					label: 'Your screen',
					hasVideo: true,
					muted: true,
					audioLevel: 0,
					speaking: false
				})
			}
			const tiles = localTiles.concat(this.focusTile ? [this.focusTile] : [], this.visibleGridTiles)
			return tiles
		},
	},
	watch: {
		tiles() {
			this.$nextTick(() => {
				this.onResize()
				this.syncLocalMediaElements()
				this.syncRemoteFeedMediaElements()
			})
		},
		visibleVideoSubscriptionKey() {
			this.syncVisibleVideoSubscriptions()
			this.$nextTick(() => this.syncRemoteFeedMediaElements())
		},
		paginationTotalPages() {
			this.clampVideoPage()
		},
		focusMode() {
			this.clampVideoPage()
		}
	},
	mounted() {
		LOG_ENTRIES.splice(0, LOG_ENTRIES.length)
		window.__JANUS_DEBUG_LOGS__ = janusDebugLogText
		window.__JANUS_DEBUG_JSON__ = () => JSON.stringify(LOG_ENTRIES, null, 2)
		window.__JANUS_COPY_DEBUG_LOGS__ = () => copyTextToClipboard(window.__JANUS_DEBUG_LOGS__())
		window.__JANUS_SHOW_DEBUG_LOGS__ = () => {
			const existing = document.getElementById('janus-debug-log-dump')
			if (existing) existing.remove()
			const textarea = document.createElement('textarea')
			textarea.id = 'janus-debug-log-dump'
			textarea.value = window.__JANUS_DEBUG_LOGS__()
			textarea.style.position = 'fixed'
			textarea.style.zIndex = '2147483647'
			textarea.style.inset = '16px'
			textarea.style.width = 'calc(100% - 32px)'
			textarea.style.height = 'calc(100% - 32px)'
			textarea.style.padding = '12px'
			textarea.style.background = '#111317'
			textarea.style.color = '#f6f7f9'
			textarea.style.font = '12px monospace'
			document.body.appendChild(textarea)
			textarea.focus()
			textarea.select()
			return textarea
		}
		window.__JANUS_DOWNLOAD_DEBUG_LOGS__ = () => {
			const blob = new Blob([window.__JANUS_DEBUG_LOGS__()], {type: 'text/plain'})
			const link = document.createElement('a')
			link.href = URL.createObjectURL(blob)
			link.download = `janus-debug-${Date.now()}.log`
			link.click()
			URL.revokeObjectURL(link.href)
		}
		this.cleaningUp = false
		this.initJanus()
		this.slowLinkInterval = window.setInterval(() => {
			this.downstreamSlowLinkCount = Math.max(this.downstreamSlowLinkCount - 1, 0)
			this.upstreamSlowLinkCount = Math.max(this.upstreamSlowLinkCount - 1, 0)
		}, 10000)
		this.audioLevelInterval = window.setInterval(this.refreshAudioLevels, AUDIO_LEVEL_INTERVAL)
	},
	unmounted() {
		this.cleanup()
		if (this.connectionRetryTimeout) {
			window.clearTimeout(this.connectionRetryTimeout)
		}
		if (this.slowLinkInterval) {
			window.clearInterval(this.slowLinkInterval)
		}
		if (this.audioLevelInterval) {
			window.clearInterval(this.audioLevelInterval)
		}
		if (this.audioPublishTimeout) {
			window.clearTimeout(this.audioPublishTimeout)
		}
		if (this.videoPublishTimeout) {
			window.clearTimeout(this.videoPublishTimeout)
		}
	},
	methods: {
		collectTrace() {
			return LOG_ENTRIES
		},
		initJanus() {
			this.connectionState = 'connecting'
			Janus.init({
				debug: 'all',
				callback: this.onJanusInitialized,
				dependencies: Janus.useDefaultDependencies({adapter})
			})
		},
		onJanusInitialized() {
			this.cleaningUp = false
			this.connectionState = 'connecting'
			Janus.trace = (t) => log('janus', 'trace', t)
			Janus.debug = (t) => log('janus', 'debug', t)
			Janus.vdebug = (t) => log('janus', 'vdebug', t)
			Janus.log = (t) => log('janus', 'log', t)
			Janus.warn = (t) => log('janus', 'warn', t)
			Janus.error = (t) => log('janus', 'error', t)
			this.janus = new Janus({
				server: this.server,
				iceServers: this.iceServers,
				success: this.onJanusConnected,
				error: this.failConnection,
				destroyed: () => {
					if (this.suppressDestroyedState) {
						this.suppressDestroyedState = false
						return
					}
					this.connectionState = 'disconnected'
				},
			})
		},
		onJanusConnected() {
			this.attachAudioPublisher()
		},
		attachAudioPublisher() {
			log('janus-audio-publisher', 'debug', {
				action: 'attachAudioPublisher:start',
				roomId: this.janusRoomId,
				audioSessionId: this.janusAudioSessionId,
				userId: this.user?.id,
			})
			this.janus.attach({
				plugin: 'janus.plugin.videoroom',
				opaqueId: `${this.user.id}-audio`,
				success: (pluginHandle) => {
					this.audioPublisherHandle = pluginHandle
					log('janus-audio-publisher', 'debug', {
						action: 'attachAudioPublisher:success',
						handleId: pluginHandle.getId(),
						roomId: this.janusRoomId,
						audioSessionId: this.janusAudioSessionId,
					})
					this.audioPublisherHandle.send({
						message: {
							request: 'join',
							room: this.janusRoomId,
							id: this.janusAudioSessionId,
							ptype: 'publisher',
							token: this.token,
							display: USER_AUDIO_DISPLAY,
						}
					})
				},
				error: (error) => {
					log('janus-audio-publisher', 'error', {
						action: 'attachAudioPublisher:error',
						error: error?.message || error,
						name: error?.name,
					})
					this.failConnection(error)
				},
				iceState: (state) => {
					log('janus-audio-publisher', 'debug', {
						action: 'iceState',
						state,
					})
					if (state === 'failed') {
						this.failConnection(`ICE connection ${state}`)
					}
				},
				mediaState: (medium, on) => {
					log('janus-audio-publisher', 'debug', {
						action: 'mediaState',
						medium,
						on,
					})
					if (on && medium === 'audio') {
						this.publishingState = 'published'
						this.publishingError = null
					}
				},
				webrtcState: (on) => {
					log('janus-audio-publisher', 'debug', {
						action: 'webrtcState',
						on,
					})
				},
				onmessage: this.onAudioPublisherMessage,
				onlocalstream: this.onLocalAudioStream,
				oncleanup: () => {
					log('janus-audio-publisher', 'debug', {
						action: 'oncleanup',
					})
				},
			})
		},
		attachVideoPublisher() {
			if (this.videoPublisherHandle) {
				if (this.videoPublisherJoined && this.cameraEnabled) {
					this.publishVideoMedia()
				}
				return
			}
			this.janus.attach({
				plugin: 'janus.plugin.videoroom',
				opaqueId: `${this.user.id}-video`,
				success: (pluginHandle) => {
					this.videoPublisherHandle = pluginHandle
					log('venueless', 'info', `Video publisher handle attached (${pluginHandle.getId()})`)
					this.videoPublisherHandle.send({
						message: {
							request: 'join',
							room: this.janusRoomId,
							id: this.janusVideoSessionId,
							ptype: 'publisher',
							token: this.token,
							display: USER_VIDEO_DISPLAY,
						}
					})
				},
				error: this.failConnection,
				iceState: (state) => {
					log('venueless', 'info', `Video publisher ICE state: ${state}`)
					if (state === 'failed') {
						this.failConnection(`ICE connection ${state}`)
					}
				},
				mediaState: (medium, on) => {
					log('venueless', 'info', `Janus ${on ? 'started' : 'stopped'} receiving local ${medium}`)
					if (on && medium === 'video' && this.publishedWithVideo) {
						this.publishingState = 'published'
						this.publishingError = null
					}
				},
				webrtcState: (on) => {
					log('venueless', 'info', `Video publisher WebRTC is ${on ? 'up' : 'down'}`)
				},
				onmessage: this.onVideoPublisherMessage,
				onlocalstream: this.onLocalVideoStream,
				slowLink: (uplink) => {
					if (uplink) this.handleVideoSlowLink()
				},
				oncleanup: () => {
					log('venueless', 'info', 'Video publisher cleanup received')
					this.publishedWithVideo = false
					this.localCameraActive = false
				},
			})
		},
		onAudioPublisherMessage(msg, jsep) {
			const event = msg.videoroom
			log('janus-audio-publisher', 'debug', {
				action: 'onAudioPublisherMessage',
				event,
				msg,
				hasJsep: Boolean(jsep),
				jsepHasAudio: Boolean(jsep?.sdp?.includes('m=audio')),
				audioPublisherJoined: this.audioPublisherJoined,
				micMuted: this.micMuted,
			})
			if (event === 'joined') {
				this.ourAudioId = msg.id
				this.ourPrivateId = msg.private_id
				this.audioPublisherJoined = true
				this.connectionState = 'connected'
				this.connectionError = null
				this.retryInterval = 1000
				this.publishAudioMedia()
				this.attachVideoPublisher()
				this.subscribeToPublishers(msg.publishers || [])
			} else {
				this.handlePublisherEvent(msg)
			}
			if (jsep) {
				log('janus-audio-publisher', 'debug', {
					action: 'handleRemoteJsep',
					jsepType: jsep?.type,
					jsepHasAudio: Boolean(jsep?.sdp?.includes('m=audio')),
				})
				this.audioPublisherHandle.handleRemoteJsep({jsep})
				this.finishAudioPublish()
			} else if (event === 'event' && msg.configured === 'ok') {
				this.finishAudioPublish()
			}
		},
		onVideoPublisherMessage(msg, jsep) {
			const event = msg.videoroom
			log('janus-video-publisher', 'debug', {
				event,
				msg,
				hasJsep: Boolean(jsep),
				publishedWithVideo: this.publishedWithVideo,
				videoPublisherJoined: this.videoPublisherJoined,
				cameraEnabled: this.cameraEnabled,
			})
			if (event === 'joined') {
				this.ourVideoId = msg.id
				this.videoPublisherJoined = true
				if (this.cameraEnabled) {
					this.publishVideoMedia()
				}
				this.subscribeToPublishers(msg.publishers || [])
			} else {
				this.handlePublisherEvent(msg)
			}
			if (jsep) {
				this.videoPublisherHandle.handleRemoteJsep({jsep})
				this.finishVideoPublish()
				if (this.publishedWithVideo && !msg.video_codec) {
					this.cameraEnabled = false
					this.publishedWithVideo = false
					this.stopLocalCameraTracks()
					this.publishingError = 'The server rejected the selected camera stream.'
				}
			} else if (event === 'event' && msg.configured === 'ok') {
				this.finishVideoPublish()
			}
		},
		handlePublisherEvent(msg) {
			const event = msg.videoroom
			log('janus-publisher-event', 'debug', {
				action: 'handlePublisherEvent',
				event,
				msg,
			})
			if (event === 'destroyed') {
				this.failConnection('Room destroyed', false)
			} else if (event === 'event') {
				if (msg.publishers) this.subscribeToPublishers(msg.publishers)
				if (msg.joining) {
					this.registerPublisherFeed(
						msg.joining.id,
						msg.joining.display,
						msg.joining.audio_codec,
						msg.joining.video_codec
					)
				}
				if (msg.leaving) this.removeRemoteFeed(msg.leaving)
				if (msg.unpublished) {
					if (msg.unpublished === 'ok') {
						return
					}
					this.removeRemoteFeed(msg.unpublished)
				}
				if (msg.error) {
					if (msg.error_code === 426) {
						this.failConnection('Room does not exist', false)
					} else {
						this.failConnection(`Server error: ${msg.error}`, false)
					}
				}
			}
		},
		async publishAudioMedia() {
			log('janus-audio-publisher', 'debug', {
				action: 'publishAudioMedia:start',
				hasHandle: Boolean(this.audioPublisherHandle),
				audioPublisherJoined: this.audioPublisherJoined,
				audioPublishInProgress: this.audioPublishInProgress,
				audioPublishQueued: this.audioPublishQueued,
				audioInput: localStorage.audioInput || '',
				micMuted: this.micMuted,
			})
			if (!this.audioPublisherHandle) return
			if (this.audioPublishInProgress) {
				log('janus-audio-publisher', 'debug', {
					action: 'publishAudioMedia:queued',
				})
				this.audioPublishQueued = true
				return
			}
			this.audioPublishInProgress = true
			this.publishingState = 'publishing'
			this.publishingError = null

			const nextAudioInput = localStorage.audioInput || ''
			const hadPeerConnection = Boolean(this.audioPublisherHandle.webrtcStuff?.pc)
			const media = {
				audioRecv: false,
				videoRecv: false,
				audioSend: true,
				videoSend: false,
			}

			media.audio = this.microphoneConstraints(nextAudioInput)
			if (hadPeerConnection && nextAudioInput !== this.audioInput) {
				media.replaceAudio = true
			}

			this.audioInput = nextAudioInput

			let explicitStream
			if (!hadPeerConnection) {
				try {
					explicitStream = await navigator.mediaDevices.getUserMedia({
						audio: media.audio,
						video: false,
					})
					log('janus-audio-publisher', 'debug', {
						action: 'getUserMedia:success',
						stream: summarizeStream(explicitStream),
					})
				} catch (error) {
					log('janus-audio-publisher', 'error', {
						action: 'getUserMedia:error',
						error: error?.message || error,
						name: error?.name,
					})
					this.finishAudioPublish()
					this.publishingState = 'failed'
					this.publishingError = error?.message || 'Could not publish microphone.'
					return
				}
			}

			const offerOptions = {
				media,
				success: (jsep) => {
					log('janus-audio-publisher', 'debug', {
						action: 'createOffer:success',
						jsepType: jsep?.type,
						hasSdpAudio: Boolean(jsep?.sdp?.includes('m=audio')),
						hasSdpVideo: Boolean(jsep?.sdp?.includes('m=video')),
					})
					this.audioPublisherHandle.send({
						message: {
							request: 'configure',
							audio: true,
							video: false,
						},
						jsep,
						success: () => {
							log('janus-audio-publisher', 'debug', {
								action: 'configure:send-success',
							})
							this.audioPublishTimeout = window.setTimeout(() => this.finishAudioPublish(), 4000)
						},
						error: (error) => {
							log('janus-audio-publisher', 'error', {
								action: 'configure:error',
								error: error?.message || error,
							})
							this.finishAudioPublish()
							this.publishingState = 'failed'
							this.publishingError = error?.message || error || 'Could not configure microphone.'
						},
					})
				},
				error: (error) => {
					log('janus-audio-publisher', 'error', {
						action: 'createOffer:error',
						error: error?.message || error,
						name: error?.name,
					})
					this.finishAudioPublish()
					this.publishingState = 'failed'
					this.publishingError = error?.message || 'Could not publish microphone.'
				},
			}
			if (explicitStream) {
				offerOptions.stream = explicitStream
			}
			this.audioPublisherHandle.createOffer(offerOptions)
		},
		async publishVideoMedia() {
			log('janus-video-publisher', 'debug', {
				action: 'publishVideoMedia:start',
				cameraEnabled: this.cameraEnabled,
				hasHandle: Boolean(this.videoPublisherHandle),
				videoPublisherJoined: this.videoPublisherJoined,
				videoPublishInProgress: this.videoPublishInProgress,
				videoPublishQueued: this.videoPublishQueued,
				videoInput: localStorage.videoInput || '',
			})
			if (!this.cameraEnabled) {
				this.unpublishVideoMedia()
				return
			}
			if (!this.videoPublisherHandle) {
				this.attachVideoPublisher()
				return
			}
			if (!this.videoPublisherJoined) {
				log('janus-video-publisher', 'warn', {
					action: 'publishVideoMedia:skip-not-joined',
					hasHandle: Boolean(this.videoPublisherHandle),
				})
				return
			}
			if (this.videoPublishInProgress) {
				this.videoPublishQueued = true
				return
			}
			this.videoPublishInProgress = true
			this.publishingState = 'publishing'
			this.publishingError = null

			const nextVideoInput = localStorage.videoInput || ''
			const hadPeerConnection = Boolean(this.videoPublisherHandle.webrtcStuff?.pc)
			const media = {
				audioRecv: false,
				videoRecv: false,
				audioSend: false,
				videoSend: true,
			}
			media.video = this.cameraConstraints(nextVideoInput)
			if (hadPeerConnection && nextVideoInput !== this.videoInput) {
				media.replaceVideo = true
			}
			this.videoInput = nextVideoInput

			let explicitStream
			if (!hadPeerConnection) {
				try {
					explicitStream = await navigator.mediaDevices.getUserMedia({
						audio: false,
						video: media.video,
					})
					log('janus-video-publisher', 'debug', {
						action: 'getUserMedia:success',
						stream: summarizeStream(explicitStream),
					})
				} catch (error) {
					log('janus-video-publisher', 'error', {
						action: 'getUserMedia:error',
						error: error?.message || error,
						name: error?.name,
					})
					this.finishVideoPublish()
					this.cameraEnabled = false
					this.publishedWithVideo = false
					this.localCameraActive = false
					localStorage.videoRequested = false
					this.publishingError = error?.message || 'Could not publish camera.'
					return
				}
			}

			const offerOptions = {
				media,
				simulcast: true,
				simulcast2: true,
				simulcastMaxBitrates: VIDEO_SIMULCAST_BITRATES,
				success: (jsep) => {
					log('janus-video-publisher', 'debug', {
						action: 'createOffer:success',
						jsepType: jsep?.type,
						hasSdpVideo: Boolean(jsep?.sdp?.includes('m=video')),
					})
					this.videoPublisherHandle.send({
						message: {
							request: 'configure',
							audio: false,
							video: true,
							bitrate: this.upstreamBitrate,
						},
						jsep,
						success: () => {
							log('janus-video-publisher', 'debug', {
								action: 'configure:send-success',
								bitrate: this.upstreamBitrate,
							})
							this.publishedWithVideo = true
							this.videoPublishTimeout = window.setTimeout(() => this.finishVideoPublish(), 4000)
						},
						error: (error) => {
							log('janus-video-publisher', 'error', {
								action: 'configure:error',
								error: error?.message || error,
							})
							this.finishVideoPublish()
							this.publishingError = error?.message || error || 'Could not configure camera.'
						},
					})
				},
				error: (error) => {
					log('janus-video-publisher', 'error', {
						action: 'createOffer:error',
						error: error?.message || error,
						name: error?.name,
					})
					this.finishVideoPublish()
					this.cameraEnabled = false
					this.publishedWithVideo = false
					this.localCameraActive = false
					localStorage.videoRequested = false
					this.publishingError = error?.message || 'Could not publish camera.'
				},
			}
			if (explicitStream) {
				offerOptions.stream = explicitStream
			}
			this.videoPublisherHandle.createOffer(offerOptions)
		},
		unpublishVideoMedia() {
			this.publishedWithVideo = false
			this.stopLocalCameraTracks()
			if (this.videoPublisherHandle?.webrtcStuff?.pc) {
				this.videoPublisherHandle.send({message: {request: 'unpublish'}})
			}
		},
		microphoneConstraints(audioInput) {
			if (!audioInput) {
				return true
			}
			const constraints = {
				echoCancellation: true,
				noiseSuppression: true,
				autoGainControl: true,
			}
			constraints.deviceId = {exact: audioInput}
			return constraints
		},
		cameraConstraints(videoInput) {
			if (!videoInput) {
				return true
			}
			const constraints = {
				width: {ideal: 1280},
				height: {ideal: 720},
				frameRate: {ideal: 30, max: 30},
			}
			constraints.deviceId = {exact: videoInput}
			return constraints
		},
		finishAudioPublish() {
			log('janus-audio-publisher', 'debug', {
				action: 'finishAudioPublish',
				hadTimeout: Boolean(this.audioPublishTimeout),
				audioPublishQueued: this.audioPublishQueued,
			})
			if (this.audioPublishTimeout) {
				window.clearTimeout(this.audioPublishTimeout)
				this.audioPublishTimeout = null
			}
			this.audioPublishInProgress = false
			if (this.audioPublishQueued) {
				this.audioPublishQueued = false
				this.$nextTick(this.publishAudioMedia)
			}
		},
		finishVideoPublish() {
			if (this.videoPublishTimeout) {
				window.clearTimeout(this.videoPublishTimeout)
				this.videoPublishTimeout = null
			}
			this.videoPublishInProgress = false
			if (this.videoPublishQueued) {
				this.videoPublishQueued = false
				this.$nextTick(this.publishVideoMedia)
			}
		},
		onLocalAudioStream(stream) {
			this.localAudioStream = stream
			log('janus-audio-publisher', 'debug', {
				action: 'onLocalAudioStream',
				stream: summarizeStream(stream),
				automute: this.automute,
				automuteApplied: this.automuteApplied,
				micMuted: this.micMuted,
			})
			this.registerAudioMeter('local', stream)
			if (this.automute && !this.automuteApplied) {
				this.micMuted = true
				this.automuteApplied = true
			}
			this.applyMicState()
			this.publishingState = 'published'
			this.publishingError = null
		},
		onLocalVideoStream(stream) {
			this.localVideoStream = stream
			this.localCameraActive = stream.getVideoTracks().some(track => track.readyState === 'live')
			if (this.localCameraActive && !this.localCameraOnAt) {
				this.localCameraOnAt = Date.now()
			}
			log('janus-video-publisher', 'debug', {
				action: 'onLocalVideoStream',
				localCameraActive: this.localCameraActive,
				stream: summarizeStream(stream),
			})
			this.attachLocalVideo(stream)
			this.publishingState = 'published'
			this.publishingError = null
		},
		applyMicState() {
			if (!this.audioPublisherHandle) {
				log('janus-audio-publisher', 'debug', {
					action: 'applyMicState:skip-no-handle',
					micMuted: this.micMuted,
				})
				return
			}
			log('janus-audio-publisher', 'debug', {
				action: 'applyMicState',
				micMuted: this.micMuted,
				handleAudioMuted: this.audioPublisherHandle.isAudioMuted(),
			})
			if (this.micMuted && !this.audioPublisherHandle.isAudioMuted()) {
				this.audioPublisherHandle.muteAudio()
			} else if (!this.micMuted && this.audioPublisherHandle.isAudioMuted()) {
				this.audioPublisherHandle.unmuteAudio()
			}
		},
		attachLocalVideo(stream) {
			this.$nextTick(() => {
				const video = this.singleRef(this.$refs.localVideo)
				if (!video) return
				this.attachLocalMediaElement(video, stream, 'video')
			})
		},
		attachLocalMediaElement(element, stream, medium) {
			if (!element || !stream) return
			if (element.srcObject !== stream) {
				Janus.attachMediaStream(element, stream)
			}
			element.muted = true
			if (!element.paused && element.readyState > 0) return
			const playPromise = element.play()
			if (playPromise?.catch) {
				playPromise.catch(error => {
					log('venueless', 'warn', `Local ${medium} playback did not start automatically: ${error}`)
				})
			}
		},
		syncLocalMediaElements() {
			if (this.localVideoStream) {
				this.attachLocalMediaElement(this.singleRef(this.$refs.localVideo), this.localVideoStream, 'video')
			}
			if (this.screenShareStream) {
				this.attachLocalMediaElement(this.singleRef(this.$refs.localScreenVideo), this.screenShareStream, 'screen')
			}
		},
		toggleMic() {
			if (!this.audioPublisherHandle) {
				log('janus-audio-publisher', 'debug', {
					action: 'toggleMic:skip-no-handle',
				})
				return
			}
			this.micMuted = !this.micMuted
			log('janus-audio-publisher', 'debug', {
				action: 'toggleMic',
				micMuted: this.micMuted,
			})
			this.applyMicState()
		},
		toggleCamera() {
			this.cameraEnabled = !this.cameraEnabled
			localStorage.videoRequested = this.cameraEnabled
			log('janus-video-publisher', 'debug', {
				action: 'toggleCamera',
				cameraEnabled: this.cameraEnabled,
			})
			if (this.cameraEnabled) {
				this.publishVideoMedia()
			} else {
				this.unpublishVideoMedia()
			}
		},
		toggleScreenShare() {
			if (this.screenShareState === 'published') {
				this.stopScreenShare()
				return
			}
			if (this.screenShareState === 'unpublished' || this.screenShareState === 'failed') {
				this.startScreenShare()
			}
		},
		async startScreenShare() {
			log('janus-screen-publisher', 'debug', {
				action: 'startScreenShare',
				state: this.screenShareState,
				hasHandle: Boolean(this.screenShareHandle),
				screenShareSessionId: this.janusScreenShareSessionId,
			})
			this.screenShareError = null
			this.screenShareState = 'publishing'
			let stream
			try {
				stream = await this.getDisplayMedia()
				log('janus-screen-publisher', 'debug', {
					action: 'getDisplayMedia:success',
					stream: summarizeStream(stream),
				})
			} catch (error) {
				log('janus-screen-publisher', 'error', {
					action: 'getDisplayMedia:error',
					error: error?.message || error,
					name: error?.name,
				})
				this.failScreenShare(error, ['AbortError', 'NotAllowedError'].includes(error?.name))
				return
			}
			if (this.screenShareHandle) {
				this.publishScreenShare(stream)
				return
			}
			this.pendingScreenShareStream = stream
			this.janus.attach({
				plugin: 'janus.plugin.videoroom',
				opaqueId: `${this.user.id}-screen`,
				success: (pluginHandle) => {
					this.screenShareHandle = pluginHandle
					log('janus-screen-publisher', 'debug', {
						action: 'attach:success',
						handleId: pluginHandle.getId(),
						screenShareSessionId: this.janusScreenShareSessionId,
					})
					this.screenShareHandle.send({
						message: {
							request: 'join',
							room: this.janusRoomId,
							ptype: 'publisher',
							token: this.token,
							id: this.janusScreenShareSessionId,
							display: SCREEN_SHARE_DISPLAY,
						}
					})
				},
				error: (error) => {
					log('janus-screen-publisher', 'error', {
						action: 'attach:error',
						error: error?.message || error,
						name: error?.name,
					})
					this.stopPendingScreenShareTracks()
					this.failScreenShare(error)
				},
				mediaState: (medium, on) => {
					log('janus-screen-publisher', 'debug', {
						action: 'mediaState',
						medium,
						on,
					})
					if (medium === 'video' && on) {
						this.screenShareState = 'published'
						this.screenShareError = null
					}
				},
				webrtcState: (on) => {
					log('janus-screen-publisher', 'debug', {
						action: 'webrtcState',
						on,
					})
				},
				onmessage: this.onScreenShareMessage,
				oncleanup: () => {
					log('janus-screen-publisher', 'debug', {
						action: 'oncleanup',
					})
					this.resetScreenShare()
				},
			})
		},
		onScreenShareMessage(msg, jsep) {
			const event = msg.videoroom
			log('janus-screen-publisher', 'debug', {
				action: 'onScreenShareMessage',
				event,
				msg,
				hasJsep: Boolean(jsep),
				jsepHasVideo: Boolean(jsep?.sdp?.includes('m=video')),
				jsepHasAudio: Boolean(jsep?.sdp?.includes('m=audio')),
			})
			if (event === 'joined') {
				const stream = this.pendingScreenShareStream
				this.pendingScreenShareStream = null
				if (stream) {
					this.publishScreenShare(stream)
				} else {
					this.failScreenShare('Screen sharing needs to be started again.')
				}
			} else if (event === 'event') {
				if (msg.unpublished === 'ok') {
					this.resetScreenShare()
					return
				}
				if (msg.error) {
					this.failScreenShare(msg.error)
				}
			} else if (event === 'destroyed') {
				this.failScreenShare('Room destroyed')
			}
			if (jsep) {
				this.screenShareHandle.handleRemoteJsep({jsep})
				if (!msg.video_codec) {
					this.failScreenShare('The server rejected the selected screen stream.')
				}
			}
		},
		async publishScreenShare(stream = null) {
			log('janus-screen-publisher', 'debug', {
				action: 'publishScreenShare:start',
				state: this.screenShareState,
			})
			this.screenShareState = 'publishing'
			this.stopScreenShareTracks()
			if (!stream) {
				this.failScreenShare('Screen sharing needs to be started again.')
				return
			}
			this.screenShareStream = stream
			stream.getVideoTracks()[0].onended = () => {
				if (this.screenShareState === 'published' || this.screenShareState === 'publishing') {
					this.stopScreenShare()
				}
			}
			await this.$nextTick()
			const localScreenVideo = this.singleRef(this.$refs.localScreenVideo)
			if (localScreenVideo) {
				Janus.attachMediaStream(localScreenVideo, stream)
				localScreenVideo.muted = true
				const playPromise = localScreenVideo.play()
				if (playPromise?.catch) {
					playPromise.catch(error => {
						log('venueless', 'warn', `Local screen playback did not start automatically: ${error}`)
					})
				}
			}
			this.onResize()
			const hasAudio = stream.getAudioTracks().length > 0
			this.screenShareHandle.createOffer({
				stream,
				media: {
					audioRecv: false,
					videoRecv: false,
					audioSend: hasAudio,
					videoSend: true,
				},
				success: (jsep) => {
					log('janus-screen-publisher', 'debug', {
						action: 'createOffer:success',
						hasAudio,
						jsepType: jsep?.type,
						hasSdpVideo: Boolean(jsep?.sdp?.includes('m=video')),
						hasSdpAudio: Boolean(jsep?.sdp?.includes('m=audio')),
					})
					this.screenShareHandle.send({
						message: {
							request: 'configure',
							audio: hasAudio,
							video: true,
							bitrate: MAX_BITRATE,
						},
						jsep,
						error: (error) => {
							log('janus-screen-publisher', 'error', {
								action: 'configure:error',
								error: error?.message || error,
								name: error?.name,
							})
							this.failScreenShare(error)
						},
					})
				},
				error: (error) => {
					log('janus-screen-publisher', 'error', {
						action: 'createOffer:error',
						error: error?.message || error,
						name: error?.name,
					})
					this.failScreenShare(error)
				},
			})
		},
		async getDisplayMedia() {
			if (!navigator.mediaDevices?.getDisplayMedia) {
				throw new Error('Screen sharing is not supported by this browser.')
			}
			const isSafari = Janus.webRTCAdapter?.browserDetails?.browser === 'safari'
			const constraints = {
				video: {
					frameRate: {ideal: 15, max: 30},
					width: {max: 1920},
					height: {max: 1080},
				},
				audio: isSafari ? false : {
					echoCancellation: true,
					noiseSuppression: true,
					autoGainControl: true,
				},
			}
			let stream
			try {
				stream = await navigator.mediaDevices.getDisplayMedia(constraints)
			} catch (error) {
				if (isSafari || !['TypeError', 'OverconstrainedError', 'ConstraintNotSatisfiedError'].includes(error?.name)) {
					throw error
				}
				stream = await navigator.mediaDevices.getDisplayMedia({
					...constraints,
					audio: false,
				})
			}
			if (!stream.getVideoTracks().length) {
				throw new Error('No screen video track was selected.')
			}
			return stream
		},
		singleRef(ref) {
			return Array.isArray(ref) ? ref[0] : ref
		},
		stopScreenShare() {
			log('janus-screen-publisher', 'debug', {
				action: 'stopScreenShare',
				state: this.screenShareState,
				hasHandle: Boolean(this.screenShareHandle),
			})
			this.screenShareState = 'unpublishing'
			this.stopPendingScreenShareTracks()
			this.stopScreenShareTracks()
			if (!this.screenShareHandle) {
				this.resetScreenShare()
				return
			}
			this.screenShareHandle.send({message: {request: 'unpublish'}})
		},
		stopScreenShareTracks() {
			if (!this.screenShareStream) return
			log('janus-screen-publisher', 'debug', {
				action: 'stopScreenShareTracks',
				stream: summarizeStream(this.screenShareStream),
			})
			for (const track of this.screenShareStream.getTracks()) {
				track.onended = null
				track.stop()
			}
			this.screenShareStream = null
		},
		stopPendingScreenShareTracks() {
			if (!this.pendingScreenShareStream) return
			log('janus-screen-publisher', 'debug', {
				action: 'stopPendingScreenShareTracks',
				stream: summarizeStream(this.pendingScreenShareStream),
			})
			for (const track of this.pendingScreenShareStream.getTracks()) {
				track.onended = null
				track.stop()
			}
			this.pendingScreenShareStream = null
		},
		resetScreenShare() {
			log('janus-screen-publisher', 'debug', {
				action: 'resetScreenShare',
				state: this.screenShareState,
			})
			this.stopPendingScreenShareTracks()
			this.stopScreenShareTracks()
			this.screenShareState = 'unpublished'
		},
		failScreenShare(error, silent = false) {
			log('janus-screen-publisher', 'error', {
				action: 'failScreenShare',
				error: error?.message || error,
				name: error?.name,
				silent,
			})
			this.stopPendingScreenShareTracks()
			this.stopScreenShareTracks()
			this.screenShareState = 'failed'
			this.screenShareError = silent ? null : (error?.message || error || 'Screen sharing failed.')
			if (silent) {
				this.screenShareState = 'unpublished'
			}
		},
		subscribeToPublishers(publishers) {
			log('janus-subscriber', 'debug', {
				action: 'subscribeToPublishers',
				publishers,
			})
			for (const publisher of publishers) {
				this.registerPublisherFeed(publisher.id, publisher.display, publisher.audio_codec, publisher.video_codec)
			}
			this.syncVisibleVideoSubscriptions()
		},
		registerPublisherFeed(feedId, display, audioCodec, videoCodec) {
			const id = this.normalizeFeedId(feedId)
			const feedType = this.feedTypeFromPublisher(display, audioCodec, videoCodec)
			const isScreenShare = feedType === 'screen'
			if (this.isOwnFeed(id)) {
				this.removeRemoteFeed(id, false)
				return
			}
			const existingFeed = this.remoteFeeds.find(feed => this.feedIdEquals(feed.id, id))
			const wasCameraOn = Boolean(existingFeed?.cameraOn)
			const feed = existingFeed || {
				id,
				handle: null,
				display,
				feedType,
				isScreenShare,
				audioCodec,
				videoCodec,
				attached: false,
				muted: false,
				user: null,
				stream: null,
				hasVideo: false,
				cameraOn: false,
				cameraOnAt: null,
				paused: false,
				requestedLayer: null,
			}
			feed.display = display
			feed.audioCodec = audioCodec
			feed.videoCodec = videoCodec
			feed.feedType = feedType
			feed.isScreenShare = isScreenShare
			if (feedType === 'video' && videoCodec && !feed.cameraOn) {
				feed.cameraOn = true
				feed.cameraOnAt = Date.now()
			}
			if (feedType === 'screen' && videoCodec) {
				feed.hasVideo = true
			}
			this.upsertRemoteFeed(feed)
			this.fetchFeedUser(id)
			if (feedType === 'video' && videoCodec && !wasCameraOn) {
				this.$nextTick(() => this.syncVisibleVideoSubscriptions())
			}
			if (feedType === 'audio' || feedType === 'screen') {
				this.subscribeToFeed(id, display, audioCodec, videoCodec)
			}
		},
		subscribeToFeed(feedId, display, audioCodec, videoCodec) {
			const id = this.normalizeFeedId(feedId)
			const feedType = this.feedTypeFromPublisher(display, audioCodec, videoCodec)
			const isScreenShare = feedType === 'screen'
			log('janus-subscriber', 'debug', {
				action: 'subscribeToFeed:seen',
				feedId: id,
				display,
				audioCodec,
				videoCodec,
				feedType,
				videoOutput: this.videoOutput,
				isOwnFeed: this.isOwnFeed(feedId),
			})
			if (this.isOwnFeed(feedId) || (!this.videoOutput && feedType === 'video') ||
					(feedType === 'video' && !this.visibleVideoLayerByFeedId[id])) {
				log('janus-subscriber', 'debug', {
					action: 'subscribeToFeed:skip-own-or-output',
					feedId: id,
					feedType,
				})
				return
			}
			const existingFeed = this.remoteFeeds.find(feed => this.feedIdEquals(feed.id, id))
			if (existingFeed) {
				if (existingFeed.handle || this.subscribingFeedIds.some(subscribingId => this.feedIdEquals(subscribingId, id))) {
					log('janus-subscriber', 'debug', {
						action: 'subscribeToFeed:skip-existing-handle',
						feedId: id,
						feedType,
					})
					return
				}
				existingFeed.display = display
				existingFeed.audioCodec = audioCodec
				existingFeed.videoCodec = videoCodec
				existingFeed.feedType = feedType
				existingFeed.isScreenShare = isScreenShare
				existingFeed.paused = false
				this.pausedVideoFeedIds = this.pausedVideoFeedIds.filter(item => !this.feedIdEquals(item, id))
				this.upsertRemoteFeed(existingFeed)
			} else if (this.subscribingFeedIds.some(subscribingId => this.feedIdEquals(subscribingId, id))) {
				log('janus-subscriber', 'debug', {
					action: 'subscribeToFeed:skip-already-subscribing',
					feedId: id,
				})
				return
			}
			this.subscribingFeedIds.push(id)
			let remoteHandle = null
			this.janus.attach({
				plugin: 'janus.plugin.videoroom',
				opaqueId: String(this.user.id),
				success: (pluginHandle) => {
					remoteHandle = pluginHandle
					const subscribe = {
						request: 'join',
						room: this.janusRoomId,
						ptype: 'subscriber',
						feed: Number(id),
						private_id: this.ourPrivateId,
						offer_audio: true,
						offer_video: isScreenShare || (feedType === 'video' && this.videoOutput),
					}
					if (Janus.webRTCAdapter.browserDetails.browser === 'safari' &&
						(videoCodec === 'vp9' || (videoCodec === 'vp8' && !Janus.safariVp8))) {
						subscribe.offer_video = false
					}
					log('janus-subscriber', 'debug', {
						action: 'subscribeToFeed:send-join',
						feedId: id,
						subscribe,
					})
					remoteHandle.send({message: subscribe})
				},
				error: (error) => {
					this.unmarkSubscribing(feedId)
					log('venueless', 'error', `Could not attach subscriber for ${feedId}: ${error}`)
				},
				onmessage: (msg, jsep) => {
					this.onSubscriberMessage(remoteHandle, feedId, display, feedType, audioCodec, videoCodec, msg, jsep)
				},
				onlocalstream: () => {},
				onremotestream: (stream) => {
					this.onRemoteStream(feedId, stream)
				},
				onremotetrack: (track, mid, on) => {
					this.onRemoteTrack(feedId, track, on)
				},
				webrtcState: (on) => {
					log('venueless', 'info', `Subscriber ${feedId} WebRTC is ${on ? 'up' : 'down'}`)
				},
				slowLink: (uplink) => {
					if (!uplink) this.downstreamSlowLinkCount++
				},
				oncleanup: () => {
					this.clearRemoteFeedHandle(feedId)
				},
			})
		},
		onSubscriberMessage(handle, feedId, display, feedType, audioCodec, videoCodec, msg, jsep) {
			const event = msg.videoroom
			log('janus-subscriber', 'debug', {
				action: 'onSubscriberMessage',
				feedId: this.normalizeFeedId(feedId),
				display,
				feedType,
				audioCodec,
				videoCodec,
				event,
				msg,
				hasJsep: Boolean(jsep),
				jsepHasVideo: Boolean(jsep?.sdp?.includes('m=video')),
			})
			if (msg.error) {
				this.unmarkSubscribing(feedId)
				log('janus-subscriber', 'error', {
					action: 'onSubscriberMessage:error',
					feedId: this.normalizeFeedId(feedId),
					error: msg.error,
					errorCode: msg.error_code,
				})
				if (msg.error_code === 428) {
					handle?.detach()
					this.scheduleSubscriberRetry(feedId, display, audioCodec, videoCodec)
				} else {
					handle?.detach()
				}
				return
			}
			if (event === 'attached') {
				const id = this.normalizeFeedId(msg.id || feedId)
				this.unmarkSubscribing(id)
				this.clearSubscriberRetry(id)
				const existingFeed = this.remoteFeeds.find(item => this.feedIdEquals(item.id, id))
				this.upsertRemoteFeed({
					...(existingFeed || {}),
					id,
					handle,
					display,
					feedType,
					isScreenShare: feedType === 'screen',
					audioCodec,
					videoCodec,
					attached: false,
					muted: existingFeed?.muted || false,
					user: existingFeed?.user || null,
					stream: null,
					paused: false,
					requestedLayer: null,
				})
				this.pausedVideoFeedIds = this.pausedVideoFeedIds.filter(item => !this.feedIdEquals(item, id))
				if (!existingFeed?.user) {
					this.fetchFeedUser(id)
				}
			}
			if (jsep) {
				handle.createAnswer({
					jsep,
					media: {
						audioSend: false,
						videoSend: false,
					},
					success: (answer) => {
						log('janus-subscriber', 'debug', {
							action: 'createAnswer:success',
							feedId: this.normalizeFeedId(feedId),
							answerHasVideo: Boolean(answer?.sdp?.includes('m=video')),
						})
						handle.send({message: {request: 'start', room: this.janusRoomId}, jsep: answer})
						if (feedType === 'video') {
							this.configureSubscriberLayer(feedId, this.visibleVideoLayerByFeedId[this.normalizeFeedId(feedId)] || 'low')
						}
						this.syncRemoteTracksFromPeerConnection(handle, feedId)
						window.setTimeout(() => this.syncRemoteTracksFromPeerConnection(handle, feedId), 500)
					},
					error: (error) => {
						log('janus-subscriber', 'error', {
							action: 'createAnswer:error',
							feedId: this.normalizeFeedId(feedId),
							error: error?.message || error,
							name: error?.name,
						})
						this.removeRemoteFeed(feedId)
						log('venueless', 'error', `Could not answer subscriber ${feedId}: ${error}`)
					},
				})
			}
		},
		scheduleSubscriberRetry(feedId, display, audioCodec, videoCodec) {
			const id = this.normalizeFeedId(feedId)
			if (this.cleaningUp || this.isOwnFeed(id)) return
			const retryCount = (this.subscriberRetryCounts[id] || 0) + 1
			if (retryCount > 4) {
				log('janus-subscriber', 'warn', {
					action: 'scheduleSubscriberRetry:give-up',
					feedId: id,
				})
				return
			}
			this.subscriberRetryCounts[id] = retryCount
			if (this.subscriberRetryTimeouts[id]) {
				window.clearTimeout(this.subscriberRetryTimeouts[id])
			}
			const delay = retryCount * 750
			log('janus-subscriber', 'debug', {
				action: 'scheduleSubscriberRetry',
				feedId: id,
				retryCount,
				delay,
			})
			this.subscriberRetryTimeouts[id] = window.setTimeout(() => {
				delete this.subscriberRetryTimeouts[id]
				this.subscribeToFeed(feedId, display, audioCodec, videoCodec)
			}, delay)
		},
		clearSubscriberRetry(feedId) {
			const id = this.normalizeFeedId(feedId)
			if (this.subscriberRetryTimeouts[id]) {
				window.clearTimeout(this.subscriberRetryTimeouts[id])
				delete this.subscriberRetryTimeouts[id]
			}
			delete this.subscriberRetryCounts[id]
		},
		syncVisibleVideoSubscriptions() {
			if (!this.janus || this.cleaningUp) return
			const previousVisible = new Set(this.visibleVideoFeedIdsSnapshot.map(this.normalizeFeedId))
			const nextVisible = new Set(this.visibleVideoParticipantIds.map(this.normalizeFeedId))
			for (const id of previousVisible) {
				if (!nextVisible.has(id)) {
					this.pauseVideoFeed(id)
				}
			}
			for (const id of nextVisible) {
				const feed = this.remoteFeeds.find(item => this.feedIdEquals(item.id, id))
				if (!feed || feed.feedType !== 'video') continue
				if (feed.handle) {
					this.configureSubscriberLayer(id, this.visibleVideoLayerByFeedId[id])
				} else {
					this.subscribeToFeed(id, feed.display, feed.audioCodec, feed.videoCodec)
				}
			}
			this.visibleVideoFeedIdsSnapshot = Array.from(nextVisible)
			log('janus-subscriber', 'debug', {
				action: 'syncVisibleVideoSubscriptions',
				previous: Array.from(previousVisible),
				next: Array.from(nextVisible),
				layers: this.visibleVideoLayerByFeedId,
			})
		},
		pauseVideoFeed(feedId) {
			const id = this.normalizeFeedId(feedId)
			const feed = this.remoteFeeds.find(item => this.feedIdEquals(item.id, id))
			if (!feed || feed.feedType !== 'video') return
			log('janus-subscriber', 'debug', {
				action: 'pauseVideoFeed',
				feedId: id,
				hasHandle: Boolean(feed.handle),
			})
			this.unmarkSubscribing(id)
			this.clearSubscriberRetry(id)
			feed.paused = true
			if (!this.pausedVideoFeedIds.some(item => this.feedIdEquals(item, id))) {
				this.pausedVideoFeedIds.push(id)
			}
			if (feed.handle) {
				feed.handle.detach()
			}
			this.closeAudioMeter(id)
			feed.handle = null
			feed.stream = null
			feed.attached = false
			feed.hasVideo = false
			feed.requestedLayer = null
			this.upsertRemoteFeed(feed)
		},
		clearRemoteFeedHandle(feedId) {
			const id = this.normalizeFeedId(feedId)
			const feed = this.remoteFeeds.find(item => this.feedIdEquals(item.id, id))
			if (!feed) return
			log('janus-subscriber', 'debug', {
				action: 'clearRemoteFeedHandle',
				feedId: id,
				feedType: feed.feedType,
				paused: feed.paused,
				paginationPaused: this.pausedVideoFeedIds.some(item => this.feedIdEquals(item, id)),
			})
			this.closeAudioMeter(id)
			feed.handle = null
			feed.stream = null
			feed.attached = false
			if (feed.feedType === 'video' && (feed.paused || this.pausedVideoFeedIds.some(item => this.feedIdEquals(item, id)))) {
				feed.hasVideo = false
				this.upsertRemoteFeed(feed)
			} else {
				this.removeRemoteFeed(id, false)
			}
		},
		configureSubscriberLayer(feedId, layer) {
			const id = this.normalizeFeedId(feedId)
			const feed = this.remoteFeeds.find(item => this.feedIdEquals(item.id, id))
			if (!feed?.handle || feed.feedType !== 'video' || !layer || feed.requestedLayer === layer) return
			const substream = SIMULCAST_SUBSTREAMS[layer]
			if (substream === undefined) return
			feed.requestedLayer = layer
			log('janus-subscriber', 'debug', {
				action: 'configureSubscriberLayer',
				feedId: id,
				layer,
				substream,
			})
			feed.handle.send({
				message: {
					request: 'configure',
					substream,
					temporal: substream,
				}
			})
			this.upsertRemoteFeed(feed)
		},
		expectedTrackKindsForFeed(feed) {
			if (feed.feedType === 'audio') return new Set(['audio'])
			if (feed.feedType === 'video') return new Set(['video'])
			return new Set(['audio', 'video'])
		},
		onRemoteTrack(feedId, track, on) {
			if (!track) return
			const id = this.normalizeFeedId(feedId)
			const feed = this.remoteFeeds.find(item => this.feedIdEquals(item.id, id))
			log('janus-subscriber', 'debug', {
				action: 'onRemoteTrack',
				feedId: id,
				feedType: feed?.feedType,
				on,
				track: summarizeTrack(track),
				hasFeed: Boolean(feed),
			})
			if (!feed) return
			if (!this.expectedTrackKindsForFeed(feed).has(track.kind)) return
			if (!feed.stream) {
				feed.stream = new MediaStream()
			}
			if (on) {
				if (!feed.stream.getTracks().some(existingTrack => existingTrack.id === track.id)) {
					feed.stream.addTrack(track)
				}
				if (feed.feedType === 'video' && track.kind === 'video' && track.readyState === 'live' && !feed.cameraOn) {
					feed.cameraOn = true
					feed.cameraOnAt = Date.now()
				}
			} else {
				for (const existingTrack of feed.stream.getTracks().filter(item => item.id === track.id)) {
					feed.stream.removeTrack(existingTrack)
				}
				if (feed.feedType === 'video' && track.kind === 'video' && !feed.stream.getVideoTracks().length) {
					feed.cameraOn = false
					feed.cameraOnAt = null
				}
			}
			this.applyRemoteStream(feed, feed.stream)
		},
		onRemoteStream(feedId, stream) {
			const id = this.normalizeFeedId(feedId)
			const feed = this.remoteFeeds.find(item => this.feedIdEquals(item.id, id))
			log('janus-subscriber', 'debug', {
				action: 'onRemoteStream',
				feedId: id,
				stream: summarizeStream(stream),
				hasFeed: Boolean(feed),
			})
			if (!feed) return
			this.applyRemoteStream(feed, stream)
		},
		syncRemoteTracksFromPeerConnection(handle, feedId) {
			const id = this.normalizeFeedId(feedId)
			const feed = this.remoteFeeds.find(item => this.feedIdEquals(item.id, id))
			const pc = handle?.webrtcStuff?.pc
			if (!feed || !pc?.getReceivers) return
			const expectedKinds = this.expectedTrackKindsForFeed(feed)
			const tracks = pc.getReceivers()
				.map(receiver => receiver.track)
				.filter(track => track && track.readyState !== 'ended' && expectedKinds.has(track.kind))
			log('janus-subscriber', 'debug', {
				action: 'syncRemoteTracksFromPeerConnection',
				feedId: id,
				feedType: feed.feedType,
				hasFeed: Boolean(feed),
				hasPeerConnection: Boolean(pc),
				tracks: tracks.map(summarizeTrack),
			})
			if (!tracks.length) return
			const stream = feed.stream || new MediaStream()
			for (const track of tracks) {
				if (!stream.getTracks().some(existingTrack => existingTrack.id === track.id)) {
					stream.addTrack(track)
				}
			}
			this.applyRemoteStream(feed, stream)
		},
		applyRemoteStream(feed, stream) {
			const id = this.normalizeFeedId(feed.id)
			feed.stream = stream
			feed.attached = true
			feed.hasVideo = stream.getVideoTracks().length > 0 && (feed.isScreenShare || feed.feedType === 'video' || !!feed.videoCodec)
			if (feed.feedType === 'video') {
				const cameraLive = stream.getVideoTracks().some(track => track.readyState === 'live' && track.enabled)
				if (cameraLive && !feed.cameraOn) {
					feed.cameraOn = true
					feed.cameraOnAt = Date.now()
				} else if (!cameraLive && !feed.paused) {
					feed.cameraOn = false
					feed.cameraOnAt = null
				}
			}
			feed.muted = stream.getAudioTracks().every(track => !track.enabled)
			log('janus-subscriber', 'debug', {
				action: 'applyRemoteStream',
				feedId: id,
				feedType: feed.feedType,
				stream: summarizeStream(stream),
			})
			this.registerAudioMeter(id, stream)
			this.upsertRemoteFeed(feed)
			this.$nextTick(() => {
				this.attachRemoteFeedMedia(feed)
			})
		},
		findRemoteVideo(feedId) {
			return Array.from(this.$el.querySelectorAll('video[data-feed-id]'))
				.find(video => this.feedIdEquals(video.dataset.feedId, feedId))
		},
		findRemoteAudio(feedId) {
			return Array.from(this.$el.querySelectorAll('audio[data-audio-feed-id]'))
				.find(audio => this.feedIdEquals(audio.dataset.audioFeedId, feedId))
		},
		attachRemoteFeedMedia(feed) {
			if (this.cleaningUp || !this.$el?.isConnected || !feed?.stream) return
			const id = this.normalizeFeedId(feed.id)
			const element = feed.feedType === 'audio' ? this.findRemoteAudio(id) : this.findRemoteVideo(id)
			if (!element?.isConnected) return
			if (element.srcObject !== feed.stream) {
				Janus.attachMediaStream(element, feed.stream)
			}
			this.setMediaElementAudioOutput(element, {
				feedId: id,
				feedType: feed.feedType,
			})
			if (!element.paused && element.readyState > 0) return
			const playPromise = element.play()
			if (playPromise?.catch) {
				playPromise.catch(error => {
					if (this.cleaningUp || !this.$el?.isConnected) return
					log('janus-subscriber', 'warn', {
						action: 'attachRemoteFeedMedia:play-error',
						feedId: id,
						feedType: feed.feedType,
						error: error?.message || error,
						name: error?.name,
					})
				})
			}
		},
		syncRemoteFeedMediaElements() {
			for (const feed of this.remoteFeeds) {
				this.attachRemoteFeedMedia(feed)
			}
		},
		groupedRemoteTiles() {
			const participantTiles = new Map()
			for (const feed of this.remoteFeeds) {
				const id = this.normalizeFeedId(feed.id)
				if (feed.isScreenShare || feed.feedType === 'screen') {
					continue
				}
				const participantId = feed.user?.id ? this.normalizeFeedId(feed.user.id) : `feed-${id}`
				const existingTile = participantTiles.get(participantId) || {
					key: feed.user?.id ? `remote-user-${participantId}` : `remote-feed-${id}`,
					id: `user-${participantId}`,
					participantId,
					videoFeedId: null,
					audioFeedId: null,
					audioMeterFeedId: null,
					local: false,
					screen: false,
					focus: false,
					pinnable: true,
					user: feed.user,
					label: feed.user?.profile?.display_name || 'Participant',
					hasVideo: false,
					cameraOn: false,
					cameraOnAt: null,
					muted: true,
					audioLevel: 0,
					speaking: false
				}
				if (feed.user && !existingTile.user) {
					existingTile.user = feed.user
					existingTile.label = feed.user?.profile?.display_name || existingTile.label
				}
				if (feed.feedType === 'video') {
					existingTile.videoFeedId = id
					existingTile.cameraOn = Boolean(feed.cameraOn)
					existingTile.hasVideo = Boolean(
						feed.hasVideo &&
						feed.stream?.getVideoTracks().some(track => track.readyState === 'live' && !track.muted)
					)
					existingTile.cameraOnAt = feed.cameraOnAt
				}
				if (feed.feedType === 'audio' || feed.stream?.getAudioTracks().length) {
					existingTile.audioFeedId = id
					existingTile.audioMeterFeedId = id
					existingTile.muted = feed.muted
				}
				participantTiles.set(participantId, existingTile)
			}
			for (const tile of participantTiles.values()) {
				const meterId = tile.audioMeterFeedId || tile.audioFeedId || tile.videoFeedId
				tile.id = tile.videoFeedId || tile.audioFeedId || tile.id
				tile.audioLevel = meterId ? this.normalizedAudioLevel(meterId) : 0
				tile.speaking = meterId ? this.activeSpeakerId === meterId : false
			}
			const sortedParticipantTiles = Array.from(participantTiles.values())
				.sort((a, b) => a.label.localeCompare(b.label))
			return sortedParticipantTiles
		},
		upsertRemoteFeed(feed) {
			const index = this.remoteFeeds.findIndex(item => this.feedIdEquals(item.id, feed.id))
			log('janus-subscriber', 'debug', {
				action: 'upsertRemoteFeed',
				feedId: this.normalizeFeedId(feed.id),
				feedType: feed.feedType,
				isNew: index === -1,
				hasStream: Boolean(feed.stream),
				stream: summarizeStream(feed.stream),
				userId: feed.user?.id,
			})
			if (index === -1) {
				this.remoteFeeds.push(feed)
			} else {
				this.remoteFeeds.splice(index, 1, feed)
			}
			this.$nextTick(() => {
				this.syncRemoteFeedMediaElements()
			})
		},
		removeRemoteFeed(feedId, detach = true) {
			const id = this.normalizeFeedId(feedId)
			this.unmarkSubscribing(id)
			this.clearSubscriberRetry(id)
			const feed = this.remoteFeeds.find(item => this.feedIdEquals(item.id, id))
			log('janus-subscriber', 'debug', {
				action: 'removeRemoteFeed',
				feedId: id,
				detach,
				hadFeed: Boolean(feed),
				feedType: feed?.feedType,
				stream: summarizeStream(feed?.stream),
			})
			if (feed?.handle && detach) {
				feed.handle.detach()
			}
			this.closeAudioMeter(id)
			this.remoteFeeds = this.remoteFeeds.filter(item => !this.feedIdEquals(item.id, id))
			this.visibleVideoFeedIdsSnapshot = this.visibleVideoFeedIdsSnapshot.filter(item => !this.feedIdEquals(item, id))
			this.pausedVideoFeedIds = this.pausedVideoFeedIds.filter(item => !this.feedIdEquals(item, id))
			if (feed?.user?.id && this.focusTarget === this.normalizeFeedId(feed.user.id)) {
				this.focusTarget = null
			}
		},
		async fetchFeedUser(feedId) {
			try {
				log('janus-subscriber', 'debug', {
					action: 'fetchFeedUser:start',
					feedId: this.normalizeFeedId(feedId),
				})
				const user = await api.call('januscall.identify', {id: feedId})
				const feed = this.remoteFeeds.find(item => this.feedIdEquals(item.id, feedId))
				log('janus-subscriber', 'debug', {
					action: 'fetchFeedUser:success',
					feedId: this.normalizeFeedId(feedId),
					userId: user?.id,
					hasFeed: Boolean(feed),
				})
				if (feed) {
					feed.user = user
					this.upsertRemoteFeed(feed)
				}
			} catch (error) {
				log('janus-subscriber', 'warn', {
					action: 'fetchFeedUser:error',
					feedId: this.normalizeFeedId(feedId),
					error: error?.message || error,
					name: error?.name,
				})
			}
		},
		togglePin(tile) {
			if (!tile?.participantId) return
			this.focusTarget = this.focusTarget === tile.participantId ? null : tile.participantId
			this.currentVideoPage = 1
		},
		nextVideoPage() {
			this.currentVideoPage = Math.min(this.currentVideoPage + 1, this.paginationTotalPages)
		},
		previousVideoPage() {
			this.currentVideoPage = Math.max(this.currentVideoPage - 1, 1)
		},
		clampVideoPage() {
			if (this.currentVideoPage > this.paginationTotalPages) {
				this.currentVideoPage = this.paginationTotalPages
			}
			if (this.currentVideoPage < 1) {
				this.currentVideoPage = 1
			}
		},
		closeDevicePrompt() {
			this.showDevicePrompt = false
			const outputChanged = this.videoOutput !== (localStorage.videoOutput !== 'false')
			const audioChanged = this.audioInput !== (localStorage.audioInput || '')
			const videoChanged = this.videoInput !== (localStorage.videoInput || '')
			log('janus-devices', 'debug', {
				action: 'closeDevicePrompt',
				outputChanged,
				audioChanged,
				videoChanged,
				currentAudioInput: this.audioInput,
				nextAudioInput: localStorage.audioInput || '',
				currentVideoInput: this.videoInput,
				nextVideoInput: localStorage.videoInput || '',
				videoOutput: localStorage.videoOutput !== 'false',
			})
			this.videoOutput = localStorage.videoOutput !== 'false'
			if (outputChanged) {
				this.cleanup()
				this.onJanusInitialized()
				return
			}
			if (audioChanged) {
				this.publishAudioMedia()
			}
			if (videoChanged && this.cameraEnabled) {
				this.publishVideoMedia()
			}
			this.updateAudioOutputs()
		},
		updateAudioOutputs() {
			for (const element of this.$el.querySelectorAll('video[data-feed-id], audio[data-audio-feed-id]')) {
				this.setMediaElementAudioOutput(element, {
					feedId: element.dataset.feedId || element.dataset.audioFeedId,
					feedType: element.tagName.toLowerCase(),
				})
			}
		},
		setMediaElementAudioOutput(element, context = {}) {
			if (!element?.setSinkId) return
			const audioOutput = localStorage.audioOutput || ''
			log('janus-devices', 'debug', {
				action: 'setSinkId',
				...context,
				audioOutput,
			})
			element.setSinkId(audioOutput).catch(error => {
				log('janus-devices', 'warn', {
					action: 'setSinkId:error',
					...context,
					audioOutput,
					error: error?.message || error,
					name: error?.name,
				})
			})
		},
		disableIncomingVideo() {
			this.videoOutput = false
			localStorage.videoOutput = false
			for (const feed of this.remoteFeeds.slice()) {
				if (feed.feedType === 'video') {
					this.pauseVideoFeed(feed.id)
				}
			}
		},
		handleVideoSlowLink() {
			this.upstreamSlowLinkCount++
			if (this.upstreamSlowLinkCount <= 2) return
			const bitrate = Math.max(this.upstreamBitrate / 2, MIN_BITRATE)
			if (bitrate !== this.upstreamBitrate) {
				this.upstreamBitrate = bitrate
				this.videoPublisherHandle.send({
					message: {
						request: 'configure',
						audio: false,
						video: true,
						bitrate: this.upstreamBitrate,
					}
				})
				this.upstreamSlowLinkCount = 0
			} else if (this.upstreamSlowLinkCount > 5 && this.cameraEnabled) {
				this.cameraEnabled = false
				this.unpublishVideoMedia()
			}
		},
		registerAudioMeter(id, stream) {
			log('janus-audio-meter', 'debug', {
				action: 'registerAudioMeter',
				id,
				stream: summarizeStream(stream),
			})
			if (!stream.getAudioTracks().length) return
			this.closeAudioMeter(id)
			try {
				const meter = new SoundMeter(this.getAudioMeterContext())
				meter.connectToSource(stream)
				this.audioMeters[id] = meter
				log('janus-audio-meter', 'debug', {
					action: 'registerAudioMeter:success',
					id,
				})
			} catch (error) {
				log('janus-audio-meter', 'warn', {
					action: 'registerAudioMeter:error',
					id,
					error: error?.message || error,
					name: error?.name,
				})
			}
		},
		getAudioMeterContext() {
			if (this.audioMeterContext && this.audioMeterContext.state !== 'closed') {
				return this.audioMeterContext
			}
			const AudioContextConstructor = window.AudioContext || window.webkitAudioContext
			this.audioMeterContext = new AudioContextConstructor()
			return this.audioMeterContext
		},
		closeAudioMeter(id) {
			const meter = this.audioMeters[id]
			if (!meter) return
			log('janus-audio-meter', 'debug', {
				action: 'closeAudioMeter',
				id,
			})
			meter.stop()
			delete this.audioMeters[id]
			delete this.audioLevels[id]
			if (!Object.keys(this.audioMeters).length) {
				this.closeAudioMeterContext()
			}
		},
		closeAudioMeterContext() {
			if (this.audioMeterContext && this.audioMeterContext.state !== 'closed') {
				this.audioMeterContext.close()
			}
			this.audioMeterContext = null
		},
		refreshAudioLevels() {
			const levels = {}
			for (const [id, meter] of Object.entries(this.audioMeters)) {
				levels[id] = Number(meter.slow || 0)
			}
			this.audioLevels = levels
		},
		normalizedAudioLevel(id) {
			return Math.min(Number(this.audioLevels[id] || 0) * 12, 1)
		},
		audioMeterStyle(tile) {
			return {transform: `scaleX(${tile.audioLevel})`}
		},
		isFeedMuted(id) {
			if (id === 'local') return this.micMuted
			const feed = this.remoteFeeds.find(item => this.feedIdEquals(item.id, id))
			return Boolean(feed?.muted)
		},
		feedTypeFromPublisher(display, audioCodec, videoCodec) {
			if (display === SCREEN_SHARE_DISPLAY) return 'screen'
			if (display === USER_AUDIO_DISPLAY) return 'audio'
			if (display === USER_VIDEO_DISPLAY) return 'video'
			if (videoCodec) return 'video'
			if (audioCodec) return 'audio'
			return 'video'
		},
		isOwnFeed(feedId) {
			// Janus can report our separate publishers before it echoes the assigned ids.
			// Keep the configured local session ids in this check to avoid self-subscribing.
			return this.feedIdEquals(feedId, this.ourAudioId) ||
				this.feedIdEquals(feedId, this.ourVideoId) ||
				this.feedIdEquals(feedId, this.janusAudioSessionId) ||
				this.feedIdEquals(feedId, this.janusVideoSessionId) ||
				this.feedIdEquals(feedId, this.janusScreenShareSessionId)
		},
		unmarkSubscribing(feedId) {
			this.subscribingFeedIds = this.subscribingFeedIds.filter(id => !this.feedIdEquals(id, feedId))
		},
		normalizeFeedId(id) {
			return String(id)
		},
		feedIdEquals(a, b) {
			return this.normalizeFeedId(a) === this.normalizeFeedId(b)
		},
		feedLabel(feed) {
			if (feed.feedType === 'screen') {
				return feed.user?.profile?.display_name ? `${feed.user.profile.display_name}'s screen` : 'Shared screen'
			}
			return feed.user?.profile?.display_name || 'Participant'
		},
		stopLocalCameraTracks() {
			this.localCameraActive = false
			this.localCameraOnAt = null
			if (!this.localVideoStream) return
			for (const track of this.localVideoStream.getVideoTracks()) {
				track.stop()
			}
			const localVideo = this.singleRef(this.$refs.localVideo)
			if (localVideo) {
				localVideo.srcObject = null
			}
			this.localVideoStream = null
		},
		clearLocalMediaElements() {
			const localVideo = this.singleRef(this.$refs.localVideo)
			if (localVideo) {
				localVideo.srcObject = null
			}
			const localScreenVideo = this.singleRef(this.$refs.localScreenVideo)
			if (localScreenVideo) {
				localScreenVideo.srcObject = null
			}
		},
		stopStreamTracks(stream) {
			for (const track of stream.getTracks()) {
				track.onended = null
				track.stop()
			}
		},
		onResize() {
			if (!this.$refs.container) return
			if (this.hasFocusTile) {
				this.layout = {cols: 2, rows: Math.max(this.tiles.length - 1, 1)}
				return
			}
			const bbox = this.$refs.container.getBoundingClientRect()
			const padding = this.size === 'tiny' ? 0 : 32
			const gap = this.size === 'tiny' ? 0 : 12
			this.layout = calculateLayout(
				Math.max(bbox.width - padding, 1),
				Math.max(bbox.height - padding, 1),
				this.tiles.length,
				16 / 9,
				gap,
			)
		},
		async showUserCard(event, user) {
			this.selectedUser = user
			await this.$nextTick()
			const target = event.currentTarget
			createPopper(target, this.$refs.avatarCard.$refs.card, {
				placement: 'top',
				strategy: 'fixed',
				modifiers: [{
					name: 'preventOverflow',
					options: {
						padding: 8
					}
				}]
			})
		},
		cleanup({preserveConnectionFailure = false} = {}) {
			this.cleaningUp = true
			log('janus-lifecycle', 'debug', {
				action: 'cleanup:start',
				preserveConnectionFailure,
				connectionState: this.connectionState,
				hasJanus: Boolean(this.janus),
				hasAudioHandle: Boolean(this.audioPublisherHandle),
				hasVideoHandle: Boolean(this.videoPublisherHandle),
				hasScreenHandle: Boolean(this.screenShareHandle),
				localAudioStream: summarizeStream(this.localAudioStream),
				localVideoStream: summarizeStream(this.localVideoStream),
				screenShareStream: summarizeStream(this.screenShareStream),
				pendingScreenShareStream: summarizeStream(this.pendingScreenShareStream),
				remoteFeedCount: this.remoteFeeds.length,
			})
			this.suppressDestroyedState = preserveConnectionFailure
			this.stopPendingScreenShareTracks()
			this.stopScreenShareTracks()
			if (this.localAudioStream) {
				this.stopStreamTracks(this.localAudioStream)
			}
			if (this.localVideoStream) {
				this.stopStreamTracks(this.localVideoStream)
			}
			this.clearLocalMediaElements()
			for (const id of Object.keys(this.audioMeters)) {
				this.closeAudioMeter(id)
			}
			this.closeAudioMeterContext()
			this.remoteFeeds = []
			this.subscribingFeedIds = []
			this.visibleVideoFeedIdsSnapshot = []
			this.pausedVideoFeedIds = []
			this.currentVideoPage = 1
			this.focusTarget = null
			for (const id of Object.keys(this.subscriberRetryTimeouts)) {
				this.clearSubscriberRetry(id)
			}
			this.localAudioStream = null
			this.localVideoStream = null
			this.screenShareStream = null
			this.pendingScreenShareStream = null
			this.audioPublisherHandle = null
			this.videoPublisherHandle = null
			this.screenShareHandle = null
			this.ourAudioId = null
			this.ourVideoId = null
			this.ourPrivateId = null
			this.audioPublisherJoined = false
			this.videoPublisherJoined = false
			this.audioPublishInProgress = false
			this.audioPublishQueued = false
			this.videoPublishInProgress = false
			this.videoPublishQueued = false
			this.localCameraActive = false
			this.localCameraOnAt = null
			this.publishedWithVideo = false
			this.automuteApplied = false
			if (this.audioPublishTimeout) {
				window.clearTimeout(this.audioPublishTimeout)
				this.audioPublishTimeout = null
			}
			if (this.videoPublishTimeout) {
				window.clearTimeout(this.videoPublishTimeout)
				this.videoPublishTimeout = null
			}
			if (this.janus) {
				this.janus.destroy({cleanupHandles: true})
				this.janus = null
			}
			this.publishingState = 'unpublished'
			this.screenShareState = 'unpublished'
			if (!preserveConnectionFailure) {
				this.connectionState = 'disconnected'
				this.connectionError = null
				this.retryInterval = 1000
			}
			log('janus-lifecycle', 'debug', {
				action: 'cleanup:done',
				connectionState: this.connectionState,
			})
		},
		failConnection(error, retry = true) {
			log('janus-lifecycle', 'error', {
				action: 'failConnection',
				error: error?.message || error,
				name: error?.name,
				retry,
				retryInterval: this.retryInterval,
			})
			const retryInterval = this.retryInterval
			this.cleanup({preserveConnectionFailure: true})
			this.connectionState = 'failed'
			this.connectionError = error?.message || error || 'Unknown Janus connection error'
			if (retry) {
				this.connectionRetryTimeout = window.setTimeout(this.onJanusInitialized, retryInterval)
				this.retryInterval = retryInterval * 2
			}
		},
		leaveRoom() {
			log('janus-lifecycle', 'debug', {
				action: 'leaveRoom',
			})
			this.cleanup()
			this.$emit('hangup')
		},
	},
}
</script>

<style lang="stylus">
.c-janusvideoroom
	background: #111317
	color: #f6f7f9
	display: flex
	flex: auto 1 1
	flex-direction: column
	height: 100%
	min-height: 0
	position: relative

	.connection-state
		align-items: center
		display: flex
		flex: auto 1 1
		justify-content: center
		padding: 24px
		.state-inner
			align-items: center
			color: #b8bec8
			display: flex
			flex-direction: column
			gap: 12px
			text-align: center
		.state-icon
			font-size: 48px
		.state-icon--error
			color: #ff6b62
		.error-detail
			color: #c8ced8
			font-size: 13px
			max-width: 360px
		.retry-btn
			margin-top: 8px

	.room-surface
		display: flex
		flex: auto 1 1
		flex-direction: column
		min-height: 0
	.audio-sinks
		height: 1px
		left: -9999px
		overflow: hidden
		position: fixed
		top: -9999px
		width: 1px

	.gallery
		align-content: center
		align-items: center
		display: grid
		flex: auto 1 1
		gap: 12px
		grid-template-columns: repeat(var(--tile-columns, 1), var(--tile-width, minmax(0, 1fr)))
		grid-template-rows: repeat(var(--tile-rows, 1), var(--tile-height, minmax(0, 1fr)))
		justify-content: center
		min-height: 0
		overflow: hidden
		padding: 16px
		position: relative
		transition: grid-template-columns .2s ease, grid-template-rows .2s ease
		&.has-screen
			align-content: stretch
			align-items: stretch
			grid-template-columns: minmax(0, 1fr) minmax(240px, 320px)
			grid-template-rows: repeat(var(--tile-rows), minmax(0, 1fr))
			.video-tile
				grid-column: 2
			.video-tile.is-focus
				grid-column: 1
				grid-row: 1 / -1
				align-self: center
				aspect-ratio: 16 / 9

	.video-tile
		background: #1e2229
		border-radius: 10px
		box-shadow: 0 2px 8px rgba(0,0,0,.35)
		height: 100%
		max-height: 100%
		max-width: 100%
		min-height: 0
		min-width: 0
		overflow: hidden
		position: relative
		transition: box-shadow .16s ease
		width: 100%
		&.is-speaking
			box-shadow: 0 0 0 3px #2d8cff, 0 2px 8px rgba(0,0,0,.35)
			.media-frame
				box-shadow: none
		&.is-screen video
			object-fit: contain
		&.is-local:not(.is-screen) video
			transform: rotateY(180deg)

		.media-frame
			background: #1e2229
			border-radius: 10px
			height: 100%
			overflow: hidden
			position: relative
			transition: box-shadow .16s ease
			width: 100%
			video
				background: #111317
				height: 100%
				object-fit: cover
				width: 100%
				&.is-hidden
					opacity: 0
			.remote-audio
				display: none

	.avatar-wrap
		align-items: center
		bottom: 0
		display: flex
		justify-content: center
		left: 0
		position: absolute
		right: 0
		top: 0
		.mdi
			color: #87909f
			font-size: 96px

	.tile-gradient
		background: linear-gradient(180deg, rgba(0,0,0,.42), transparent 32%, transparent 58%, rgba(0,0,0,.68))
		bottom: 0
		left: 0
		pointer-events: none
		position: absolute
		right: 0
		top: 0

	.tile-top
		align-items: center
		display: flex
		gap: 8px
		justify-content: flex-end
		left: 10px
		position: absolute
		right: 10px
		top: 10px

	.audio-meter
		background: rgba(255,255,255,.18)
		border-radius: 99px
		height: 5px
		overflow: hidden
		width: 52px
		&.active
			background: rgba(255,255,255,.28)
		.audio-meter-fill
			background: #31c48d
			height: 100%
			transform-origin: left center
			transition: transform .12s linear
			width: 100%

	.mute-pill
		align-items: center
		background: #d93025
		border-radius: 99px
		display: flex
		height: 28px
		justify-content: center
		width: 28px
		.mdi
			color: white
			font-size: 17px

	.tile-bottom
		align-items: center
		bottom: 10px
		display: flex
		gap: 8px
		justify-content: space-between
		left: 10px
		position: absolute
		right: 10px

	.identity
		align-items: center
		background: rgba(0,0,0,.56)
		border: 0
		border-radius: 6px
		color: #fff
		cursor: pointer
		display: flex
		font-size: 13px
		gap: 7px
		line-height: 28px
		max-width: min(260px, 70%)
		min-width: 0
		padding: 4px 8px
		span
			overflow: hidden
			text-overflow: ellipsis
			white-space: nowrap
	.identity--plain
		cursor: default

	.tile-actions
		display: flex
		gap: 6px
		opacity: 0
		transition: opacity .14s ease
	.video-tile:hover .tile-actions
		opacity: 1

	.tile-action
		align-items: center
		background: rgba(0,0,0,.56)
		border: 0
		border-radius: 6px
		color: #fff
		cursor: pointer
		display: flex
		height: 32px
		justify-content: center
		width: 32px
		.mdi
			font-size: 20px
		&:hover
			background: rgba(255,255,255,.18)

	.info-bar
		align-items: center
		display: flex
		flex-direction: column
		flex: none
		gap: 4px
		min-height: 0

	.info-message
		align-items: center
		color: #c8ced8
		display: flex
		font-size: 13px
		gap: 6px
		justify-content: center
		padding: 5px 16px
		text-align: center
	.error-message
		color: #ff9a91

	.slow-banner
		background: rgba(245, 158, 11, .22)
		border-radius: 0 0 8px 8px
		color: #fcd978
		cursor: pointer
		font-size: 13px
		left: 0
		padding: 9px 16px
		position: absolute
		right: 0
		text-align: center
		top: 0

	.pagination-bar
		align-items: center
		background: #181b20
		border-top: 1px solid #2d333d
		color: #c8ced8
		display: flex
		flex: none
		gap: 12px
		justify-content: center
		min-height: 42px
		padding: 6px 16px
	.pagination-button
		min-width: 44px
		.mdi
			font-size: 22px
	.page-indicator
		font-size: 13px
		line-height: 1
		min-width: 90px
		text-align: center

	.controlbar
		align-items: center
		background: #181b20
		border-top: 1px solid #2d333d
		display: flex
		flex: none
		gap: 10px
		justify-content: center
		padding: 12px 18px

	.control-button
		align-items: center
		background: #2c323c
		border: 0
		border-radius: 50%
		color: #f6f7f9
		cursor: pointer
		display: flex
		height: 48px
		justify-content: center
		transition: background .14s ease, transform .14s ease
		width: 48px
		.mdi
			font-size: 23px
		&:hover
			background: #3a4350
		&:active
			transform: scale(.96)
		&.muted,
		&.disabled
			background: #d93025
		&.active
			background: #1976d2
		&.loading
			opacity: .55
		&.leave
			background: #d93025
			border-radius: 24px
			width: 64px
			&:hover
				background: #b3261e

	&.size-tiny
		.gallery
			gap: 0
			padding: 0
		.video-tile,
		.media-frame
			border-radius: 0
		.tile-top,
		.tile-bottom,
		.controlbar,
		.info-bar
			display: none

	+below('m')
		.gallery
			gap: 8px
			padding: 10px
			&.has-screen
				grid-auto-rows: minmax(120px, auto)
				grid-template-columns: minmax(0, 1fr)
				grid-template-rows: auto
				.video-tile,
				.video-tile.is-focus
					grid-column: 1
					grid-row: auto
		.controlbar
			gap: 8px
			padding: 10px
		.control-button
			height: 44px
			width: 44px
			&.leave
				width: 58px
</style>

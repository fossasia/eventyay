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
		.gallery(ref="container", :style="gridStyle", v-resize-observer="onResize")
			.video-tile(
				v-for="tile in tiles",
				:key="tile.key",
				:class="{ 'is-local': tile.local && !tile.screen, 'is-screen': tile.screen, 'is-speaking': tile.speaking }"
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
						:data-feed-id="tile.id",
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
							button.tile-action(type="button", title="Fullscreen", @click="requestFullscreen('janus_' + tile.key)")
								.mdi.mdi-fullscreen
							button.tile-action(type="button", v-if="tile.local && tile.screen", :title="$t('JanusVideoroom:tool-screenshare:off')", @click="stopScreenShare")
								.mdi.mdi-monitor-off

			.slow-banner(v-if="downstreamSlowLinkCount > 5 && videoOutput", @click="disableIncomingVideo") {{ $t('JanusVideoroom:slow:text') }}

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
const USER_DISPLAY = 'venueless user'
const AUDIO_LEVEL_INTERVAL = 160
const SPEAKING_THRESHOLD = 0.03
const LOG_ENTRIES = []

const log = (source, level, message) => {
	LOG_ENTRIES.push([source, (new Date()).toISOString(), level, JSON.stringify(message)])
	console.log(`[${level}][${source}]`, message)
}

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
		screenShareSessionId: {
			type: [Number, String],
			default: null
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
			publisherHandle: null,
			screenShareHandle: null,
			ourId: null,
			ourPrivateId: null,
			localStream: null,
			screenShareStream: null,
			remoteFeeds: [],
			subscribingFeedIds: [],
			cameraEnabled: localStorage.videoRequested !== 'false',
			publishedWithVideo: false,
			localPublishInProgress: false,
			localPublishQueued: false,
			localPublishTimeout: null,
			localCameraActive: false,
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
		janusScreenShareSessionId() {
			return Number(this.screenShareSessionId || Number(this.sessionId) + 1000000000)
		},
		gridStyle() {
			return {
				'--tile-columns': this.layout.cols,
				'--tile-rows': this.layout.rows,
			}
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
			const localAudioLevel = this.normalizedAudioLevel('local')
			const localTiles = [{
				key: 'local',
				id: 'local',
				local: true,
				screen: false,
				user: this.user,
				label: this.user?.profile?.display_name || 'You',
				hasVideo: this.localCameraActive,
				muted: this.micMuted,
				audioLevel: localAudioLevel,
				speaking: this.activeSpeakerId === 'local'
			}]
			if (this.screenShareStream) {
				localTiles.push({
					key: 'local-screen',
					id: 'local-screen',
					local: true,
					screen: true,
					user: this.user,
					label: 'Your screen',
					hasVideo: true,
					muted: true,
					audioLevel: 0,
					speaking: false
				})
			}
			const remoteTiles = this.remoteFeeds
				.slice()
				.sort((a, b) => {
					if (a.isScreenShare !== b.isScreenShare) return a.isScreenShare ? -1 : 1
					return this.feedLabel(a).localeCompare(this.feedLabel(b))
				})
				.map(feed => {
					const id = this.normalizeFeedId(feed.id)
					const level = this.normalizedAudioLevel(id)
					return {
						key: `remote-${id}`,
						id,
						local: false,
						screen: feed.isScreenShare,
						user: feed.user,
						label: this.feedLabel(feed),
						hasVideo: feed.hasVideo,
						muted: feed.muted,
						audioLevel: level,
						speaking: this.activeSpeakerId === id
					}
				})
			return localTiles.concat(remoteTiles)
		},
	},
	watch: {
		tiles() {
			this.$nextTick(this.onResize)
		}
	},
	mounted() {
		LOG_ENTRIES.splice(0, LOG_ENTRIES.length)
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
			if (this.localPublishTimeout) {
				window.clearTimeout(this.localPublishTimeout)
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
			this.janus.attach({
				plugin: 'janus.plugin.videoroom',
				opaqueId: String(this.user.id),
				success: (pluginHandle) => {
					this.publisherHandle = pluginHandle
					log('venueless', 'info', `Publisher handle attached (${pluginHandle.getId()})`)
					this.publisherHandle.send({
						message: {
							request: 'join',
							room: this.janusRoomId,
							id: this.janusSessionId,
							ptype: 'publisher',
							token: this.token,
							display: USER_DISPLAY,
						}
					})
				},
				error: this.failConnection,
				iceState: (state) => {
					log('venueless', 'info', `Publisher ICE state: ${state}`)
					if (state === 'failed') {
						this.failConnection(`ICE connection ${state}`)
					}
				},
				mediaState: (medium, on) => {
					log('venueless', 'info', `Janus ${on ? 'started' : 'stopped'} receiving local ${medium}`)
					if (on && medium === 'audio') {
						this.publishingState = 'published'
						this.publishingError = null
					}
					if (on && medium === 'video' && this.publishedWithVideo) {
						this.publishingState = 'published'
						this.publishingError = null
					}
				},
				webrtcState: (on) => {
					log('venueless', 'info', `Publisher WebRTC is ${on ? 'up' : 'down'}`)
				},
				onmessage: this.onPublisherMessage,
				onlocalstream: this.onLocalStream,
				slowLink: (uplink) => {
					if (uplink) this.handlePublisherSlowLink()
				},
				oncleanup: () => {
					log('venueless', 'info', 'Publisher cleanup received')
					this.publishingState = 'unpublished'
				},
			})
		},
		onPublisherMessage(msg, jsep) {
			const event = msg.videoroom
			if (event === 'joined') {
				this.ourId = msg.id
				this.ourPrivateId = msg.private_id
				this.connectionState = 'connected'
				this.connectionError = null
				this.retryInterval = 1000
				this.publishLocalMedia()
				this.subscribeToPublishers(msg.publishers || [])
			} else if (event === 'destroyed') {
				this.failConnection('Room destroyed', false)
			} else if (event === 'event') {
				if (msg.publishers) this.subscribeToPublishers(msg.publishers)
				if (msg.leaving) this.removeRemoteFeed(msg.leaving)
				if (msg.unpublished) {
					if (msg.unpublished === 'ok') {
						this.publishingState = 'unpublished'
						this.stopLocalCameraTracks()
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
			if (jsep) {
				this.publisherHandle.handleRemoteJsep({jsep})
				this.finishLocalPublish()
				if (this.publishedWithVideo && !msg.video_codec) {
					this.cameraEnabled = false
					this.publishedWithVideo = false
					this.stopLocalCameraTracks()
					this.publishingError = 'The server rejected the selected camera stream.'
				}
			} else if (event === 'event' && msg.configured === 'ok') {
				this.finishLocalPublish()
			}
		},
		async publishLocalMedia() {
			if (!this.publisherHandle) return
			if (this.localPublishInProgress) {
				this.localPublishQueued = true
				return
			}
			this.localPublishInProgress = true
			this.publishingState = 'publishing'
			this.publishingError = null

			const nextVideoInput = localStorage.videoInput || ''
			const nextAudioInput = localStorage.audioInput || ''
			const wantsVideo = this.cameraEnabled
			let hadPeerConnection = Boolean(this.publisherHandle.webrtcStuff?.pc)
			const wasPublishingVideo = this.publishedWithVideo
			if (wantsVideo && hadPeerConnection && !wasPublishingVideo) {
				this.publisherHandle.hangup()
				this.localStream = null
				hadPeerConnection = false
			}
			const media = {
				audioRecv: false,
				videoRecv: false,
				audioSend: true,
				videoSend: wantsVideo,
			}

			media.audio = this.microphoneConstraints(nextAudioInput)
			if (hadPeerConnection && nextAudioInput !== this.audioInput) {
				media.replaceAudio = true
			}

			if (wantsVideo) {
				media.video = this.cameraConstraints(nextVideoInput)
				if (hadPeerConnection && !wasPublishingVideo) {
					media.addVideo = true
				} else if (hadPeerConnection && wasPublishingVideo && nextVideoInput !== this.videoInput) {
					media.replaceVideo = true
				}
			} else if (hadPeerConnection && wasPublishingVideo) {
				media.removeVideo = true
			}

			this.audioInput = nextAudioInput
			this.videoInput = nextVideoInput
			if (!wantsVideo) {
				this.localCameraActive = false
			}

			let explicitStream
			if (!hadPeerConnection) {
				try {
					explicitStream = await navigator.mediaDevices.getUserMedia({
						audio: media.audio,
						video: wantsVideo ? media.video : false,
					})
				} catch (error) {
					this.finishLocalPublish()
					if (wantsVideo) {
						this.cameraEnabled = false
						this.publishedWithVideo = false
						this.localCameraActive = false
						localStorage.videoRequested = false
						this.publishLocalMedia()
						return
					}
					this.publishingState = 'failed'
					this.publishingError = error?.message || 'Could not publish microphone.'
					return
				}
			}

			const offerOptions = {
				media,
				simulcast: false,
				simulcast2: false,
				success: (jsep) => {
					this.publisherHandle.send({
						message: {
							request: 'configure',
							audio: true,
							video: wantsVideo,
							bitrate: this.upstreamBitrate,
						},
						jsep,
						success: () => {
							this.publishedWithVideo = wantsVideo
							this.localPublishTimeout = window.setTimeout(() => this.finishLocalPublish(), 4000)
						},
						error: (error) => {
							this.finishLocalPublish()
							this.publishingState = 'failed'
							this.publishingError = error?.message || error || 'Could not configure local media.'
						},
					})
					if (!wantsVideo) {
						this.stopLocalCameraTracks()
					}
				},
				error: (error) => {
					log('venueless', 'error', `Could not publish local media: ${error}`)
					this.finishLocalPublish()
					if (wantsVideo) {
						this.cameraEnabled = false
						this.publishedWithVideo = false
						this.localCameraActive = false
						localStorage.videoRequested = false
						this.publishLocalMedia()
						return
					}
					this.publishingState = 'failed'
					this.publishingError = error?.message || 'Could not publish microphone.'
				},
			}
			if (explicitStream) {
				offerOptions.stream = explicitStream
			}
			this.publisherHandle.createOffer(offerOptions)
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
		finishLocalPublish() {
			if (this.localPublishTimeout) {
				window.clearTimeout(this.localPublishTimeout)
				this.localPublishTimeout = null
			}
			this.localPublishInProgress = false
			if (this.localPublishQueued) {
				this.localPublishQueued = false
				this.$nextTick(this.publishLocalMedia)
			}
		},
		onLocalStream(stream) {
			this.localStream = stream
			this.localCameraActive = this.cameraEnabled && stream.getVideoTracks().some(track => track.readyState === 'live')
			this.registerAudioMeter('local', stream)
			if (this.automute && !this.automuteApplied) {
				this.micMuted = true
				this.automuteApplied = true
			}
			this.applyMicState()
			this.attachLocalVideo(stream)
			if (!this.publishedWithVideo || stream.getVideoTracks().length > 0) {
				this.publishingState = 'published'
				this.publishingError = null
			}
		},
		applyMicState() {
			if (!this.publisherHandle) return
			if (this.micMuted && !this.publisherHandle.isAudioMuted()) {
				this.publisherHandle.muteAudio()
			} else if (!this.micMuted && this.publisherHandle.isAudioMuted()) {
				this.publisherHandle.unmuteAudio()
			}
		},
		attachLocalVideo(stream) {
			this.$nextTick(() => {
				const video = this.singleRef(this.$refs.localVideo)
				if (!video) return
				Janus.attachMediaStream(video, stream)
				video.muted = true
				const playPromise = video.play()
				if (playPromise?.catch) {
					playPromise.catch(error => {
						log('venueless', 'warn', `Local video playback did not start automatically: ${error}`)
					})
				}
			})
		},
		toggleMic() {
			if (!this.publisherHandle) return
			this.micMuted = !this.micMuted
			this.applyMicState()
		},
		toggleCamera() {
			this.cameraEnabled = !this.cameraEnabled
			localStorage.videoRequested = this.cameraEnabled
			this.publishLocalMedia()
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
		startScreenShare() {
			this.screenShareError = null
			this.screenShareState = 'publishing'
			if (this.screenShareHandle) {
				this.publishScreenShare()
				return
			}
			this.janus.attach({
				plugin: 'janus.plugin.videoroom',
				opaqueId: `${this.user.id}-screen`,
				success: (pluginHandle) => {
					this.screenShareHandle = pluginHandle
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
				error: this.failScreenShare,
				mediaState: (medium, on) => {
					if (medium === 'video' && on) {
						this.screenShareState = 'published'
						this.screenShareError = null
					}
				},
				webrtcState: (on) => {
					log('venueless', 'info', `Screen share WebRTC is ${on ? 'up' : 'down'}`)
				},
				onmessage: this.onScreenShareMessage,
				oncleanup: () => {
					this.resetScreenShare()
				},
			})
		},
		onScreenShareMessage(msg, jsep) {
			const event = msg.videoroom
			if (event === 'joined') {
				this.publishScreenShare()
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
		async publishScreenShare() {
			this.screenShareState = 'publishing'
			this.stopScreenShareTracks()
			let stream
			try {
				stream = await this.getDisplayMedia()
			} catch (error) {
				this.failScreenShare(error, ['AbortError', 'NotAllowedError'].includes(error?.name))
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
					this.screenShareHandle.send({
						message: {
							request: 'configure',
							audio: hasAudio,
							video: true,
							bitrate: MAX_BITRATE,
						},
						jsep,
						error: this.failScreenShare,
					})
				},
				error: this.failScreenShare,
			})
		},
		async getDisplayMedia() {
			if (!navigator.mediaDevices?.getDisplayMedia) {
				throw new Error('Screen sharing is not supported by this browser.')
			}
			const constraints = {
				video: {
					frameRate: {ideal: 15, max: 30},
					width: {max: 1920},
					height: {max: 1080},
				},
				audio: {
					echoCancellation: true,
					noiseSuppression: true,
					autoGainControl: true,
				},
			}
			let stream
			try {
				stream = await navigator.mediaDevices.getDisplayMedia(constraints)
			} catch (error) {
				if (!['TypeError', 'OverconstrainedError', 'ConstraintNotSatisfiedError'].includes(error?.name)) {
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
			this.screenShareState = 'unpublishing'
			this.stopScreenShareTracks()
			if (!this.screenShareHandle) {
				this.resetScreenShare()
				return
			}
			this.screenShareHandle.send({message: {request: 'unpublish'}})
		},
		stopScreenShareTracks() {
			if (!this.screenShareStream) return
			for (const track of this.screenShareStream.getTracks()) {
				track.onended = null
				track.stop()
			}
			this.screenShareStream = null
		},
		resetScreenShare() {
			this.stopScreenShareTracks()
			this.screenShareState = 'unpublished'
		},
		failScreenShare(error, silent = false) {
			log('venueless', 'error', `Screen share failed: ${error}`)
			this.stopScreenShareTracks()
			this.screenShareState = 'failed'
			this.screenShareError = silent ? null : (error?.message || error || 'Screen sharing failed.')
			if (silent) {
				this.screenShareState = 'unpublished'
			}
		},
		subscribeToPublishers(publishers) {
			for (const publisher of publishers) {
				this.subscribeToFeed(publisher.id, publisher.display, publisher.audio_codec, publisher.video_codec)
			}
		},
		subscribeToFeed(feedId, display, audioCodec, videoCodec) {
			const id = this.normalizeFeedId(feedId)
			const isScreenShare = this.isScreenShareFeed(feedId, display)
			if (this.isOwnFeed(feedId) || (!this.videoOutput && !isScreenShare)) {
				return
			}
			const existingFeed = this.remoteFeeds.find(feed => this.feedIdEquals(feed.id, id))
			if (existingFeed) {
				existingFeed.display = display
				existingFeed.audioCodec = audioCodec
				existingFeed.videoCodec = videoCodec
				existingFeed.isScreenShare = isScreenShare
				if (!isScreenShare && videoCodec && !existingFeed.hasVideo && this.videoOutput) {
					this.removeRemoteFeed(id)
				} else {
					if (!isScreenShare && !videoCodec) {
						existingFeed.hasVideo = false
					}
					this.upsertRemoteFeed(existingFeed)
					return
				}
			} else if (this.subscribingFeedIds.some(subscribingId => this.feedIdEquals(subscribingId, id))) {
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
						feed: feedId,
						private_id: this.ourPrivateId,
						offer_audio: true,
						offer_video: this.videoOutput || isScreenShare,
					}
					if (Janus.webRTCAdapter.browserDetails.browser === 'safari' &&
						(videoCodec === 'vp9' || (videoCodec === 'vp8' && !Janus.safariVp8))) {
						subscribe.offer_video = false
					}
					remoteHandle.send({message: subscribe})
				},
				error: (error) => {
					this.unmarkSubscribing(feedId)
					log('venueless', 'error', `Could not attach subscriber for ${feedId}: ${error}`)
				},
				onmessage: (msg, jsep) => {
					this.onSubscriberMessage(remoteHandle, feedId, display, isScreenShare, audioCodec, videoCodec, msg, jsep)
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
					this.removeRemoteFeed(feedId, false)
				},
			})
		},
		onSubscriberMessage(handle, feedId, display, isScreenShare, audioCodec, videoCodec, msg, jsep) {
			const event = msg.videoroom
			if (msg.error) {
				this.unmarkSubscribing(feedId)
				log('venueless', 'error', `Subscriber ${feedId} error: ${msg.error}`)
				return
			}
			if (event === 'attached') {
				const id = this.normalizeFeedId(msg.id || feedId)
				this.unmarkSubscribing(id)
				this.upsertRemoteFeed({
					id,
					handle,
					display,
					isScreenShare,
					audioCodec,
					videoCodec,
					attached: false,
					hasVideo: isScreenShare,
					muted: false,
					user: null,
					stream: null,
				})
				this.fetchFeedUser(id)
			}
			if (jsep) {
				handle.createAnswer({
					jsep,
					media: {
						audioSend: false,
						videoSend: false,
					},
					success: (answer) => {
						handle.send({message: {request: 'start', room: this.janusRoomId}, jsep: answer})
						this.syncRemoteTracksFromPeerConnection(handle, feedId)
						window.setTimeout(() => this.syncRemoteTracksFromPeerConnection(handle, feedId), 500)
					},
					error: (error) => {
						this.removeRemoteFeed(feedId)
						log('venueless', 'error', `Could not answer subscriber ${feedId}: ${error}`)
					},
				})
			}
		},
		onRemoteTrack(feedId, track, on) {
			if (!track) return
			const id = this.normalizeFeedId(feedId)
			const feed = this.remoteFeeds.find(item => this.feedIdEquals(item.id, id))
			if (!feed) return
			if (!feed.stream) {
				feed.stream = new MediaStream()
			}
			if (on) {
				if (!feed.stream.getTracks().some(existingTrack => existingTrack.id === track.id)) {
					feed.stream.addTrack(track)
				}
			} else {
				for (const existingTrack of feed.stream.getTracks().filter(item => item.id === track.id)) {
					feed.stream.removeTrack(existingTrack)
				}
			}
			this.applyRemoteStream(feed, feed.stream)
		},
		onRemoteStream(feedId, stream) {
			const id = this.normalizeFeedId(feedId)
			const feed = this.remoteFeeds.find(item => this.feedIdEquals(item.id, id))
			if (!feed) return
			this.applyRemoteStream(feed, stream)
		},
		syncRemoteTracksFromPeerConnection(handle, feedId) {
			const id = this.normalizeFeedId(feedId)
			const feed = this.remoteFeeds.find(item => this.feedIdEquals(item.id, id))
			const pc = handle?.webrtcStuff?.pc
			if (!feed || !pc?.getReceivers) return
			const tracks = pc.getReceivers()
				.map(receiver => receiver.track)
				.filter(track => track && track.readyState !== 'ended')
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
			feed.hasVideo = stream.getVideoTracks().length > 0 && (feed.isScreenShare || !!feed.videoCodec)
			feed.muted = stream.getAudioTracks().every(track => !track.enabled)
			this.registerAudioMeter(id, stream)
			this.upsertRemoteFeed(feed)
			this.$nextTick(() => {
				const video = this.findRemoteVideo(feed.id)
				if (!video) return
				if (video.srcObject !== stream) {
					Janus.attachMediaStream(video, stream)
				}
				if (localStorage.audioOutput && video.setSinkId) {
					video.setSinkId(localStorage.audioOutput)
				}
				if (!video.paused && video.readyState > 0) return
				const playPromise = video.play()
				if (playPromise?.catch) {
					playPromise.catch(error => {
						log('venueless', 'warn', `Remote video playback did not start automatically for ${id}: ${error}`)
					})
				}
			})
		},
		findRemoteVideo(feedId) {
			return Array.from(this.$el.querySelectorAll('video[data-feed-id]'))
				.find(video => this.feedIdEquals(video.dataset.feedId, feedId))
		},
		upsertRemoteFeed(feed) {
			const index = this.remoteFeeds.findIndex(item => this.feedIdEquals(item.id, feed.id))
			if (index === -1) {
				this.remoteFeeds.push(feed)
			} else {
				this.remoteFeeds.splice(index, 1, feed)
			}
		},
		removeRemoteFeed(feedId, detach = true) {
			const id = this.normalizeFeedId(feedId)
			this.unmarkSubscribing(id)
			const feed = this.remoteFeeds.find(item => this.feedIdEquals(item.id, id))
			if (feed?.handle && detach) {
				feed.handle.detach()
			}
			this.closeAudioMeter(id)
			this.remoteFeeds = this.remoteFeeds.filter(item => !this.feedIdEquals(item.id, id))
		},
		async fetchFeedUser(feedId) {
			try {
				const user = await api.call('januscall.identify', {id: feedId})
				const feed = this.remoteFeeds.find(item => this.feedIdEquals(item.id, feedId))
				if (feed) {
					feed.user = user
					this.upsertRemoteFeed(feed)
				}
			} catch (error) {
				log('venueless', 'warn', `Could not identify Janus feed ${feedId}: ${error}`)
			}
		},
		closeDevicePrompt() {
			this.showDevicePrompt = false
			const outputChanged = this.videoOutput !== (localStorage.videoOutput !== 'false')
			const nextAudioInput = localStorage.audioInput || ''
			const nextVideoInput = localStorage.videoInput || ''
			const devicesChanged = nextAudioInput !== this.audioInput || nextVideoInput !== this.videoInput
			this.videoOutput = localStorage.videoOutput !== 'false'
			if (outputChanged) {
				this.cleanup()
				this.onJanusInitialized()
				return
			}
			if (devicesChanged) {
				this.publishLocalMedia()
			}
			this.updateAudioOutputs()
		},
		updateAudioOutputs() {
			for (const video of this.$el.querySelectorAll('video[data-feed-id]')) {
				if (localStorage.audioOutput && video.setSinkId) {
					video.setSinkId(localStorage.audioOutput)
				}
			}
		},
		disableIncomingVideo() {
			this.videoOutput = false
			localStorage.videoOutput = false
			for (const feed of this.remoteFeeds.slice()) {
				if (!feed.isScreenShare) {
					this.removeRemoteFeed(feed.id)
				}
			}
		},
		handlePublisherSlowLink() {
			this.upstreamSlowLinkCount++
			if (this.upstreamSlowLinkCount <= 2) return
			const bitrate = Math.max(this.upstreamBitrate / 2, MIN_BITRATE)
			if (bitrate !== this.upstreamBitrate) {
				this.upstreamBitrate = bitrate
				this.publisherHandle.send({
					message: {
						request: 'configure',
						audio: true,
						video: this.publishedWithVideo,
						bitrate: this.upstreamBitrate,
					}
				})
				this.upstreamSlowLinkCount = 0
			} else if (this.upstreamSlowLinkCount > 5 && this.cameraEnabled) {
				this.cameraEnabled = false
				localStorage.videoRequested = false
				this.publishLocalMedia()
			}
		},
		registerAudioMeter(id, stream) {
			if (!stream.getAudioTracks().length) return
			this.closeAudioMeter(id)
			try {
				window.AudioContext = window.AudioContext || window.webkitAudioContext
				const context = new AudioContext()
				const meter = new SoundMeter(context)
				meter.connectToSource(stream)
				this.audioMeters[id] = meter
			} catch (error) {
				log('venueless', 'warn', `Could not create audio meter for ${id}: ${error}`)
			}
		},
		closeAudioMeter(id) {
			const meter = this.audioMeters[id]
			if (!meter) return
			if (meter.context?.state !== 'closed') {
				meter.context.close()
			}
			delete this.audioMeters[id]
			delete this.audioLevels[id]
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
		isScreenShareFeed(feedId, display) {
			return display === SCREEN_SHARE_DISPLAY || this.feedIdEquals(feedId, this.janusScreenShareSessionId)
		},
		isOwnFeed(feedId) {
			return this.feedIdEquals(feedId, this.ourId) || this.feedIdEquals(feedId, this.janusScreenShareSessionId)
		},
		isSubscribedOrSubscribing(feedId) {
			return this.remoteFeeds.some(feed => this.feedIdEquals(feed.id, feedId)) ||
				this.subscribingFeedIds.some(id => this.feedIdEquals(id, feedId))
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
			if (feed.isScreenShare) {
				return feed.user?.profile?.display_name ? `${feed.user.profile.display_name}'s screen` : 'Shared screen'
			}
			return feed.user?.profile?.display_name || 'Participant'
		},
		stopLocalCameraTracks() {
			this.localCameraActive = false
			if (!this.localStream) return
			for (const track of this.localStream.getVideoTracks()) {
				track.stop()
			}
			const localVideo = this.singleRef(this.$refs.localVideo)
			if (localVideo) {
				localVideo.srcObject = null
			}
			if (!this.localStream.getAudioTracks().length) {
				this.localStream = null
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
		requestFullscreen(id) {
			const element = document.getElementById(id)
			if (element?.requestFullscreen) {
				element.requestFullscreen()
			}
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
			this.suppressDestroyedState = preserveConnectionFailure
			this.stopScreenShareTracks()
			if (this.localStream) {
				this.stopStreamTracks(this.localStream)
			}
			for (const id of Object.keys(this.audioMeters)) {
				this.closeAudioMeter(id)
			}
			this.remoteFeeds = []
			this.subscribingFeedIds = []
			this.localStream = null
			this.screenShareStream = null
			this.publisherHandle = null
			this.screenShareHandle = null
			this.localPublishInProgress = false
			this.localPublishQueued = false
			this.automuteApplied = false
			if (this.localPublishTimeout) {
				window.clearTimeout(this.localPublishTimeout)
				this.localPublishTimeout = null
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
		},
		failConnection(error, retry = true) {
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

	.gallery
		align-content: center
		align-items: center
		display: grid
		flex: auto 1 1
		gap: 12px
		grid-template-columns: repeat(var(--tile-columns), minmax(0, 1fr))
		grid-template-rows: repeat(var(--tile-rows), minmax(0, 1fr))
		justify-content: center
		min-height: 0
		overflow: hidden
		padding: 16px
		position: relative

	.video-tile
		background: #252a32
		border-radius: 8px
		height: 100%
		max-height: 100%
		max-width: 100%
		min-height: 0
		min-width: 0
		overflow: hidden
		position: relative
		width: 100%
		&.is-speaking .media-frame
			box-shadow: 0 0 0 3px #2d8cff
		&.is-screen video
			object-fit: contain
		&.is-local:not(.is-screen) video
			transform: rotateY(180deg)

	.media-frame
		background: #252a32
		border-radius: 8px
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
		.controlbar
			gap: 8px
			padding: 10px
		.control-button
			height: 44px
			width: 44px
			&.leave
				width: 58px
</style>

<template lang="pug">
.c-janusconference

	.connection-state(v-if="connectionState != 'connected'")
		div(v-if="connectionState == 'disconnected'") {{ $t('JanusVideoroom:disconnected:text') }}
		div.connection-error(v-else-if="connectionState == 'failed'")
			p {{ $t('JanusVideoroom:connection-error:text') }}
			p {{ connectionError }}
		bunt-progress-circular(v-else-if="connectionState == 'connecting'", size="huge", :page="true")

	audio(v-show="false", ref="mixedAudio", autoplay, playsinline)

	.participants(v-show="connectionState === 'connected'")
		.participant.me(:class="{talking: !knownMuteState && talkingParticipants.includes(ourAudioId)}", @click="showUserCard($event, user)")
			avatar(:user="user", :size="36")
			.mute-indicator(v-if="knownMuteState")
				.bunt-icon.mdi.mdi-microphone-off
		.participant(v-for="p in sortedParticipants", @click="showUserCard($event, p.venueless_user)", :class="{talking: !p.muted && talkingParticipants.includes(p.id)}")
			avatar(v-if="p.venueless_user", :user="p.venueless_user", :size="36")
			.mute-indicator(v-if="p.muted")
				.bunt-icon.mdi.mdi-microphone-off

	.users(v-show="connectionState === 'connected'", ref="container", :style="gridStyle", v-resize-observer="onResize")
		.feed(v-for="t in tiles", :key="t.id", :class="{ me: t.isMe, 'screenshare-feed': t.isScreenshare }")
			.video-container(:class="{ speaking: t.speaking && size !== 'tiny' }", :id="'janus_' + t.id")
				video(v-if="t.isMe && !t.isScreenshare", v-show="t.hasVideo", ref="ourVideo", autoplay, playsinline, muted)
				video(v-else-if="t.isMe && t.isScreenshare", ref="ourScreenshareVideo", autoplay, playsinline, muted)
				video(v-else, v-show="t.hasVideo", :data-rfid="t.rfid", autoplay, playsinline)

				.novideo-indicator(v-if="!t.hasVideo && !t.isScreenshare")
					avatar(:user="t.user", :size="size === 'tiny' ? 40 : 100")

				.video-overlay
					.badge-row
						span.badge.badge--me(v-if="t.isMe && size !== 'tiny' && !t.isScreenshare") You
						span.badge.badge--screensharing(v-if="t.isScreenshare && t.isMe") 🖥 Your Screen
						span.badge.badge--screensharing(v-if="t.isScreenshare && !t.isMe") 🖥 Screen
						span.badge.badge--screensharing(v-if="!t.isScreenshare && t.isMe && screensharingState === 'published'") 🖥 Sharing

			.controls
				.user(v-if="t.user", @click="showUserCard($event, t.user)")
					avatar(:user="t.user", :size="36")
					span.display-name {{ t.user.profile.display_name }}
				bunt-icon-button(v-if="t.hasVideo", @click="requestFullscreen('#janus_' + t.id)") fullscreen
				bunt-icon-button(v-if="t.isMe && t.isScreenshare", @click="unpublishOwnScreenshareFeed") monitor-off

			.mute-indicator(v-if="t.muted")
				.bunt-icon.mdi.mdi-microphone-off

		.slow-banner(v-if="downstreamSlowLinkCount > 5 && (videoRequested || videoOutput)", @click="disableAllVideo") {{ $t('JanusConference:slow:text') }}

	.info-bar
		.info-message(v-if="!videoOutput") {{ $t('JanusVideoroom:video-output:off') }}
		.info-message.screensharing-error(v-if="screensharingError")
			.mdi.mdi-alert
			span {{ screensharingError }}

	.controlbar(v-show="connectionState == 'connected'", :class="{ always: knownMuteState }")
		.ctrl-btn(:class="{ 'ctrl-btn--active': videoRequested }", :title="videoRequested ? $t('JanusVideoroom:tool-video:off') : $t('JanusVideoroom:tool-video:on')", @click="toggleVideo")
			.mdi(:class="videoRequested ? 'mdi-video' : 'mdi-video-off'")
		.ctrl-btn(:class="{ 'ctrl-btn--muted': knownMuteState }", :title="knownMuteState ? $t('JanusVideoroom:tool-mute:off') : $t('JanusVideoroom:tool-mute:on')", @click="toggleMute")
			.mdi(:class="knownMuteState ? 'mdi-microphone-off' : 'mdi-microphone'")
		.ctrl-btn(:class="{ 'ctrl-btn--active': screensharingState === 'published', 'ctrl-btn--disabled': screensharingState === 'publishing' || screensharingState === 'unpublishing' }", :title="screensharingState === 'published' ? $t('JanusVideoroom:tool-screenshare:off') : $t('JanusVideoroom:tool-screenshare:on')", @click="toggleScreenShare")
			.mdi(:class="screensharingState === 'published' ? 'mdi-monitor-off' : 'mdi-monitor'")
		.ctrl-btn(title="Settings", @click="showDevicePrompt = true")
			.mdi.mdi-cog
		.ctrl-btn(title="Report issue", @click="showFeedbackPrompt = true")
			.mdi.mdi-message-alert-outline
		.ctrl-btn.ctrl-btn--hangup(:title="$t('JanusVideoroom:tool-hangup:tooltip')", @click="cleanup(); $emit('hangup')")
			.mdi.mdi-phone-hangup

	chat-user-card(v-if="selectedUser", ref="avatarCard", :user="selectedUser", @close="selectedUser = null")
	transition(name="prompt")
		template
			a-v-device-prompt(v-if="showDevicePrompt", @close="closeDevicePrompt")
			feedback-prompt(v-if="showFeedbackPrompt", module="janus", :collectTrace="collectTrace", @close="showFeedbackPrompt = false")
			prompt.screenshare-prompt(v-if="showScreensharePrompt", @close="showScreensharePrompt=false")
				.content
					h1 {{ $t('JanusVideoroom:tool-screenshare:on') }}
					form(@submit.prevent="publishOwnScreenshareFeed")
						bunt-button(type="submit") {{ $t('JanusVideoroom:tool-screenshare:start') }}
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
import Prompt from 'components/Prompt'
import {createPopper} from '@popperjs/core'
import Color from 'color'
import {colors} from 'theme'

const calculateLayout = (containerWidth, containerHeight, videoCount, aspectRatio, videoPadding) => {
	let bestLayout = {
		area: 0,
		cols: 0,
		rows: 0,
		width: 0,
		height: 0
	}

	// brute-force search layout where video occupy the largest area of the container
	for (let cols = 1; cols <= videoCount; cols++) {
		const rows = Math.ceil(videoCount / cols)
		const hScale = (containerWidth - cols * 2 * videoPadding) / (cols * aspectRatio)
		const vScale = (containerHeight - cols * 2 * videoPadding) / rows
		let width
		let height
		if (hScale <= vScale) {
			width = Math.floor((containerWidth - cols * 2 * videoPadding) / cols)
			height = Math.floor(width / aspectRatio)
		} else {
			height = Math.floor((containerHeight - cols * 2 * videoPadding) / rows)
			width = Math.floor(height * aspectRatio)
		}
		const area = width * height
		if (area > bestLayout.area) {
			bestLayout = {
				area,
				width,
				height,
				rows,
				cols
			}
		}
	}
	return bestLayout
}

const MIN_BITRATE = 150 * 1000
const MAX_BITRATE = 1500 * 1000

const LOG_ENTRIES = []

const log = (source, level, message) => {
	LOG_ENTRIES.push([source, (new Date()).toISOString(), level, JSON.stringify(message)])
	console.log(`[${level}][${source}]`, message)
}

export default {
	components: {Avatar, AVDevicePrompt, ChatUserCard, FeedbackPrompt, Prompt},
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
			type: String, // 'normal', 'tiny'
			default: 'normal'
		},
	},
	emits: ['hangup'],
	data() {
		return {
			// State machines
			connectionState: 'disconnected', // disconnected, connecting, connected, failed
			audioReceivingState: 'pending', // pending, receiving
			videoReceivingState: 'pending', // pending, receiving, failed
			audioPublishingState: 'unpublished', // unpublished, publishing, published, failed
			videoPublishingState: 'unpublished', // unpublished, publishing, published, failed
			screensharingState: 'unpublished', // unpublished, publishing, published, unpublishing, failed

			// Error handling
			retryInterval: 1000,
			connectionError: null,
			connectionRetryTimeout: null,
			suppressDestroyedState: false,
			publishingError: null,
			screensharingError: null,

			// References to Janus.js
			janus: null,
			audioPluginHandle: null,
			videoPluginHandle: null,
			screensharePluginHandle: null,

			// Video controls state
			videoRequested: false,

			// Janus audiobridge state
			audioInput: null, // audio input currently requested from janus
			audioReceived: true, // janus *has* received our audio
			ourAudioId: null,
			participants: [],
			talkingParticipants: [],
			knownMuteState: this.automute,

			// Janus video call state
			videoPublishers: [],
			feeds: [],
			subscribingFeedIds: [],
			ourId: null,
			ourPrivateId: null,
			ourStream: null,
			ourScreenShareStream: null,
			showOwnScreenShare: false,
			publishingWithVideo: false, // we are *trying* to send video
			videoReceived: false, // janus *has* received our video
			videoInput: null, // video input currently requested from janus
			videoOutput: localStorage.videoOutput !== 'false',
			waitingForConsent: false,

			// Bandwidth control
			upstreamBitrate: MAX_BITRATE,
			upstreamSlowLinkCount: 0,
			downstreamSlowLinkCount: 0,

			// Layout utilities
			userCache: {},
			primaryColor: Color(colors.primary),
			showScreensharePrompt: false,
			showFeedbackPrompt: false,
			showDevicePrompt: false,
			selectedUser: null,
			layout: {
				area: 0,
				cols: 0,
				rows: 0,
				width: 0,
				height: 0
			},
		}
	},
	computed: {
		...mapState(['user']),

		sortedParticipants() {
			return this.participants.slice().sort((a, b) => a.venueless_user && b.venueless_user ? a.venueless_user.profile.display_name.localeCompare(b.venueless_user.profile.display_name) : 1)
		},
		sortedFeeds() {
			return this.feeds.slice().sort((a, b) => a.venueless_user && b.venueless_user ? a.venueless_user.profile.display_name.localeCompare(b.venueless_user.profile.display_name) : 1)
		},
		tiles() {
			const t = []

			// 1. Our own video/avatar tile
			t.push({
				id: 'me',
				isMe: true,
				isScreenshare: false,
				participant: { id: this.ourAudioId },
				user: this.user,
				hasVideo: this.publishingWithVideo,
				speaking: !this.knownMuteState && this.talkingParticipants.includes(this.ourAudioId),
				muted: this.knownMuteState,
			})

			// 2. Our own screenshare
			if (this.showOwnScreenShare) {
				t.push({
					id: 'me-screenshare',
					isMe: true,
					isScreenshare: true,
					user: this.user,
					hasVideo: true,
				})
			}

			// 3. Peer tiles (from participants)
			for (const p of this.sortedParticipants) {
				const feed = this.feeds.find(f => !f.isScreenshare && this.feedIdEquals(f.rfid, p.id))
				t.push({
					id: `peer-${p.id}`,
					rfid: feed ? feed.rfid : null,
					isMe: false,
					isScreenshare: false,
					participant: p,
					user: p.venueless_user,
					feed: feed,
					hasVideo: !!(feed && feed.rfattached && feed.hasVideo),
					speaking: !p.muted && this.talkingParticipants.includes(p.id),
					muted: p.muted,
				})
			}

			// 4. Peer screenshares
			const peerScreenshares = this.feeds.filter(f => f.isScreenshare)
			for (const f of peerScreenshares) {
				t.push({
					id: `screenshare-${f.rfid}`,
					rfid: f.rfid,
					isMe: false,
					isScreenshare: true,
					user: f.venueless_user,
					feed: f,
					hasVideo: f.rfattached,
					speaking: false,
					muted: false,
				})
			}

			return t
		},
		gridStyle() {
			return {
				'--video-width': `${this.layout.width}px`,
				'--video-height': `${this.layout.height}px`,
			}
		},
		janusRoomId() {
			return Number(this.roomId)
		},
		janusSessionId() {
			return Number(this.sessionId)
		},
		janusScreenShareSessionId() {
			return Number(this.screenShareSessionId || Number(this.sessionId) + 1000000000)
		},
	},
	watch: {
		feeds() {
			this.onResize()
		},
		videoPublishingState() {
			this.onResize()
		}
	},
	unmounted() {
		if (this.janus) {
			this.cleanup()
		}
		if (this.connectionRetryTimeout) {
			window.clearTimeout(this.connectionRetryTimeout)
		}
		if (this.slowLinkInterval) {
			window.clearInterval(this.slowLinkInterval)
		}
	},
	mounted() {
		LOG_ENTRIES.splice(0, LOG_ENTRIES.length)
		if (this.janus) {
			this.cleanup()
		}
		this.initJanus()
		this.slowLinkInterval = window.setInterval(() => {
			this.downstreamSlowLinkCount = Math.max(this.downstreamSlowLinkCount - 1, 0)
			this.upstreamSlowLinkCount = Math.max(this.upstreamSlowLinkCount - 1, 0)
		}, 10000)
	},
	methods: {
		collectTrace() {
			// Yes, passing a function to a component is an antipattern in Vue, but I'm worried about the performance
			// penalty on Vue computing reactivity on our log which might get large.
			return LOG_ENTRIES
		},
		cleanup({preserveConnectionFailure = false} = {}) {
			if (!this.janus) return
			this.suppressDestroyedState = preserveConnectionFailure
			this.janus.destroy({cleanupHandles: true})
			if (!preserveConnectionFailure) this.connectionState = 'disconnected'
			this.audioReceivingState = 'pending'
			this.videoReceivingState = 'pending'
			this.audioPublishingState = 'unpublished'
			this.videoPublishingState = 'unpublished'
			this.screensharingState = 'unpublished'
			if (!preserveConnectionFailure) {
				this.retryInterval = 1000
				this.connectionError = null
			}
			this.screensharingError = null
			this.feeds = []
			this.subscribingFeedIds = []
			this.participants = []
			this.stopOwnVideoTracks()
			this.ourStream = null
			this.stopOwnScreenshareStream()
			this.screensharePluginHandle = null
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
		onResize() {
			const bbox = this.$refs.container.getBoundingClientRect()
			this.layout = calculateLayout(
				this.size === 'tiny' ? bbox.width : bbox.width - 16 * 2,
				this.size === 'tiny' ? bbox.height : bbox.height - 16 * 2,
				this.tiles.length,
				16 / 9,
				this.size === 'tiny' ? 0 : 8,
			)
		},
		requestFullscreen(el) {
			document.querySelector(el).requestFullscreen()
		},
		closeDevicePrompt() {
			this.showDevicePrompt = false
			if (this.videoOutput !== (localStorage.videoOutput !== 'false')) {
				this.videoOutput = (localStorage.videoOutput !== 'false')
				if (this.videoOutput) {
					// Enable receiving video
					for (const f of this.videoPublishers) {
						this.subscribeRemoteVideo(f.id, f.display, f.audio_codec, f.video_codec)
					}
				} else {
					this.disableAllVideo()
				}
			} else {
				this.publishOwnVideo()
			}
			this.publishOwnAudio()
			if (typeof this.$refs.mixedAudio.setSinkId !== 'undefined') {
				this.$refs.mixedAudio.setSinkId(localStorage.audioOutput || '')
			}
		},
		async showUserCard(event, user) {
			this.selectedUser = user
			await this.$nextTick()
			const target = event.target.closest('.user, .participant')
			createPopper(target, this.$refs.avatarCard.$refs.card, {
				placement: 'bottom',
				strategy: 'fixed',
				modifiers: [{
					name: 'flip',
					options: {
						flipVariations: false
					}
				}, {
					name: 'preventOverflow',
					options: {
						padding: 8
					}
				}]
			})
		},
		toggleScreenShare() {
			if (this.screensharingState === 'published') {
				this.unpublishOwnScreenshareFeed()
			} else if (this.screensharingState === 'unpublished' || this.screensharingState === 'failed') {
				if (this.screensharePluginHandle !== null) {
					this.publishOwnScreenshareFeed()
					return
				}
				this.janus.attach(
					{
						plugin: 'janus.plugin.videoroom',
						opaqueId: String(this.user.id),
						success: (pluginHandle) => {
							this.screensharePluginHandle = pluginHandle
							log('venueless', 'info',
								'Plugin attached! (' + this.screensharePluginHandle.getPlugin() + ', id=' + this.videoPluginHandle.getId() + ')')

							const register = {
								request: 'join',
								room: this.janusRoomId,
								id: this.janusScreenShareSessionId,
								ptype: 'publisher',
								token: this.token,
								display: 'venueless screenshare'
							}
							this.screensharePluginHandle.send({message: register})
						},
						error: (error) => {
							log('venueless', 'error', '  -- Error attaching plugin...', error)
							this.failScreenshare(error)
						},
						consentDialog: (on) => {
							this.waitingForConsent = on
						},
						iceState: (state) => {
							log('venueless', 'info', 'ICE state changed to ' + state)
							// if state "failed", show user, unless we're currently leaving the room
						},
						mediaState: (medium, on) => {
							log('venueless', 'info', 'Janus ' + (on ? 'started' : 'stopped') + ' receiving our ' + medium)
							if (medium === 'video' && on) {
								this.screensharingState = 'published'
							}
						},
						webrtcState: (on) => {
							log('venueless', 'info', 'Janus says our WebRTC PeerConnection is ' + (on ? 'up' : 'down') + ' now')
						},
						onmessage: (msg, jsep) => {
							log('venueless', 'debug', ' ::: Got a message (publisher) :::', msg)
							var event = msg.videoroom
							log('venueless', 'debug', 'Event: ' + event)
							if (event) {
								if (event === 'joined') {
									if (Janus.webRTCAdapter.browserDetails.browser === 'safari') {
										// In Safari, screenshare must be directly triggered by a user gesture
										this.showScreensharePrompt = true
									} else {
										this.publishOwnScreenshareFeed()
									}
								} else if (event === 'destroyed') {
									this.screensharingState = 'failed'
									this.screensharingError = 'The room has been destroyed.'
								} else if (event === 'event') {
									if (msg.unpublished) {
									// One of the publishers has unpublished?
										const unpublished = msg.unpublished
										log('venueless', 'info', 'Publisher left: ' + unpublished)
										if (unpublished === 'ok') {
											this.resetScreenshareState()
											this.screensharePluginHandle.hangup()
											return
										}
									} else if (msg.error) {
										this.screensharingState = 'failed'
										if (msg.error_code === 426) {
											this.screensharingError = 'The room does not exist.'
										} else {
											this.screensharingError = msg.error
										}
									}
								}
							}
							if (jsep) {
								log('venueless', 'debug', 'Handling SDP as well...', jsep)
								this.screensharePluginHandle.handleRemoteJsep({jsep: jsep})
								var audio = msg.audio_codec
								if (this.ourScreenShareStream && this.ourScreenShareStream.getAudioTracks() && this.ourScreenShareStream.getAudioTracks().length > 0 &&
									!audio) {
									// Audio has been rejected
									log('venueless', 'warning', 'Our audio stream has been rejected, viewers won\'t hear our screenshare')
								}
								var video = msg.video_codec
								if (this.ourScreenShareStream && this.ourScreenShareStream.getVideoTracks() && this.ourScreenShareStream.getVideoTracks().length > 0 &&
									!video) {
									this.screensharingState = 'failed'
									this.screensharingError = 'Stream rejected.'
								}
							}
						},
						slowLink: (uplink) => {
							log('venueless', 'info', 'slowlink on screenshare')
						},
						oncleanup: () => {
							log('venueless', 'info', ' ::: Got a cleanup notification: we are unpublished now :::')
							this.resetScreenshareState()
						},
					})
			}
		},
		resetScreenshareState() {
			this.stopOwnScreenshareStream()
			this.showScreensharePrompt = false
			this.screensharingState = 'unpublished'
			this.screensharingError = null
		},
		stopOwnScreenshareStream() {
			if (!this.ourScreenShareStream) {
				this.showOwnScreenShare = false
				return
			}
			for (const track of this.ourScreenShareStream.getTracks()) {
				track.onended = null
				track.stop()
			}
			this.ourScreenShareStream = null
			this.showOwnScreenShare = false
		},
		unpublishOwnScreenshareFeed() {
			this.screensharingState = 'unpublishing'
			this.stopOwnScreenshareStream()
			if (!this.screensharePluginHandle) {
				this.resetScreenshareState()
				return
			}
			try {
				this.screensharePluginHandle.send({message: {request: 'unpublish'}})
			} catch (error) {
				log('venueless', 'error', 'Could not unpublish screenshare:', error)
				this.resetScreenshareState()
			}
		},
		failScreenshare(error) {
			log('venueless', 'error', 'Screen sharing failed:', error)
			this.stopOwnScreenshareStream()
			if (error && ['AbortError', 'NotAllowedError'].includes(error.name)) {
				this.screensharingState = 'unpublished'
				this.screensharingError = null
				return
			}
			this.screensharingState = 'failed'
			this.screensharingError = error?.message || error || 'Screen sharing failed.'
		},
		async getScreenshareStream() {
			if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
				throw new Error('Screen sharing is not supported by this browser.')
			}
			const stream = await navigator.mediaDevices.getDisplayMedia({
				video: {
					frameRate: {ideal: 15, max: 30},
					width: {max: 1920},
					height: {max: 1080},
				},
				audio: false,
			})
			if (!stream.getVideoTracks().length) {
				throw new Error('No screen video track was selected.')
			}
			return stream
		},
		toggleVideo() {
			this.videoRequested = !this.videoRequested
			this.publishOwnVideo()
		},
		normalizeFeedId(id) {
			return String(id)
		},
		feedIdEquals(a, b) {
			return this.normalizeFeedId(a) === this.normalizeFeedId(b)
		},
		isScreenshareFeedId(id, display = null) {
			const feedId = this.normalizeFeedId(id)
			return display === 'venueless screenshare' || feedId === this.normalizeFeedId(this.janusScreenShareSessionId) || feedId.includes('_screenshare_')
		},
		isOwnPublishedFeed(id) {
			return this.feedIdEquals(id, this.ourId) || this.feedIdEquals(id, this.janusScreenShareSessionId)
		},
		isSubscribedOrSubscribing(id) {
			return this.feeds.some(rf => this.feedIdEquals(rf.rfid, id)) || this.subscribingFeedIds.some(fid => this.feedIdEquals(fid, id))
		},
		markSubscribing(id) {
			if (!this.subscribingFeedIds.some(fid => this.feedIdEquals(fid, id))) {
				this.subscribingFeedIds.push(this.normalizeFeedId(id))
			}
		},
		unmarkSubscribing(id) {
			this.subscribingFeedIds = this.subscribingFeedIds.filter(fid => !this.feedIdEquals(fid, id))
		},
		removeRemoteFeed(id) {
			this.unmarkSubscribing(id)
			const remoteFeed = this.feeds.find((rf) => this.feedIdEquals(rf.rfid, id))
			if (remoteFeed != null) {
				log('venueless', 'debug', 'Feed ' + remoteFeed.rfid + ' (' + remoteFeed.rfdisplay + ') has left the room, detaching')
				this.feeds = this.feeds.filter((rf) => !this.feedIdEquals(rf.rfid, remoteFeed.rfid))
				remoteFeed.detach()
			}
		},
		stopOwnVideoTracks() {
			if (!this.ourStream) {
				return
			}
			for (const track of this.ourStream.getVideoTracks()) {
				track.onended = null
				track.stop()
			}
			const videoEl = Array.isArray(this.$refs.ourVideo) ? this.$refs.ourVideo[0] : this.$refs.ourVideo
			if (videoEl) {
				videoEl.srcObject = null
			}
		},
		stopStreamTracks(stream) {
			for (const track of stream.getTracks()) {
				track.onended = null
				track.stop()
			}
		},
		disableAllVideo() {
			this.videoRequested = false
			localStorage.videoOutput = false
			this.stopOwnVideoTracks()

			for (const h of this.feeds) {
				if (!h.isScreenshare && !this.isScreenshareFeedId(h.rfid, h.rfdisplay)) {
					h.hangup()
				}
			}

			this.videoOutput = (localStorage.videoOutput !== 'false')
			this.publishOwnVideo()
		},
		toggleMute() {
			if (this.audioPluginHandle == null) {
				return
			}
			this.knownMuteState = this.audioPluginHandle.isAudioMuted()
			if (this.knownMuteState) {
				this.audioPluginHandle.unmuteAudio()
				this.audioPluginHandle.send({message: { request: 'configure', muted: false }})
			} else {
				this.audioPluginHandle.muteAudio()
				this.audioPluginHandle.send({message: { request: 'configure', muted: true }})
			}
			this.knownMuteState = this.audioPluginHandle.isAudioMuted()
		},
		async publishOwnVideo() {
			const media = {
				audioRecv: false,
				videoRecv: false,
				audioSend: false,
				videoSend: true,
			}
			const nextVideoInput = localStorage.videoInput || ''
			let hadPeerConnection = Boolean(this.videoPluginHandle.webrtcStuff?.pc)

			if (this.videoRequested) {
				if (hadPeerConnection && !this.publishingWithVideo) {
					this.videoPluginHandle.hangup()
					this.ourStream = null
					hadPeerConnection = false
				}
				media.video = this.cameraConstraints(nextVideoInput)
				if (hadPeerConnection && nextVideoInput !== this.videoInput) {
					media.replaceVideo = true
				}
			} else {
				this.stopOwnVideoTracks()
				if (this.publishingWithVideo && this.videoPublishingState !== 'unpublished' && this.videoPublishingState !== 'failed') {
					this.videoPublishingState = 'unpublishing'
					const unpublish = {request: 'unpublish'}
					this.videoPluginHandle.send({message: unpublish})
				} else {
					this.videoPublishingState = 'unpublished'
				}
				return
			}

			this.publishingWithVideo = this.videoRequested
			this.videoInput = nextVideoInput
			if (this.videoRequested) {
				this.videoPublishingState = 'publishing'
			}

			this.videoPluginHandle.createOffer(
				{
					media: media,
					// If you want to test simulcasting (Chrome and Firefox only), set to true
					simulcast: false,
					simulcast2: false,
					success: (jsep) => {
						const publish = {request: 'configure', audio: false, video: this.publishingWithVideo, bitrate: this.upstreamBitrate}
						this.videoPluginHandle.send({message: publish, jsep: jsep})
						if (!this.publishingWithVideo) {
							this.stopOwnVideoTracks()
						}
					},
					error: (error) => {
						this.videoPublishingState = 'failed'
						this.publishingError = error.message
					},
				})
		},
		cameraConstraints(videoInput) {
			if (!videoInput) {
				return true
			}
			const video = {
				width: {ideal: 1280},
				height: {ideal: 720},
				frameRate: {ideal: 30, max: 30},
			}
			video.deviceId = {exact: videoInput}
			return video
		},
		publishOwnAudio() {
			const media = {video: false}
			if (localStorage.audioInput) {
				media.audio = {deviceId: localStorage.audioInput}
			}
			if (localStorage.audioInput !== this.audioInput) {
				media.replaceAudio = true
				this.audioInput = localStorage.audioInput
			}
			this.audioPluginHandle.createOffer({
				media: media,
				success: (jsep) => {
					const publish = {request: 'configure', muted: this.knownMuteState}
					this.audioPluginHandle.send({message: publish, jsep: jsep})
				},
				error: (error) => {
					this.audioPublishingState = 'failed'
					this.publishingError = error.message
				},
			})
		},
		async publishOwnScreenshareFeed() {
			this.showScreensharePrompt = false
			this.screensharingError = null
			this.screensharingState = 'publishing'
			this.stopOwnScreenshareStream()

			let stream
			try {
				stream = await this.getScreenshareStream()
			} catch (error) {
				this.failScreenshare(error)
				return
			}

			this.ourScreenShareStream = stream
			this.showOwnScreenShare = true
			await this.$nextTick()
			const screenshareVideoEl = Array.isArray(this.$refs.ourScreenshareVideo) ? this.$refs.ourScreenshareVideo[0] : this.$refs.ourScreenshareVideo
			if (screenshareVideoEl) {
				Janus.attachMediaStream(screenshareVideoEl, stream)
				screenshareVideoEl.muted = 'muted'
			} else {
				this.$forceUpdate()
				await this.$nextTick()
				const screenshareVideoElRetry = Array.isArray(this.$refs.ourScreenshareVideo) ? this.$refs.ourScreenshareVideo[0] : this.$refs.ourScreenshareVideo
				if (screenshareVideoElRetry) {
					Janus.attachMediaStream(screenshareVideoElRetry, stream)
					screenshareVideoElRetry.muted = 'muted'
				}
			}
			this.onResize()
			stream.getVideoTracks()[0].onended = () => {
				if (this.screensharingState === 'published' || this.screensharingState === 'publishing') {
					this.unpublishOwnScreenshareFeed()
				}
			}

			const hasAudio = stream.getAudioTracks().length > 0
			const media = {audioRecv: false, videoRecv: false, audioSend: hasAudio, videoSend: true}
			this.screensharePluginHandle.createOffer(
				{
					media: media,
					stream: stream,
					success: (jsep) => {
						log('venueless', 'debug', 'Got publisher SDP!', jsep)
						const publish = {request: 'configure', audio: hasAudio, video: true, bitrate: this.upstreamBitrate}
						this.screensharePluginHandle.send({message: publish, jsep: jsep})
					},
					error: (error) => {
						this.failScreenshare(error)
					},
				})
		},
		subscribeRemoteVideo(id, display, audio, video) {
			const isScreenshare = this.isScreenshareFeedId(id, display)
			if (this.isOwnPublishedFeed(id) || (!this.videoOutput && !isScreenshare)) {
				return
			}
			const existingFeed = this.feeds.find(rf => this.feedIdEquals(rf.rfid, id))
			if (existingFeed) {
				existingFeed.rfdisplay = display
				existingFeed.videoCodec = video
				existingFeed.isScreenshare = isScreenshare
				if (!isScreenshare && video && !existingFeed.hasVideo && this.videoOutput) {
					this.removeRemoteFeed(id)
				} else {
					if (!isScreenshare && !video) {
						existingFeed.hasVideo = false
					}
					return
				}
			} else if (this.subscribingFeedIds.some(fid => this.feedIdEquals(fid, id))) {
				return
			}
			this.markSubscribing(id)
			let remoteFeed = null
			this.janus.attach({
				plugin: 'janus.plugin.videoroom',
				opaqueId: String(this.user.id),
				success: (pluginHandle) => {
					remoteFeed = pluginHandle
					remoteFeed.simulcastStarted = false
					log('venueless', 'info', 'Plugin attached! (' + remoteFeed.getPlugin() + ', id=' + remoteFeed.getId() + ')')
					// We wait for the plugin to send us an offer
					var subscribe = {
						request: 'join',
						room: this.janusRoomId,
						ptype: 'subscriber',
						feed: id,
						private_id: this.ourPrivateId,
					}
					// In case you don't want to receive audio, video or data, even if the
					// publisher is sending them, set the 'offer_audio', 'offer_video' or
					// 'offer_data' properties to false (they're true by default), e.g
					subscribe.offer_video = this.videoOutput || isScreenshare
					// For example, if the publisher is VP8 and this is Safari, let's avoid video
					if (Janus.webRTCAdapter.browserDetails.browser === 'safari' &&
						(video === 'vp9' || (video === 'vp8' && !Janus.safariVp8))) {
						if (video) {
							video = video.toUpperCase()
						}
						log('venueless', 'info', 'Publisher is using ' + video + ', but Safari doesn\'t support it: disabling video')
						subscribe.offer_video = false
					}
					remoteFeed.videoCodec = video
					remoteFeed.send({message: subscribe})
				},
				error: (error) => {
					this.unmarkSubscribing(id)
					log('venueless', 'error', '  -- Error attaching plugin...', error)
					alert('Error attaching plugin... ' + error)
				},
				onmessage: (msg, jsep) => {
					log('venueless', 'debug', ' ::: Got a message (subscriber) :::', msg)
					var event = msg.videoroom
					log('venueless', 'debug', 'Event: ' + event)
					if (msg.error) {
						this.unmarkSubscribing(id)
						log('venueless', 'error', 'Error when subscribing: ' + msg.error)
						// todo: show something?
					} else if (event) {
						if (event === 'attached') {
							// Subscriber created and attached
							const remoteFeedId = msg.id || id
							this.unmarkSubscribing(remoteFeedId)
							remoteFeed.rfattached = false
							remoteFeed.hasVideo = isScreenshare
							remoteFeed.rfid = remoteFeedId
							remoteFeed.rfdisplay = display
							remoteFeed.isScreenshare = isScreenshare
							remoteFeed.participant = this.participants.find(pp => this.feedIdEquals(pp.id, remoteFeed.rfid))
							remoteFeed.venueless_user = null
							if (!this.feeds.some(rf => this.feedIdEquals(rf.rfid, remoteFeed.rfid))) {
								this.feeds.push(remoteFeed)
								this.fetchUser(remoteFeed)
							}
						} else if (event === 'event') {
							// Check if we got a simulcast-related event from this publisher
							var substream = msg.substream
							var temporal = msg.temporal
							if ((substream !== null && substream !== undefined) ||
								(temporal !== null && temporal !== undefined)) {
								if (!remoteFeed.simulcastStarted) {
									remoteFeed.simulcastStarted = true
									// Add some new buttons
									// addSimulcastButtons(remoteFeed.rfindex,
									//	remoteFeed.videoCodec === 'vp8' || remoteFeed.videoCodec === 'h264')
								}
								// We just received notice that there's been a switch, update the buttons
								// updateSimulcastButtons(remoteFeed.rfindex, substream, temporal)
							}
						} else {
							// What has just happened?
						}
					}
					if (jsep) {
						log('venueless', 'debug', 'Handling SDP as well...', jsep)
						// Answer and attach
						remoteFeed.createAnswer({
							jsep: jsep,
							// Add data:true here if you want to subscribe to datachannels as well
							// (obviously only works if the publisher offered them in the first place)
							media: {audioSend: false, videoSend: false},	// We want recvonly audio/video
							success: (jsep) => {
								log('venueless', 'debug', 'Got SDP!', jsep)
								var body = {request: 'start', room: this.janusRoomId}
								remoteFeed.send({message: body, jsep: jsep})
							},
							error: (error) => {
								log('venueless', 'error', 'WebRTC error:', error)
								alert('WebRTC error... ' + error.message)
							},
						})
					}
				},
				iceState: (state) => {
					log('venueless', 'info',
						'ICE state of this WebRTC PeerConnection (feed #' + remoteFeed.rfid + ') changed to ' + state)
				},
				webrtcState: (on) => {
					log('venueless', 'info',
						'Janus says this WebRTC PeerConnection (feed #' + remoteFeed.rfid + ') is ' + (on ? 'up' : 'down') +
						' now')
				},
				slowLink: (uplink) => {
					log('venueless', 'info', 'slowLink on subscriber')
					this.downstreamSlowLinkCount++
				},
				onremotestream: (stream) => {
					log('venueless', 'debug', 'Remote feed #' + remoteFeed.rfid + ', stream:', stream)
					const rfindex = this.feeds.findIndex((rf) => this.feedIdEquals(rf.rfid, remoteFeed.rfid))
					if (rfindex === -1) {
						return
					}
					const videoTracks = stream.getVideoTracks()
					remoteFeed.rfattached = true
					remoteFeed.hasVideo = videoTracks && videoTracks.length > 0 && (remoteFeed.isScreenshare || !!remoteFeed.videoCodec)
					this.feeds.splice(rfindex, 1, remoteFeed)
					this.$nextTick(() => {
						const videoEl = this.$el.querySelector(`video[data-rfid="${remoteFeed.rfid}"]`)
						if (videoEl) {
							Janus.attachMediaStream(videoEl, stream)
						}
					})
				},
				oncleanup: () => {
					this.unmarkSubscribing(id)
					this.feeds = this.feeds.filter((rf) => !this.feedIdEquals(rf.rfid, id))
				}
			})
		},
		onJanusConnected() {
			// Roughly based on https://janus.conf.meetecho.com/audiobridgetest.js
			this.janus.attach(
				{
					plugin: 'janus.plugin.audiobridge',
					opaqueId: String(this.user.id),
					success: (pluginHandle) => {
						this.audioPluginHandle = pluginHandle
						log('venueless', 'info', 'Plugin attached! (' + this.audioPluginHandle.getPlugin() + ', id=' + this.audioPluginHandle.getId() + ')')

						const register = {
							request: 'join',
							room: this.janusRoomId,
							token: this.token,
							id: this.janusSessionId,
							display: 'venueless user',
							muted: this.automute
						}
						this.knownMuteState = this.automute
						this.audioPluginHandle.send({message: register})
					},
					error: (error) => {
						this.failConnection(error)
					},
					consentDialog: (on) => {
						this.waitingForConsent = on
					},
					iceState: (state) => {
						log('venueless', 'info', 'ICE state changed to ' + state)
						if (state === 'failed') {
							this.failConnection(`ICE connection ${state}`)
						}
					},
					mediaState: (medium, on) => {
						log('venueless', 'info', 'Janus ' + (on ? 'started' : 'stopped') + ' receiving our ' + medium)
						if (medium === 'audio') {
							this.audioReceived = on
						}
					},
					webrtcState: (on) => {
						log('venueless', 'info', 'Janus says our WebRTC PeerConnection is ' + (on ? 'up' : 'down') + ' now')
					},
					onmessage: (msg, jsep) => {
						const event = msg.audiobridge
						if (event) {
							if (event === 'joined') {
								if (msg.id) {
									log('venueless', 'info', 'Successfully joined audiobridge ' + msg.room + ' with ID ' + msg.id)

									this.ourAudioId = msg.id
									this.connectionState = 'connected'
									this.connectionError = null

									if (this.audioPublishingState !== 'published') {
										this.publishOwnAudio()
									}

									// Any remote feeds to attach to?
									this.participants = msg.participants || []
									if (msg.participants) {
										for (const p of this.participants) {
											this.fetchUser(p)
											if (p.talking && !this.talkingParticipants.some(id => this.feedIdEquals(id, p.id))) {
												this.talkingParticipants.push(p.id)
											}
										}
									}

									// start video plugin
									if (this.videoReceivingState === 'pending') {
										this.connectVideoroom()
									}
								} else {
									// someone else joined
									if (msg.participants) {
										for (const p of msg.participants) {
											this.fetchUser(p)
											if (!this.participants.find(pp => this.feedIdEquals(pp.id, p.id))) {
												this.participants.push(p)
											}
										}
									}
								}
							} else if (event === 'destroyed') {
								this.failConnection('Room destroyed', false)
							} else if (event === 'talking') {
								if (msg.id && !this.talkingParticipants.some(id => this.feedIdEquals(id, msg.id))) {
									this.talkingParticipants.push(msg.id)
								}
							} else if (event === 'stopped-talking') {
								this.talkingParticipants = this.talkingParticipants.filter(p => !this.feedIdEquals(p, msg.id))
							} else if (event === 'event') {
								if (msg.participants) {
									// Update e.g. muted states
									for (const p of msg.participants) {
										const exp = this.participants.find(e => this.feedIdEquals(e.id, p.id))
										if (exp) {
											exp.muted = p.muted
											if (p.talking && !this.talkingParticipants.some(id => this.feedIdEquals(id, p.id))) {
												this.talkingParticipants.push(p.id)
											} else if (this.talkingParticipants.some(id => this.feedIdEquals(id, p.id))) {
												this.talkingParticipants = this.talkingParticipants.filter(e => !this.feedIdEquals(e, p.id))
											}
										} else {
											this.fetchUser(p)
											this.participants.push(p)
										}
									}
								} else if (msg.leaving) {
									// One of the publishers has gone away?
									this.participants = this.participants.filter((rf) => !this.feedIdEquals(rf.id, msg.leaving))
								} else if (msg.error) {
									if (msg.error_code === 485) {
										this.failConnection('Room does not exist', false)
									} else {
										this.failConnection(`Server error: ${msg.error}`, false)
									}
								}
							}
						}
						if (jsep) {
							log('venueless', 'debug', 'Handling SDP as well...', jsep)
							this.audioPluginHandle.handleRemoteJsep({jsep: jsep})
						}
					},
					slowLink: (uplink) => {
						this.upstreamSlowLinkCount++
						if (this.upstreamSlowLinkCount > 2 && this.videoRequested) {
							const newUpstreamBitrate = Math.max(this.upstreamBitrate / 2, MIN_BITRATE)
							if (newUpstreamBitrate !== this.upstreamBitrate) {
								this.upstreamBitrate = newUpstreamBitrate
								log('venueless', 'info', 'Received slowLink on outgoing audio, reducing video bitrate to ' + this.upstreamBitrate)
								const publish = {request: 'configure', audio: false, video: this.publishingWithVideo, bitrate: this.upstreamBitrate}
								this.videoPluginHandle.send({message: publish})
								this.upstreamSlowLinkCount = 0
							} else {
								if (this.upstreamSlowLinkCount > 5) {
									log('venueless', 'info', 'Received slowLink on outgoing audio, video bitrate already at minimum, turning video off')
									this.videoRequested = false
									this.publishOwnVideo()
								} else {
									log('venueless', 'info', 'Received slowLink on outgoing audio, video bitrate already at minimum')
								}
							}
						}
					},
					onlocalstream: (stream) => {
						// Ignore our own audio stream, we don't want an echo, let's just confirm that it's there
						if (this.audioPluginHandle.webrtcStuff.pc.iceConnectionState !== 'completed' &&
							this.audioPluginHandle.webrtcStuff.pc.iceConnectionState !== 'connected') {
							this.audioPublishingState = 'publishing'
						} else {
							if (this.audioReceived) {
								this.audioPublishingState = 'published'
								this.publishingError = null
							}
						}
						if (this.knownMuteState) {
							// Mute client side as well as server side
							this.audioPluginHandle.muteAudio()
						}
					},
					onremotestream: (stream) => {
						this.audioReceivingState = 'receiving'
						Janus.attachMediaStream(this.$refs.mixedAudio, stream)
						if (localStorage.audioOutput) {
							if (this.$refs.mixedAudio.setSinkId) { // chrome only for now
								this.$refs.mixedAudio.setSinkId(localStorage.audioOutput)
							}
						}
					},
					oncleanup: () => {
						log('venueless', 'info', ' ::: Got a cleanup notification: we are unpublished now :::')
						this.audioPublishingState = 'unpublished'
					},
				})
		},
		connectVideoroom() {
			// Roughly based on https://janus.conf.meetecho.com/videoroomtest.js
			this.janus.attach(
				{
					plugin: 'janus.plugin.videoroom',
					opaqueId: String(this.ourAudioId),
					success: (pluginHandle) => {
						this.videoPluginHandle = pluginHandle
						log('venueless', 'info', 'Plugin attached! (' + this.videoPluginHandle.getPlugin() + ', id=' + this.videoPluginHandle.getId() + ')')

						const register = {
							request: 'join',
							room: this.janusRoomId,
							id: this.janusSessionId,
							ptype: 'publisher',
							token: this.token,
							display: 'venueless user',
						}
						this.videoPluginHandle.send({message: register})
					},
					error: (error) => {
						this.videoReceivingState = 'failed'
						this.failConnection(error)
					},
					consentDialog: (on) => {
						this.waitingForConsent = on
					},
					iceState: (state) => {
						log('venueless', 'info', 'ICE state changed to ' + state)
						if (state === 'failed') {
							this.videoReceivingState = 'failed'
							this.failConnection(`ICE connection ${state}`)
						}
					},
					mediaState: (medium, on) => {
						log('venueless', 'info', 'Janus ' + (on ? 'started' : 'stopped') + ' receiving our ' + medium)
						if (medium === 'video') {
							this.videoReceived = on
						}
						if (this.videoReceived) {
							this.videoPublishingState = 'published'
							this.publishingError = null
						} else if (!this.videoReceived && !this.videoRequested) {
							this.videoPublishingState = 'unpublished'
						}
					},
					webrtcState: (on) => {
						log('venueless', 'info', 'Janus says our WebRTC PeerConnection is ' + (on ? 'up' : 'down') + ' now')
					},
					onmessage: (msg, jsep) => {
						const event = msg.videoroom
						if (event) {
							if (event === 'joined') {
								log('venueless', 'info', 'Successfully joined room ' + msg.room + ' with ID ' + msg.id)

								// Publisher/manager created, negotiate WebRTC and attach to existing feeds, if any
								this.ourId = msg.id
								this.ourPrivateId = msg.private_id

								this.videoReceivingState = 'receiving'

								// Any remote feeds to attach to?
								if (msg.publishers) {
									this.videoPublishers = msg.publishers
									for (const f of msg.publishers) {
										this.subscribeRemoteVideo(f.id, f.display, f.audio_codec, f.video_codec)
									}
								}
								this.publishOwnVideo()
							} else if (event === 'destroyed') {
								this.videoReceivingState = 'failed'
								this.failConnection('Room destroyed', false)
							} else if (event === 'event') {
								// Any new feed to attach to?
								if (msg.publishers) {
									for (const f of msg.publishers) {
										if (!this.videoPublishers.find(rf => this.feedIdEquals(rf.id, f.id))) {
											this.videoPublishers.push(f)
										}
										this.subscribeRemoteVideo(f.id, f.display, f.audio_codec, f.video_codec)
									}
								} else if (msg.leaving) {
									// One of the publishers has gone away?
									const leaving = msg.leaving
									this.videoPublishers = this.videoPublishers.filter((rf) => !this.feedIdEquals(rf.id, leaving))
									this.removeRemoteFeed(leaving)
								} else if (msg.unpublished) {
									// One of the publishers has unpublished?
									const unpublished = msg.unpublished
									if (unpublished === 'ok') {
										// That's us
										this.videoPublishingState = 'unpublished'
										this.publishingError = null
										this.stopOwnVideoTracks()
										this.videoPluginHandle.hangup()
										return
									}
									this.videoPublishers = this.videoPublishers.filter((rf) => !this.feedIdEquals(rf.id, unpublished))
									this.removeRemoteFeed(unpublished)
								} else if (msg.error) {
									if (msg.error_code === 426) {
										this.videoReceivingState = 'failed'
										this.failConnection('Room does not exist', false)
									} else {
										this.videoReceivingState = 'failed'
										this.failConnection(`Server error: ${msg.error}`, false)
									}
								}
							}
						}
						if (jsep) {
							log('venueless', 'debug', 'Handling SDP as well...', jsep)
							this.videoPluginHandle.handleRemoteJsep({jsep: jsep})
							// Check if any of the media we wanted to publish has
							// been rejected (e.g., wrong or unsupported codec)
							var video = msg.video_codec
							if (this.ourStream && this.ourStream.getVideoTracks() && this.ourStream.getVideoTracks().length > 0 &&
								!video) {
								// todo: log, show error to user?
								this.videoRequested = false
								this.publishingWithVideo = false
								this.stopOwnVideoTracks()
							}
						}
					},
					slowLink: (uplink) => {
						this.upstreamSlowLinkCount++
						if (this.upstreamSlowLinkCount > 2) {
							const newUpstreamBitrate = Math.max(this.upstreamBitrate / 2, MIN_BITRATE)
							if (newUpstreamBitrate !== this.upstreamBitrate) {
								this.upstreamBitrate = newUpstreamBitrate
								log('venueless', 'info', 'Received slowLink on outgoing video, reducing bitrate to ' + this.upstreamBitrate)
								const publish = {request: 'configure', audio: false, video: this.publishingWithVideo, bitrate: this.upstreamBitrate}
								this.videoPluginHandle.send({message: publish})
								this.upstreamSlowLinkCount = 0
							} else {
								if (this.upstreamSlowLinkCount > 5) {
									log('venueless', 'info', 'Received slowLink on outgoing video, bitrate already at minimum, turning video off')
									this.videoRequested = false
									this.stopOwnVideoTracks()
									this.publishOwnVideo()
								} else {
									log('venueless', 'info', 'Received slowLink on outgoing video, bitrate already at minimum')
								}
							}
						}
					},
					onlocalstream: (stream) => {
						if (this.ourStream && this.ourStream !== stream) {
							this.stopStreamTracks(this.ourStream)
						}
						this.ourStream = stream
						if (this.videoPluginHandle.webrtcStuff.pc && this.videoPluginHandle.webrtcStuff.pc.iceConnectionState !== 'completed' &&
							this.videoPluginHandle.webrtcStuff.pc.iceConnectionState !== 'connected') {
							this.videoPublishingState = 'publishing'
						} else {
							if ((this.videoReceived || !this.publishingWithVideo) && this.audioReceived) {
								this.videoPublishingState = 'published'
								this.publishingError = null
							}
						}
						if (this.automute) {
							this.videoPluginHandle.muteAudio()
						}
						const videoTracks = stream.getVideoTracks()
						if (!videoTracks || videoTracks.length === 0) {
							this.videoRequested = false
							this.publishingWithVideo = false
						} else {
							const videoEl = Array.isArray(this.$refs.ourVideo) ? this.$refs.ourVideo[0] : this.$refs.ourVideo
							if (videoEl) {
								Janus.attachMediaStream(videoEl, stream)
							}
						}
					},
					oncleanup: () => {
						log('venueless', 'info', ' ::: Got a cleanup notification: we are unpublished now :::')
						this.videoPublishingState = 'unpublished'
					},
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
				error: (error) => {
					this.failConnection(error)
				},
				destroyed: () => {
					if (this.suppressDestroyedState) {
						this.suppressDestroyedState = false
						return
					}
					this.connectionState = 'disconnected'
				},
			})
		},
		initJanus() {
			this.connectionState = 'connecting'
			Janus.init({
				debug: 'all', // todo: conditional
				callback: this.onJanusInitialized,
				dependencies: Janus.useDefaultDependencies({
					adapter,
				})
			})
		},
		async fetchUser(feed) {
			const uid = feed.rfid || feed.id
			let user = this.userCache[uid]
			if (!user) {
				user = await api.call('januscall.identify', {id: uid})
				this.userCache[uid] = user
			}
			feed.venueless_user = user
			const rfindex = this.feeds.findIndex((rf) => this.feedIdEquals(rf.rfid, feed.rfid))
			if (rfindex > -1) {
				this.feeds.splice(rfindex, 1, feed)
			}
		},
	},
}
</script>
<style lang="stylus">
.c-janusconference
	background: #202124
	color: #e8eaed
	flex: auto 1 1
	height: 100%
	display: flex
	flex-direction: column
	position: relative

	.connection-state
		display: flex
		justify-content: center
		align-items: center
		flex: auto 1 1

	.participants
		padding: 6px 14px
		display: flex
		flex-wrap: wrap
		gap: 4px
		background: #2d2f31
		border-bottom: 1px solid #3c4043
		flex-shrink: 0

		.participant
			position: relative
			cursor: pointer
			display: inline-flex
			border: 3px solid transparent
			border-radius: 50%
			transition: border-color 0.15s
			&.talking
				border-color: #8ab4f8
			.mute-indicator
				position: absolute
				right: 0
				bottom: 0
				background: #ea4335
				width: 14px
				height: 14px
				border-radius: 50%
				display: flex
				align-items: center
				justify-content: center
				.bunt-icon
					color: white
					font-size: 9px
					line-height: 14px

	.users
		padding: 12px
		display: flex
		justify-content: center
		align-content: center
		flex-wrap: wrap
		gap: 8px
		height: auto
		max-height: 100%
		flex: auto 1 1
		overflow: hidden
		position: relative
		background: #202124

	.users .feed
		width: var(--video-width)
		height: var(--video-height)
		position: relative
		border-radius: 12px
		overflow: hidden

		.video-container
			background: #3c4043
			width: 100%
			height: 100%
			position: relative
			overflow: hidden
			border-radius: 12px
			transition: box-shadow 0.15s ease
			&.speaking
				box-shadow: 0 0 0 3px #8ab4f8
			video
				width: 100%
				height: 100%
				object-fit: cover

		.video-overlay
			position: absolute
			inset: 0
			pointer-events: none
			.badge-row
				position: absolute
				bottom: 8px
				left: 8px
				display: flex
				gap: 4px

		.badge
			background: rgba(0,0,0,0.55)
			backdrop-filter: blur(4px)
			color: #e8eaed
			font-size: 11px
			font-weight: 600
			border-radius: 4px
			padding: 2px 6px
			&.badge--me
				background: rgba(26,115,232,0.7)
			&.badge--screensharing
				background: rgba(52,168,83,0.75)

		.controls
			display: flex
			align-items: center
			padding: 0 8px 0 12px
			height: 40px
			position: absolute
			bottom: 8px
			right: 8px
			background: rgba(0,0,0,0.55)
			backdrop-filter: blur(4px)
			border-radius: 20px
			opacity: 0
			transition: opacity 0.2s
			gap: 4px
			.user
				display: flex
				cursor: pointer
				align-items: center
				gap: 6px
				.display-name
					max-width: 120px
					white-space: nowrap
					overflow: hidden
					text-overflow: ellipsis
					font-size: 13px
					color: #e8eaed

		&:hover .controls
			opacity: 1

		.novideo-indicator
			position: absolute
			inset: 0
			display: flex
			align-items: center
			justify-content: center
			background: #3c4043

		.mute-indicator
			position: absolute
			top: 10px
			right: 10px
			background: #ea4335
			width: 32px
			height: 32px
			border-radius: 50%
			display: flex
			align-items: center
			justify-content: center
			.bunt-icon
				color: white
				font-size: 18px
				line-height: 32px

	.users .feed.me
		.video-container video
			transform: rotateY(180deg)

	.users .feed.screenshare-feed
		.video-container video
			object-fit: contain

	.info-bar
		display: flex
		flex-direction: column
		align-items: center
		gap: 4px
		flex-shrink: 0

	.info-message
		color: #9aa0a6
		font-size: 13px
		text-align: center
		padding: 6px 16px
		&.screensharing-error
			color: #f28b82
			display: flex
			align-items: center
			gap: 6px

	.slow-banner
		box-sizing: border-box
		background: rgba(234,179,8,0.15)
		color: #fdd663
		cursor: pointer
		padding: 8px 16px
		position: absolute
		left: 0
		top: 0
		width: 100%
		text-align: center
		font-size: 13px

	.controlbar
		display: flex
		align-items: center
		justify-content: center
		gap: 8px
		padding: 12px 20px
		background: #2d2f31
		border-top: 1px solid #3c4043
		flex-shrink: 0
		z-index: 20

	.ctrl-btn
		display: flex
		align-items: center
		justify-content: center
		width: 52px
		height: 52px
		border-radius: 50%
		background: #3c4043
		color: #e8eaed
		cursor: pointer
		transition: background 0.15s, transform 0.1s
		border: none
		outline: none
		.mdi
			font-size: 24px
		&:hover
			background: #4a4d50
			transform: scale(1.07)
		&.ctrl-btn--active
			background: #8ab4f8
			color: #202124
		&.ctrl-btn--muted
			background: #ea4335
			color: white
		&.ctrl-btn--disabled
			opacity: 0.4
			cursor: not-allowed
			pointer-events: none
		&.ctrl-btn--hangup
			background: #ea4335
			color: white
			width: 64px
			border-radius: 32px
			&:hover
				background: #c5221f

	.size-tiny &
		.participants
			display: none
		.users
			padding: 0
			gap: 0
			.feed
				border-radius: 0
				.video-container
					border-radius: 0
		.controlbar, .controls, .mute-indicator, .badge-row
			display: none

	.screenshare-prompt
		.content
			display: flex
			flex-direction: column
			align-items: center
			padding: 32px
			gap: 16px
			text-align: center
			h1
				color: #e8eaed
				font-size: 20px
			.bunt-button
				themed-button-primary()
</style>

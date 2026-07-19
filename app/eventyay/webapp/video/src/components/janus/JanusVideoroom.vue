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
		.moderation-notice(v-if="moderationNotice")
			.mdi.mdi-information-outline
			span {{ moderationNotice }}
		.gallery(ref="container", :class="{ 'has-screen': hasScreenTile }", :style="gridStyle", v-resize-observer="onResize")
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
						:data-feed-id="tile.videoFeedId || tile.id",
						:muted="remoteVideoShouldBeMuted(tile)",
						autoplay,
						playsinline
					)
					audio(
						v-if="!tile.local && tile.audioFeedId",
						class="remote-audio",
						:data-audio-feed-id="tile.audioFeedId",
						autoplay
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
				:disabled="screenShareBlockedByHost || screenShareState === 'publishing' || screenShareState === 'unpublishing'",
				:title="screenShareBlockedByHost ? 'Screen sharing was disabled by the host' : (screenShareState === 'published' ? $t('JanusVideoroom:tool-screenshare:off') : $t('JanusVideoroom:tool-screenshare:on'))",
				@click="toggleScreenShare"
			)
				.mdi(:class="screenShareState === 'published' ? 'mdi-monitor-off' : 'mdi-monitor-share'")
			button.control-button.participants-button(type="button", :class="{ active: showParticipantsDrawer }", title="Participants", @click="showParticipantsDrawer = !showParticipantsDrawer")
				.mdi.mdi-account-multiple
				span.participant-count-badge {{ participantCount }}
			button.control-button(type="button", title="Settings", @click="showDevicePrompt = true")
				.mdi.mdi-cog
			button.control-button(type="button", title="Report issue", @click="showFeedbackPrompt = true")
				.mdi.mdi-message-alert-outline
			button.control-button.leave(type="button", :title="$t('JanusVideoroom:tool-hangup:tooltip')", @click="leaveRoom")
				.mdi.mdi-phone-hangup

	transition(name="participants-backdrop")
		.participants-backdrop(v-if="showParticipantsDrawer", @click="showParticipantsDrawer = false")
	transition(name="participants-drawer")
		.participants-drawer(v-if="showParticipantsDrawer")
			.participants-header
				.header-text
					h2 Participants
					span {{ participantCount }} in room
				.participants-header-actions
					button.end-meeting-button(v-if="canModerateParticipants", type="button", title="End meeting for all", :disabled="endingMeeting", @click="sendEndMeeting")
						.mdi.mdi-phone-hangup
						span End
					button.drawer-close(type="button", title="Close participants", @click="showParticipantsDrawer = false")
						.mdi.mdi-close
			.participants-list
				.participant-row(
					v-for="participant in participantRows",
					:key="participant.key",
					:class="{ 'is-local': participant.local, 'is-speaking': participant.speaking }"
				)
					avatar(:user="participant.user", :size="40")
					.participant-main
						.participant-name
							span.name {{ participant.label }}
							span.self-label(v-if="participant.local") You
						.participant-status(v-if="participant.statuses.length")
							span.status-item(v-for="status in participant.statuses", :key="status.key")
								.mdi(:class="status.icon")
								span {{ status.label }}
					.participant-media
						.mdi(:class="participant.cameraOn ? 'mdi-video' : 'mdi-video-off off'", :title="participant.cameraOn ? 'Camera on' : 'Camera off'")
						.mdi(:class="participant.micOn ? 'mdi-microphone' : 'mdi-microphone-off muted'", :title="participant.micOn ? 'Microphone on' : 'Muted'")
					.participant-actions(v-if="canModerateParticipants && !participant.local")
						button.participant-action-button(type="button", title="Participant actions", :aria-expanded="openParticipantMenu === participant.key ? 'true' : 'false'", @click.stop="toggleParticipantMenu(participant.key)")
							.mdi.mdi-dots-vertical
						.participant-action-menu(v-if="openParticipantMenu === participant.key")
							button(type="button", :disabled="!participant.audioFeedId || !participant.micOn || isModeratorActionPending(participant, 'mute_participant')", @click="sendModeratorAction(participant, 'mute_participant')")
								.mdi.mdi-microphone-off
								span Mute
							button(type="button", :disabled="!participant.videoFeedId || !participant.cameraOn || isModeratorActionPending(participant, 'stop_participant_video')", @click="sendModeratorAction(participant, 'stop_participant_video')")
								.mdi.mdi-video-off
								span Stop Video
							button(type="button", :disabled="!participant.screenShareFeedId || isModeratorActionPending(participant, 'disable_screenshare')", @click="sendModeratorAction(participant, 'disable_screenshare')")
								.mdi.mdi-monitor-off
								span Disable screenshare
							button.danger(type="button", :disabled="isModeratorActionPending(participant, 'remove_participant')", @click="sendModeratorAction(participant, 'remove_participant')")
								.mdi.mdi-account-remove
								span Remove

	chat-user-card(v-if="selectedUser", ref="avatarCard", :user="selectedUser", @close="selectedUser = null")
	transition(name="prompt")
		template
			a-v-device-prompt(v-if="showDevicePrompt", :video-preview="cameraEnabled", @close="closeDevicePrompt")
			feedback-prompt(v-if="showFeedbackPrompt", module="janus", :collectTrace="collectTrace", @close="showFeedbackPrompt = false")
</template>

<script>
import Janus from 'lib/janus.js'
import adapter from 'webrtc-adapter'
import {mapGetters, mapState} from 'vuex'
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
const LOG_ENTRIES = []

const log = (source, level, message) => {
	LOG_ENTRIES.push([source, (new Date()).toISOString(), level, JSON.stringify(message)])
	console.log(`[${level}][${source}]`, message)
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
			default: null
		},
		videoSessionId: {
			type: [Number, String],
			default: null
		},
		screenShareSessionId: {
			type: [Number, String],
			default: null
		},
		roomId: {
			type: [Number, String],
			required: true
		},
		eventRoomId: {
			type: [Number, String],
			default: null
		},
		isModerator: {
			type: Boolean,
			default: false
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
			showParticipantsDrawer: false,
			mediaStates: {},
			apiMessageHandler: null,
			selectedUser: null,
			openParticipantMenu: null,
			pendingModeratorActions: {},
			endingMeeting: false,
			screenShareBlockedByHost: false,
			moderationNotice: null,
			moderationNoticeTimeout: null,
		}
	},
	computed: {
		...mapGetters(['hasPermission']),
		...mapState(['user']),
		canModerateParticipants() {
			return this.isModerator ||
				this.hasPermission('room:januscall.moderate') ||
				this.hasPermission('room:bbb.moderate') ||
				this.hasPermission('room:update') ||
				this.hasPermission('world:update')
		},
		janusRoomId() {
			return Number(this.roomId)
		},
		janusSessionId() {
			return Number(this.sessionId)
		},
		janusAudioSessionId() {
			return Number(this.audioSessionId || this.sessionId)
		},
		janusVideoSessionId() {
			return Number(this.videoSessionId || Number(this.sessionId) + 1)
		},
		janusScreenShareSessionId() {
			return Number(this.screenShareSessionId || Number(this.sessionId) + 1000000000)
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
		hasScreenTile() {
			return this.tiles.some(tile => tile.screen)
		},
		participantRows() {
			const rows = new Map()
			const localState = this.currentMediaState()
			rows.set(`local-${this.user?.id || 'user'}`, {
				key: `local-${this.user?.id || 'user'}`,
				local: true,
				user: this.user,
				label: this.user?.profile?.display_name || 'You',
				micOn: localState.micOn,
				cameraOn: localState.cameraOn,
				sharingScreen: localState.sharingScreen,
				speaking: localState.micOn && this.activeSpeakerId === 'local',
				audioFeedId: this.normalizeFeedId(this.ourAudioId || this.janusAudioSessionId),
				videoFeedId: this.normalizeFeedId(this.ourVideoId || this.janusVideoSessionId),
				screenShareFeedId: this.normalizeFeedId(this.janusScreenShareSessionId),
			})
			for (const feed of this.remoteFeeds) {
				if (!feed.user?.id) continue
				const userId = this.normalizeFeedId(feed.user.id)
				const mediaState = this.mediaStates[userId]
				const hasMediaState = Boolean(mediaState)
				const key = `remote-${userId}`
				const row = rows.get(key) || {
					key,
					local: false,
					user: feed.user,
					label: feed.user?.profile?.display_name || 'Participant',
					micOn: Boolean(mediaState?.micOn),
					cameraOn: Boolean(mediaState?.cameraOn),
					sharingScreen: Boolean(mediaState?.sharingScreen),
					speaking: false,
					audioFeedId: null,
					videoFeedId: null,
					screenShareFeedId: null,
				}
				if (!hasMediaState && (feed.feedType === 'screen' || feed.isScreenShare)) {
					row.sharingScreen = true
				}
				if (feed.feedType === 'screen' || feed.isScreenShare) {
					row.screenShareFeedId = this.normalizeFeedId(feed.id)
				}
				const hasVideoTrack = Boolean(feed.stream?.getVideoTracks().length)
				if (!hasMediaState && (feed.feedType === 'video' || feed.hasVideo || hasVideoTrack)) {
					row.cameraOn = Boolean(feed.hasVideo || hasVideoTrack)
				}
				if (feed.feedType === 'video' || feed.hasVideo || hasVideoTrack) {
					row.videoFeedId = this.normalizeFeedId(feed.id)
				}
				const hasAudioTrack = Boolean(feed.stream?.getAudioTracks().length)
				if (!hasMediaState && (feed.feedType === 'audio' || hasAudioTrack)) {
					row.micOn = hasAudioTrack && !feed.muted
				}
				if (feed.feedType === 'audio' || hasAudioTrack) {
					row.audioFeedId = this.normalizeFeedId(feed.id)
				}
				row.speaking = row.micOn && this.activeSpeakerId === this.normalizeFeedId(feed.id)
				rows.set(key, row)
			}
			return Array.from(rows.values()).map(row => ({
				...row,
				statuses: this.participantStatuses(row),
			})).sort((a, b) => {
				if (a.local) return -1
				if (b.local) return 1
				return a.label.localeCompare(b.label)
			})
		},
		participantCount() {
			return this.participantRows.length
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
			const remoteTiles = this.groupedRemoteTiles()
			return localTiles.concat(remoteTiles)
		},
	},
	watch: {
		tiles() {
			this.$nextTick(() => {
				this.onResize()
			})
		}
	},
	mounted() {
		LOG_ENTRIES.splice(0, LOG_ENTRIES.length)
		window.__JANUS_DEBUG_LOGS__ = () => LOG_ENTRIES
			.map(([source, timestamp, level, message]) => `${timestamp} [${level}] [${source}] ${message}`)
			.join('\n')
		window.__JANUS_DEBUG_JSON__ = () => JSON.stringify(LOG_ENTRIES, null, 2)
		window.__JANUS_COPY_DEBUG_LOGS__ = () => copy(window.__JANUS_DEBUG_LOGS__())
		this.apiMessageHandler = this.onApiMessage.bind(this)
		api.on('message', this.apiMessageHandler)
		this.cleaningUp = false
		this.initJanus()
		this.loadMediaStates()
		this.slowLinkInterval = window.setInterval(() => {
			this.downstreamSlowLinkCount = Math.max(this.downstreamSlowLinkCount - 1, 0)
			this.upstreamSlowLinkCount = Math.max(this.upstreamSlowLinkCount - 1, 0)
		}, 10000)
		this.audioLevelInterval = window.setInterval(this.refreshAudioLevels, AUDIO_LEVEL_INTERVAL)
	},
	unmounted() {
		if (this.apiMessageHandler) {
			api.off('message', this.apiMessageHandler)
			this.apiMessageHandler = null
		}
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
			if (this.moderationNoticeTimeout) {
				window.clearTimeout(this.moderationNoticeTimeout)
			}
	},
	methods: {
		collectTrace() {
			return LOG_ENTRIES
		},
		currentMediaState() {
			const localHasAudio = Boolean(this.localAudioStream?.getAudioTracks().some(track => track.readyState === 'live' && track.enabled))
			return {
				micOn: localHasAudio && !this.micMuted,
				cameraOn: this.localCameraActive,
				sharingScreen: Boolean(this.screenShareStream),
			}
		},
		onApiMessage(message) {
			const [name, payload] = message
			if (this.normalizeFeedId(payload?.room) !== this.normalizeFeedId(this.eventRoomId)) {
				return
			}
			if (name === 'januscall.media_state') {
				this.mergeMediaStates({
					[this.normalizeFeedId(payload.user)]: payload.state,
				})
			} else if (name === 'januscall.moderation_action') {
				this.handleModeratorAction(payload)
			}
		},
		mergeMediaStates(states) {
			const normalizedStates = {}
			for (const [userId, state] of Object.entries(states || {})) {
				normalizedStates[this.normalizeFeedId(userId)] = {
					micOn: Boolean(state?.micOn),
					cameraOn: Boolean(state?.cameraOn),
					sharingScreen: Boolean(state?.sharingScreen),
				}
			}
			this.mediaStates = {
				...this.mediaStates,
				...normalizedStates,
			}
		},
		async loadMediaStates() {
			if (!this.eventRoomId) return
			try {
				const response = await api.call('januscall.media_state.list', {
					room: this.eventRoomId,
				})
				this.mergeMediaStates(response?.states)
			} catch (error) {
				log('janus-media-state', 'warn', {
					action: 'loadMediaStates:error',
					error: error?.message || error,
					name: error?.name,
				})
			}
		},
		showModerationNotice(message) {
			this.moderationNotice = message
			if (this.moderationNoticeTimeout) {
				window.clearTimeout(this.moderationNoticeTimeout)
			}
			this.moderationNoticeTimeout = window.setTimeout(() => {
				this.moderationNotice = null
				this.moderationNoticeTimeout = null
			}, 5000)
		},
		handleModeratorAction(payload) {
			if (payload.action === 'end_meeting') {
				this.micMuted = true
				this.localCameraActive = false
				this.sendMediaState()
				this.cleanup()
				this.$emit('hangup', {message: 'The meeting was ended by the host.'})
				return
			}
			if (this.normalizeFeedId(payload?.target_user) !== this.normalizeFeedId(this.user?.id)) {
				return
			}
			if (payload.action === 'mute_participant') {
				this.micMuted = true
				this.applyMicState()
				this.sendMediaState()
				this.showModerationNotice('You were muted by the host.')
			} else if (payload.action === 'stop_participant_video') {
				this.cameraEnabled = false
				localStorage.videoRequested = false
				this.unpublishVideoMedia()
				this.showModerationNotice('Your camera was turned off by the host.')
			} else if (payload.action === 'remove_participant') {
				this.micMuted = true
				this.localCameraActive = false
				this.sendMediaState()
				this.cleanup()
				this.$emit('hangup', {message: 'You were removed by the host.'})
			} else if (payload.action === 'disable_screenshare') {
				this.screenShareBlockedByHost = true
				if (this.screenShareState === 'published' || this.screenShareState === 'publishing') {
					this.stopScreenShare()
				} else {
					this.stopPendingScreenShareTracks()
				}
				this.showModerationNotice('Screen sharing was disabled by the host.')
			}
		},
		toggleParticipantMenu(key) {
			this.openParticipantMenu = this.openParticipantMenu === key ? null : key
		},
		moderatorActionKey(participant, action) {
			return `${participant.key}:${action}`
		},
		isModeratorActionPending(participant, action) {
			return Boolean(this.pendingModeratorActions[this.moderatorActionKey(participant, action)])
		},
		targetFeedIdForAction(participant, action) {
			if (action === 'mute_participant') return participant.audioFeedId
			if (action === 'stop_participant_video') return participant.videoFeedId
			if (action === 'disable_screenshare') return participant.screenShareFeedId
			return participant.audioFeedId || participant.videoFeedId || participant.screenShareFeedId
		},
		async sendModeratorAction(participant, action) {
			const targetFeedId = this.targetFeedIdForAction(participant, action)
			if (!targetFeedId) return
			const key = this.moderatorActionKey(participant, action)
			this.pendingModeratorActions = {
				...this.pendingModeratorActions,
				[key]: true,
			}
			this.openParticipantMenu = null
			try {
				await api.call(`januscall.${action}`, {
					room: this.eventRoomId,
					target_feed_id: targetFeedId,
				})
			} catch (error) {
				const denied = error?.error === 'protocol.denied' || error?.code === 'protocol.denied'
				this.showModerationNotice(denied ? 'Permission denied.' : 'Could not apply moderator action.')
				log('janus-moderation', 'warn', {
					action: 'sendModeratorAction:error',
					command: action,
					targetFeedId,
					error: error?.message || error,
					name: error?.name,
				})
			} finally {
				const nextPending = {...this.pendingModeratorActions}
				delete nextPending[key]
				this.pendingModeratorActions = nextPending
			}
		},
		async sendEndMeeting() {
			if (this.endingMeeting) return
			this.endingMeeting = true
			this.openParticipantMenu = null
			try {
				await api.call('januscall.end_meeting', {
					room: this.eventRoomId,
				})
			} catch (error) {
				const denied = error?.error === 'protocol.denied' || error?.code === 'protocol.denied'
				this.showModerationNotice(denied ? 'Permission denied.' : 'Could not end the meeting.')
				log('janus-moderation', 'warn', {
					action: 'sendEndMeeting:error',
					error: error?.message || error,
					name: error?.name,
				})
				this.endingMeeting = false
			}
		},
		async sendMediaState() {
			if (!this.eventRoomId) return
			const state = this.currentMediaState()
			this.mergeMediaStates({
				[this.normalizeFeedId(this.user?.id)]: state,
			})
			try {
				const response = await api.call('januscall.media_state', {
					room: this.eventRoomId,
					...state,
				})
				this.mergeMediaStates(response?.states)
			} catch (error) {
				log('janus-media-state', 'warn', {
					action: 'sendMediaState:error',
					error: error?.message || error,
					name: error?.name,
				})
			}
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
					this.subscribeToFeed(
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
				simulcast: false,
				simulcast2: false,
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
			this.sendMediaState()
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
			this.sendMediaState()
		},
		onLocalVideoStream(stream) {
			this.localVideoStream = stream
			this.localCameraActive = stream.getVideoTracks().some(track => track.readyState === 'live')
			log('janus-video-publisher', 'debug', {
				action: 'onLocalVideoStream',
				localCameraActive: this.localCameraActive,
				stream: summarizeStream(stream),
			})
			this.attachLocalVideo(stream)
			this.publishingState = 'published'
			this.publishingError = null
			this.sendMediaState()
		},
		applyMicState() {
			if (this.localAudioStream) {
				for (const track of this.localAudioStream.getAudioTracks()) {
					track.enabled = !this.micMuted
				}
			}
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
			this.sendMediaState()
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
			if (this.screenShareBlockedByHost) {
				this.showModerationNotice('Screen sharing was disabled by the host.')
				return
			}
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
			this.sendMediaState()
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
			this.sendMediaState()
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
			this.sendMediaState()
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
			this.sendMediaState()
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
				this.subscribeToFeed(publisher.id, publisher.display, publisher.audio_codec, publisher.video_codec)
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
			if (this.isOwnFeed(feedId) || (!this.videoOutput && feedType === 'video')) {
				log('janus-subscriber', 'debug', {
					action: 'subscribeToFeed:skip-own-or-output',
					feedId: id,
					feedType,
				})
				return
			}
			const existingFeed = this.remoteFeeds.find(feed => this.feedIdEquals(feed.id, id))
			if (existingFeed) {
				if (feedType === 'video' && videoCodec && !existingFeed.stream?.getVideoTracks().length) {
					log('janus-subscriber', 'debug', {
						action: 'subscribeToFeed:reattach-video-without-track',
						feedId: id,
						videoCodec,
					})
					this.removeRemoteFeed(id)
				} else {
					existingFeed.display = display
					existingFeed.audioCodec = audioCodec
					existingFeed.videoCodec = videoCodec
					existingFeed.feedType = feedType
					existingFeed.isScreenShare = isScreenShare
					this.upsertRemoteFeed(existingFeed)
					return
				}
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
						feed: feedId,
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
					this.removeRemoteFeed(feedId, false)
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
				}
				return
			}
			if (event === 'attached') {
				const id = this.normalizeFeedId(msg.id || feedId)
				this.unmarkSubscribing(id)
				this.clearSubscriberRetry(id)
				this.upsertRemoteFeed({
					id,
					handle,
					display,
					feedType,
					isScreenShare: feedType === 'screen',
					audioCodec,
					videoCodec,
					attached: false,
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
						log('janus-subscriber', 'debug', {
							action: 'createAnswer:success',
							feedId: this.normalizeFeedId(feedId),
							answerHasVideo: Boolean(answer?.sdp?.includes('m=video')),
						})
						handle.send({message: {request: 'start', room: this.janusRoomId}, jsep: answer})
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
		onRemoteTrack(feedId, track, on) {
			if (!track) return
			const id = this.normalizeFeedId(feedId)
			const feed = this.remoteFeeds.find(item => this.feedIdEquals(item.id, id))
			log('janus-subscriber', 'debug', {
				action: 'onRemoteTrack',
				feedId: id,
				on,
				track: summarizeTrack(track),
				hasFeed: Boolean(feed),
			})
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
			const tracks = pc.getReceivers()
				.map(receiver => receiver.track)
				.filter(track => track && track.readyState !== 'ended')
			log('janus-subscriber', 'debug', {
				action: 'syncRemoteTracksFromPeerConnection',
				feedId: id,
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
			if (localStorage.audioOutput && element.setSinkId) {
				element.setSinkId(localStorage.audioOutput)
			}
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
			const screenTiles = []
			for (const feed of this.remoteFeeds) {
				const id = this.normalizeFeedId(feed.id)
				if (feed.isScreenShare || feed.feedType === 'screen') {
					const level = this.normalizedAudioLevel(id)
					screenTiles.push({
						key: `remote-screen-${id}`,
						id,
						videoFeedId: id,
						audioFeedId: null,
						local: false,
						screen: true,
						user: feed.user,
						label: this.feedLabel(feed),
						hasVideo: feed.hasVideo,
						muted: feed.muted,
						audioLevel: level,
						speaking: this.activeSpeakerId === id
					})
					continue
				}
				if (!feed.user?.id) continue
				const userId = this.normalizeFeedId(feed.user.id)
				const mediaState = this.mediaStates[userId]
				const existingTile = participantTiles.get(userId) || {
					key: `remote-user-${userId}`,
					id: `user-${userId}`,
					videoFeedId: null,
					audioFeedId: null,
					audioMeterFeedId: null,
					local: false,
					screen: false,
					user: feed.user,
					label: feed.user?.profile?.display_name || 'Participant',
					hasVideo: Boolean(mediaState?.cameraOn),
					muted: mediaState ? !mediaState.micOn : true,
					audioLevel: 0,
					speaking: false
				}
				if (feed.feedType === 'video' || feed.hasVideo || feed.stream?.getVideoTracks().length) {
					existingTile.videoFeedId = id
					existingTile.hasVideo = mediaState ? Boolean(mediaState.cameraOn) : Boolean(feed.hasVideo)
				}
				if (feed.feedType === 'audio' || feed.stream?.getAudioTracks().length) {
					existingTile.audioFeedId = id
					existingTile.audioMeterFeedId = id
					existingTile.muted = mediaState ? !mediaState.micOn : feed.muted
				}
				participantTiles.set(userId, existingTile)
			}
			for (const tile of participantTiles.values()) {
				const meterId = tile.audioMeterFeedId || tile.audioFeedId || tile.videoFeedId
				tile.id = tile.videoFeedId || tile.audioFeedId || tile.id
				tile.audioLevel = meterId ? this.normalizedAudioLevel(meterId) : 0
				tile.speaking = meterId ? this.activeSpeakerId === meterId : false
			}
			const sortedParticipantTiles = Array.from(participantTiles.values())
				.sort((a, b) => a.label.localeCompare(b.label))
			screenTiles.sort((a, b) => a.label.localeCompare(b.label))
			return screenTiles.concat(sortedParticipantTiles)
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
					if (this.feedIdEquals(user?.id, this.user?.id)) {
						log('janus-subscriber', 'warn', {
							action: 'fetchFeedUser:skip-own-user-feed',
							feedId: this.normalizeFeedId(feedId),
							userId: user?.id,
						})
						this.removeRemoteFeed(feedId)
						return
					}
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
			for (const video of this.$el.querySelectorAll('video[data-feed-id]')) {
				if (localStorage.audioOutput && video.setSinkId) {
					log('janus-devices', 'debug', {
						action: 'setSinkId',
						feedId: video.dataset.feedId,
						audioOutput: localStorage.audioOutput,
					})
					video.setSinkId(localStorage.audioOutput)
				}
			}
		},
		disableIncomingVideo() {
			this.videoOutput = false
			localStorage.videoOutput = false
			for (const feed of this.remoteFeeds.slice()) {
				if (feed.feedType === 'video') {
					this.removeRemoteFeed(feed.id)
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
				localStorage.videoRequested = false
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
				window.AudioContext = window.AudioContext || window.webkitAudioContext
				const context = new AudioContext()
				const meter = new SoundMeter(context)
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
		closeAudioMeter(id) {
			const meter = this.audioMeters[id]
			if (!meter) return
			log('janus-audio-meter', 'debug', {
				action: 'closeAudioMeter',
				id,
			})
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
		remoteVideoShouldBeMuted(tile) {
			return Boolean(tile.audioFeedId && tile.videoFeedId && !this.feedIdEquals(tile.audioFeedId, tile.videoFeedId))
		},
		participantStatuses(participant) {
			const statuses = []
			if (participant.speaking) {
				statuses.push({key: 'speaking', icon: 'mdi-volume-high', label: 'Speaking'})
			}
			if (participant.sharingScreen) {
				statuses.push({key: 'screen', icon: 'mdi-monitor-share', label: 'Sharing screen'})
			}
			if (!participant.cameraOn) {
				statuses.push({key: 'camera-off', icon: 'mdi-video-off', label: 'Camera off'})
			}
			if (!participant.micOn) {
				statuses.push({key: 'mic-muted', icon: 'mdi-microphone-off', label: 'Muted'})
			}
			return statuses
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
			return String(id).split('_')[0]
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
		stopStreamTracks(stream) {
			for (const track of stream.getTracks()) {
				track.onended = null
				track.stop()
			}
		},
		onResize() {
			if (!this.$refs.container) return
			if (this.hasScreenTile) {
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
			for (const id of Object.keys(this.audioMeters)) {
				this.closeAudioMeter(id)
			}
			this.remoteFeeds = []
			this.subscribingFeedIds = []
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
			this.micMuted = true
			this.localCameraActive = false
			this.screenShareStream = null
			this.sendMediaState()
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
		position: relative

	.moderation-notice
		align-items: center
		align-self: center
		background: rgba(47, 128, 237, .95)
		border-radius: 6px
		box-shadow: 0 8px 24px rgba(0,0,0,.32)
		color: #fff
		display: flex
		font-size: 14px
		font-weight: 650
		gap: 8px
		margin-top: 12px
		max-width: calc(100% - 24px)
		padding: 10px 14px
		position: absolute
		top: 0
		z-index: 18
		.mdi
			font-size: 19px

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
			.video-tile.is-screen
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
		&.participants-button
			position: relative

	.participant-count-badge
		align-items: center
		background: #f6f7f9
		border: 2px solid #2c323c
		border-radius: 99px
		color: #111317
		display: flex
		font-size: 11px
		font-weight: 700
		height: 20px
		justify-content: center
		line-height: 1
		min-width: 20px
		padding: 0 5px
		position: absolute
		right: -4px
		top: -4px

	.participants-backdrop
		background: rgba(0,0,0,.35)
		bottom: 0
		left: 0
		position: absolute
		right: 0
		top: 0
		z-index: 20

	.participants-backdrop-enter-active,
	.participants-backdrop-leave-active
		transition: opacity .18s ease
	.participants-backdrop-enter-from,
	.participants-backdrop-leave-to
		opacity: 0

	.participants-drawer
		background: #1b1f26
		border-left: 1px solid #323944
		box-sizing: border-box
		box-shadow: -12px 0 30px rgba(0,0,0,.36)
		bottom: 0
		color: #f6f7f9
		display: flex
		flex-direction: column
		min-height: 0
		position: absolute
		right: 0
		top: 0
		width: min(320px, 100%)
		z-index: 21

	.participants-drawer-enter-active,
	.participants-drawer-leave-active
		transition: transform .22s ease, opacity .22s ease
	.participants-drawer-enter-from,
	.participants-drawer-leave-to
		opacity: 0
		transform: translateX(100%)

	.participants-header
		align-items: center
		border-bottom: 1px solid #323944
		display: flex
		flex: none
		justify-content: space-between
		padding: 18px 18px 14px
		.header-text
			display: flex
			flex-direction: column
			gap: 3px
			min-width: 0
		h2
			font-size: 18px
			font-weight: 700
			line-height: 1.25
			margin: 0
		span
			color: #aeb6c2
			font-size: 13px

	.participants-header-actions
		align-items: center
		display: flex
		flex: none
		gap: 8px

	.end-meeting-button
		align-items: center
		background: #5a2426
		border: 1px solid #7c3034
		border-radius: 6px
		color: #fff
		cursor: pointer
		display: flex
		flex: none
		font-size: 13px
		font-weight: 600
		gap: 5px
		height: 34px
		padding: 0 10px
		.mdi
			font-size: 18px
		&:hover,
		&:focus-visible
			background: #733034
			outline: none
		&:disabled
			cursor: default
			opacity: .65

	.drawer-close
		align-items: center
		background: #2c323c
		border: 0
		border-radius: 50%
		color: #f6f7f9
		cursor: pointer
		display: flex
		flex: none
		height: 36px
		justify-content: center
		width: 36px
		.mdi
			font-size: 22px
		&:hover
			background: #3a4350

	.participants-list
		box-sizing: border-box
		display: flex
		flex: auto 1 1
		flex-direction: column
		gap: 6px
		min-height: 0
		overflow-y: auto
		padding: 10px

	.participant-row
		align-items: center
		background: transparent
		border: 0
		border-radius: 8px
		box-sizing: border-box
		color: inherit
		display: flex
		gap: 12px
		min-height: 64px
		min-width: 0
		padding: 10px
		position: relative
		text-align: left
		width: 100%
		&.is-speaking
			box-shadow: inset 3px 0 0 #31c48d

	.participant-main
		display: flex
		flex: auto 1 1
		flex-direction: column
		gap: 5px
		min-width: 0

	.participant-name
		align-items: center
		display: flex
		gap: 7px
		min-width: 0
		.name
			color: #f6f7f9
			font-size: 14px
			font-weight: 650
			min-width: 0
			overflow: hidden
			text-overflow: ellipsis
			white-space: nowrap
		.self-label
			background: #303844
			border-radius: 99px
			color: #cbd3de
			flex: none
			font-size: 11px
			font-weight: 700
			padding: 2px 7px

	.participant-status
		color: #aeb6c2
		display: flex
		flex-wrap: wrap
		gap: 6px 10px
		min-width: 0

	.status-item
		align-items: center
		display: flex
		font-size: 12px
		gap: 4px
		line-height: 1.2
		min-width: 0
		.mdi
			font-size: 15px

	.participant-media
		align-items: center
		color: #cbd3de
		display: flex
		flex: none
		gap: 6px
		height: 32px
		justify-content: center
		min-width: 32px
		.mdi
			color: #cbd3de
			font-size: 21px
			&.off
				color: #aeb6c2
			&.muted
				color: #ff8f86

	.participant-actions
		flex: none
		position: relative

	.participant-action-button
		align-items: center
		background: transparent
		border: 0
		border-radius: 6px
		color: #cbd3de
		cursor: pointer
		display: flex
		height: 32px
		justify-content: center
		width: 32px
		.mdi
			font-size: 21px
		&:hover,
		&:focus-visible
			background: #2c323c
			color: #fff
			outline: none

	.participant-action-menu
		background: #242a33
		border: 1px solid #3a4350
		border-radius: 8px
		box-shadow: 0 10px 28px rgba(0,0,0,.38)
		display: flex
		flex-direction: column
		min-width: 190px
		padding: 6px
		position: absolute
		right: 0
		top: 36px
		z-index: 24
		button
			align-items: center
			background: transparent
			border: 0
			border-radius: 6px
			color: #f6f7f9
			cursor: pointer
			display: flex
			font-size: 13px
			gap: 8px
			height: 34px
			padding: 0 10px
			text-align: left
			.mdi
				font-size: 18px
			&:hover,
			&:focus-visible
				background: #313945
				outline: none
			&:disabled
				color: #798392
				cursor: default
				&:hover
					background: transparent
			&.danger
				color: #ffaaa4

	&.size-tiny
		.gallery
			gap: 0
			padding: 0
		.video-tile,
		.media-frame
			border-radius: 0
		.tile-top,
		.tile-bottom,
		.participants-backdrop,
		.participants-drawer,
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
				.video-tile.is-screen
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
		.participants-drawer
			border-left: 0
			border-top: 1px solid #323944
			height: min(70%, 560px)
			top: auto
			width: 100%
</style>

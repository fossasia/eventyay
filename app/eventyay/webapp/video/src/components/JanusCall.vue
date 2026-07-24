<template lang="pug">
.c-januscall(:class="[`size-${size}`]")
	.error(v-if="error") {{ $t('JanusCall:error:text') }}
	// Pre-join screen
	janus-prejoin(
		v-else-if="!joined && !left && !requestingAdmission && !waitingForAdmission && !denied && !error",
		:roomName="room.name || 'Meeting Room'",
		@join="onPrejoinComplete"
	)
	.waiting-room(v-else-if="requestingAdmission && !joined && !error")
		.waiting-room-inner
			.waiting-room-icon
				.mdi.mdi-account-arrow-right-outline
			h2 Requesting access...
			p {{ room.name || 'Meeting Room' }}
	.waiting-room(v-else-if="waitingForAdmission && !joined && !error")
		.waiting-room-inner
			.waiting-room-icon
				.mdi.mdi-account-clock-outline
			h2 Waiting for host to admit you...
			p {{ room.name || 'Meeting Room' }}
			button.left-room-button(type="button", @click="cancelWaitingRoom")
				.mdi.mdi-close
				span Leave
	.denied-room(v-else-if="denied && !error")
		.left-room-inner
			.left-room-icon
				.mdi.mdi-account-cancel-outline
			h2 The host declined your request to join
			p {{ room.name || 'Meeting Room' }}
			.left-room-actions
				button.left-room-button.primary(type="button", @click="returnToPrejoin")
					.mdi.mdi-refresh
					span Try again
				button.left-room-button(type="button", @click="$router.push('/')")
					.mdi.mdi-arrow-left
					span Back to event
	.left-room(v-else-if="left && !error")
		.left-room-inner
			.left-room-icon
				.mdi.mdi-phone-hangup
			h2 {{ leftMessage }}
			p {{ room.name || 'Meeting Room' }}
			.left-room-actions
				button.left-room-button.primary(type="button", @click="rejoinRoom")
					.mdi.mdi-phone
					span Rejoin
				button.left-room-button(type="button", @click="$router.push('/')")
					.mdi.mdi-arrow-left
					span Back to event
	// Live call
	janus-videoroom(
		v-else-if="joined && server",
		:server="server",
		:token="token",
		:iceServers="iceServers",
		:sessionId="sessionId",
		:audioSessionId="audioSessionId",
		:videoSessionId="videoSessionId",
		:screenShareSessionId="screenShareSessionId",
		:roomId="roomId",
		:eventRoomId="room.id",
		:is-moderator="isModerator",
		:size="size",
		:automute="joinedWithMicMuted",
		@hangup="onRoomLeft"
	)
</template>
<script>
import api from 'lib/api'
import JanusVideoroom from 'components/janus/JanusVideoroom'
import JanusPrejoin from 'components/janus/JanusPrejoin'

export default {
	components: { JanusVideoroom, JanusPrejoin },
	props: {
		room: {
			type: Object,
			required: true
		},
		module: {
			type: Object,
			required: true
		},
		size: {
			type: String, // 'normal', 'tiny'
			default: 'normal'
		},
		background: Boolean
	},
	data() {
		return {
			server: null,
			token: null,
			iceServers: [],
			roomId: null,
			sessionId: null,
			audioSessionId: null,
			videoSessionId: null,
			screenShareSessionId: null,
			isModerator: false,
			loading: false,
			error: null,
			roomUrlPromise: null,
			// Pre-join state
			joined: false,
			left: false,
			requestingAdmission: false,
			waitingForAdmission: false,
			denied: false,
			leftMessage: 'You left the room',
			joinedWithMicMuted: true,
			apiMessageHandler: null,
		}
	},
	computed: {},
	async created() {
		// In tiny/background mode, skip the prejoin screen and join immediately
		if (this.size === 'tiny' || this.background) {
			await this.fetchRoomUrl()
			if (this.server) this.joined = true
		} else if (!this.module.config?.waiting_room_enabled) {
			// Pre-fetch the room URL in the background while the user is on
			// the prejoin screen, so join is instant when they click.
			this.fetchRoomUrl()
		}
	},
	mounted() {
		this.apiMessageHandler = this.onApiMessage.bind(this)
		api.on('message', this.apiMessageHandler)
	},
	unmounted() {
		if (this.apiMessageHandler) {
			api.off('message', this.apiMessageHandler)
			this.apiMessageHandler = null
		}
	},
	methods: {
		onApiMessage(message) {
			const [name, payload] = message
			if (name !== 'januscall.admission_result') return
			if (String(payload?.room) !== String(this.room.id)) return
			if (payload.status === 'admitted' && payload.session) {
				this.applyRoomUrl(payload.session)
				this.waitingForAdmission = false
				this.denied = false
				this.left = false
				this.joined = true
			} else if (payload.status === 'denied') {
				this.clearRoomUrl()
				this.waitingForAdmission = false
				this.joined = false
				this.denied = true
			}
		},
		applyRoomUrl({ server, roomId, token, sessionId, audioSessionId, videoSessionId, screenShareSessionId, iceServers, isModerator }) {
			this.roomId = roomId
			this.token = token
			this.iceServers = iceServers
			this.sessionId = sessionId
			this.audioSessionId = audioSessionId
			this.videoSessionId = videoSessionId
			this.screenShareSessionId = screenShareSessionId
			this.isModerator = Boolean(isModerator)
			this.server = server
		},
		async fetchRoomUrl() {
			if (this.roomUrlPromise) return this.roomUrlPromise
			this.loading = true
			this.error = null
			this.roomUrlPromise = api.call('januscall.room_url', { room: this.room.id })
				.then((response) => {
					if (!this.$el || this._isDestroyed) return
					if (response.status === 'pending') {
						this.waitingForAdmission = true
						return
					}
					this.applyRoomUrl(response)
				})
				.catch((error) => {
					this.error = error
					this.loading = false
					console.log(error)
				})
				.finally(() => {
					this.roomUrlPromise = null
				})
			return this.roomUrlPromise
		},
		async onPrejoinComplete({ micMuted }) {
			this.joinedWithMicMuted = micMuted
			this.denied = false
			this.requestingAdmission = true
			if (!this.server) {
				await this.fetchRoomUrl()
			}
			this.requestingAdmission = false
			if (this.error) return
			if (this.waitingForAdmission) return
			this.joined = true
		},
		async cancelWaitingRoom() {
			try {
				await api.call('januscall.waiting_room.cancel', { room: this.room.id })
			} catch (error) {
				console.log(error)
			}
			this.waitingForAdmission = false
			this.requestingAdmission = false
			this.left = true
			this.leftMessage = 'You left the waiting room'
			this.clearRoomUrl()
		},
		returnToPrejoin() {
			this.denied = false
			this.left = false
			this.leftMessage = 'You left the room'
			this.clearRoomUrl()
		},
		onRoomLeft(payload = {}) {
			this.joined = false
			this.left = true
			this.requestingAdmission = false
			this.waitingForAdmission = false
			this.denied = false
			this.leftMessage = payload.message || 'You left the room'
			this.clearRoomUrl()
		},
		rejoinRoom() {
			this.left = false
			this.leftMessage = 'You left the room'
			this.fetchRoomUrl()
		},
		clearRoomUrl() {
			this.server = null
			this.token = null
			this.iceServers = []
			this.roomId = null
			this.sessionId = null
			this.audioSessionId = null
			this.videoSessionId = null
			this.screenShareSessionId = null
			this.isModerator = false
			this.requestingAdmission = false
			this.waitingForAdmission = false
		},
	},
}
</script>
<style lang="stylus">
.c-januscall
	flex: auto
	height: auto // 100% breaks safari
	display: flex
	flex-direction: column
	position: relative
	overflow: hidden

	.left-room,
	.waiting-room,
	.denied-room
		flex: auto
		display: flex
		align-items: center
		justify-content: center
		min-height: 0
		background: #111315
		color: #edf1f5

	.left-room-inner
		display: flex
		flex-direction: column
		align-items: center
		gap: 14px
		padding: 32px
		text-align: center

		h2
			margin: 0
			font-size: 24px
			font-weight: 600

		p
			margin: 0
			color: #9aa6b2
			font-size: 14px

	.left-room-icon
		width: 64px
		height: 64px
		border-radius: 50%
		background: #22282f
		border: 1px solid #343d47
		display: flex
		align-items: center
		justify-content: center
		color: #ffb3b3

		.mdi
			font-size: 30px

	.waiting-room-icon
		width: 64px
		height: 64px
		border-radius: 50%
		background: #22282f
		border: 1px solid #343d47
		display: flex
		align-items: center
		justify-content: center
		color: #a8d7ff

		.mdi
			font-size: 30px

	.left-room-actions
		display: flex
		gap: 12px
		margin-top: 10px

		@media (max-width: 480px)
			flex-direction: column
			width: 100%

	.left-room-button
		height: 42px
		border: 1px solid #343d47
		border-radius: 8px
		background: #22282f
		color: #edf1f5
		cursor: pointer
		display: flex
		align-items: center
		justify-content: center
		gap: 8px
		padding: 0 16px
		font-size: 14px
		font-weight: 600

		&:hover, &:focus-visible
			background: #2a323b
			outline: none

		&:focus-visible
			box-shadow: 0 0 0 3px rgba(47,128,237,0.35)

		&.primary
			background: #2f80ed
			border-color: #2f80ed
			color: #fff

			&:hover, &:focus-visible
				background: #1f6fd1

	&.size-tiny
		height: 48px
		width: 86px // TODO total guesstimate
		pointer-events: none
		.controls, .mdi
			opacity: 0

</style>

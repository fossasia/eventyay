<template lang="pug">
.c-januscall(:class="[`size-${size}`]")
	.error(v-if="error") {{ $t('JanusCall:error:text') }}
	// Pre-join screen
	janus-prejoin(
		v-else-if="!joined && !left && !error",
		:roomName="room.name || 'Meeting Room'",
		@join="onPrejoinComplete"
	)
	.left-room(v-else-if="left && !error")
		.left-room-inner
			.left-room-icon
				.mdi.mdi-phone-hangup
			h2 You left the room
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
			loading: false,
			error: null,
			roomUrlPromise: null,
			// Pre-join state
			joined: false,
			left: false,
			joinedWithMicMuted: true,
		}
	},
	computed: {},
	async created() {
		// In tiny/background mode, skip the prejoin screen and join immediately
		if (this.size === 'tiny' || this.background) {
			await this.fetchRoomUrl()
			this.joined = true
		} else {
			// Pre-fetch the room URL in the background while the user is on
			// the prejoin screen, so join is instant when they click.
			this.fetchRoomUrl()
		}
	},
	methods: {
		async fetchRoomUrl() {
			if (this.roomUrlPromise) return this.roomUrlPromise
			this.loading = true
			this.error = null
			this.roomUrlPromise = api.call('januscall.room_url', { room: this.room.id })
				.then(({ server, roomId, token, sessionId, audioSessionId, videoSessionId, screenShareSessionId, iceServers }) => {
					if (!this.$el || this._isDestroyed) return
					this.roomId = roomId
					this.token = token
					this.iceServers = iceServers
					this.sessionId = sessionId
					this.audioSessionId = audioSessionId
					this.videoSessionId = videoSessionId
					this.screenShareSessionId = screenShareSessionId
					this.server = server
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
			if (!this.server) {
				await this.fetchRoomUrl()
			}
			if (this.error) return
			this.joined = true
		},
		onRoomLeft() {
			this.joined = false
			this.left = true
			this.clearRoomUrl()
		},
		rejoinRoom() {
			this.left = false
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

	.left-room
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

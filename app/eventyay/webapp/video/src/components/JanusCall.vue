<template lang="pug">
.c-januscall(:class="[`size-${size}`]")
	.error(v-if="error") {{ $t('JanusCall:error:text') }}
	// Pre-join screen
	janus-prejoin(
		v-else-if="!joined && !error",
		:roomName="room.name || 'Meeting Room'",
		@join="onPrejoinComplete"
	)
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
		@hangup="roomId = null; $router.push('/')"
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

	&.size-tiny
		height: 48px
		width: 86px // TODO total guesstimate
		pointer-events: none
		.controls, .mdi
			opacity: 0

</style>

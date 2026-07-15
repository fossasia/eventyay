<template lang="pug">
.c-admin-room
	.error(v-if="error")
		span We could not fetch the current configuration.
		span(v-if="errorCode")  ({{ errorCode }})
		span(v-if="errorCode === 'protocol.denied'")  You likely lack admin permissions.
	template(v-else-if="config")
		template(v-if="!inferredType")
			.ui-page-header
				bunt-icon-button(@click="$router.push({name: 'admin:rooms:index'})") arrow_left
				h1 Mystery Room
			.mystery-room
				p Room not instantiated.
				bunt-button(@click="showRoomEditPrompt = true") Initiate room
		template(v-else)
			.ui-page-header
				bunt-icon-button(@click="$router.push({name: 'admin:rooms:index'})") arrow_left
				h1 {{ inferredType ? inferredType.name : 'Mystery Room' }} :
					span.room-name(v-html="$emojify(config.name)")
				.actions
					bunt-button(v-if="hasPermission('room:update')", @click="showRoomEditPrompt = true") Edit
			edit-form(:config="config")
	bunt-progress-circular(v-else, size="huge")
	transition(name="prompt")
		RoomEditPrompt(
			v-if="showRoomEditPrompt && config",
			:room="{id: config.id}",
			@close="closeRoomEditPrompt",
			@deleted="roomDeleted"
		)
</template>
<script>
import { mapGetters } from 'vuex'
import api from 'lib/api'
import RoomEditPrompt from 'components/RoomEditPrompt'
import { inferType } from 'lib/room-types'
import EditForm from './EditForm'

export default {
	name: 'AdminRoom',
	components: { EditForm, RoomEditPrompt },
	props: {
		roomId: String
	},
	data() {
		return {
			error: null,
			errorCode: null,
			config: null,
			showRoomEditPrompt: false,
			_unwatchConnected: null
		}
	},
	computed: {
		...mapGetters(['hasPermission']),
		inferredType() {
			return inferType(this.config)
		}
	},
	async created() {
		await this.ensureConnectedAndFetch()
	},
	beforeUnmount() {
		if (this._unwatchConnected) this._unwatchConnected()
	},
	methods: {
		async ensureConnectedAndFetch() {
			if (this.$store.state.connected) return this.fetchConfig()
			// wait until websocket joined before calling
			this._unwatchConnected = this.$store.watch(
				state => state.connected,
				(connected) => {
					if (connected) {
						if (this._unwatchConnected) this._unwatchConnected()
						this._unwatchConnected = null
						this.fetchConfig()
					}
				}
			)
		},
		async fetchConfig() {
			try {
				this.error = null
				this.errorCode = null
				this.config = await api.call('room.config.get', {room: this.roomId})
			} catch (error) {
				this.error = error
				this.errorCode = error?.code || error?.message || String(error)
				console.error(error)
			}
		},
		closeRoomEditPrompt() {
			this.showRoomEditPrompt = false
			this.fetchConfig()
		},
		roomDeleted() {
			this.$router.replace({name: 'admin:rooms:index'})
		}
	}
}
</script>
<style lang="stylus">
.c-admin-room
	display: flex
	flex-direction: column
	background: $clr-white
	min-height: 0
	min-width: 0
	.bunt-icon-button
		icon-button-style(style: clear)
	.ui-page-header
		background-color: $clr-grey-100
		.bunt-icon-button
			margin-right: 8px
		h1
			flex: auto
			font-size: 24px
			font-weight: 500
			margin: 1px 16px 0 0
			ellipsis()
			.room-name
				margin-left: 8px
				font-size: 24px
				line-height: 56px
				font-weight: 600
				// TODO decopypaste
				.emoji
					display: inline-block
					vertical-align: middle
					width: 36px
					height: @width
					&.needs-space
						margin-right: 8px
		.actions
			display: flex
			flex: none
			.bunt-button:not(:last-child)
				margin-right: 16px
	.mystery-room
		flex: auto
		display: flex
		flex-direction: column
		justify-content: center
		align-items: center
		gap: 12px
		padding: 24px
		p
			margin: 0
			font-size: 16px
			color: $clr-secondary-text-light
</style>

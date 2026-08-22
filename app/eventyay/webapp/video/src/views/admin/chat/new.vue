<template lang="pug">
.c-admin-chat-new
	.ui-page-header
		bunt-icon-button(@click="type ? $router.replace({name: 'admin:chat:new'}) : $router.replace({name: 'admin:chat:index'})") arrow_left
		h1 New channel
			template(v-if="chosenType")  : {{ chosenType.name }}
	.error(v-if="connected && !canCreate")
		span You do not have permission to create chat or video chat channels.
	.choose-type(v-else-if="!type", v-scrollbar.y="")
		h2 Choose a channel type
		.types
			router-link.type(v-for="channelType of CHANNEL_TYPES", :key="channelType.id", :to="{name: 'admin:chat:new', params: {type: channelType.id}}")
				.icon.mdi(:class="[`mdi-${channelType.icon}`]")
				.text
					.name {{ channelType.name }}
					.description {{ channelType.description }}
	edit-form(v-else-if="config", :config="config", :creating="true")
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import { mapGetters, mapState } from 'vuex'
import ROOM_TYPES, { chatCreationTypes } from 'lib/room-types'
import { filterRoomTypesByPermission, isBbbConfigured } from 'lib/room-type-permissions'
import EditForm from 'views/admin/rooms/EditForm'

export default {
	components: { EditForm },
	data() {
		return {
			allRoomTypes: ROOM_TYPES,
			type: null,
			config: null
		}
	},
	computed: {
		...mapState(['connected']),
		...mapGetters(['hasPermission', 'isAdminMode']),
		CHANNEL_TYPES() {
			return filterRoomTypesByPermission(
				chatCreationTypes(this.allRoomTypes),
				this.hasPermission,
				this.isAdminMode,
				{bbbAvailable: isBbbConfigured(this.$store.state.world)}
			)
		},
		canCreate() {
			return this.CHANNEL_TYPES.length > 0
		},
		chosenType() {
			return this.CHANNEL_TYPES.find(t => t.id === this.type)
		}
	},
	watch: {
		$route: 'updateType',
		connected: 'updateType',
		CHANNEL_TYPES: 'updateType'
	},
	created() {
		this.updateType()
	},
	methods: {
		getStartingModuleConfig(type) {
			if (type.id === 'channel-video-chat') {
				return {video_chat: true}
			}
			return {}
		},
		updateType() {
			this.type = this.$route.params.type
			if (!this.connected || !this.canCreate) return
			if (!this.type) {
				if (this.CHANNEL_TYPES.length === 1) {
					this.$router.replace({name: 'admin:chat:new', params: {type: this.CHANNEL_TYPES[0].id}})
				}
				return
			}
			if (!this.chosenType) {
				this.$router.replace({name: 'admin:chat:new'})
				return
			}
			const startingModule = this.chosenType.startingModule
			if (this.config?.module_config?.[0]?.type === startingModule) return
			this.config = {
				name: '',
				description: '',
				sorting_priority: '',
				pretalx_id: '',
				force_join: false,
				module_config: [{type: startingModule, config: this.getStartingModuleConfig(this.chosenType)}],
			}
		}
	}
}
</script>
<style lang="stylus">
.c-admin-chat-new
	background-color: $clr-white
	display: flex
	flex-direction: column
	min-height: 0
	height: 100%
	.bunt-icon-button
		icon-button-style(style: clear)
	.ui-page-header
		background-color: $clr-grey-100
		.bunt-icon-button
			margin-right: 8px
	h1
		font-size: 24px
		font-weight: 500
	.error
		padding: 24px 16px
		color: $clr-secondary-text-light
	.choose-type
		display: flex
		flex-direction: column
		height: 89vh
		> *
			margin: 16px
		h2
			margin: 16px 16px 0px
	.types
		display: flex
		flex-direction: column
		border: border-separator()
		border-radius: 4px
		max-width: 480px
		.type
			display: flex
			min-height: 52px
			flex: none
			cursor: pointer
			padding: 0 16px 0 8px
			box-sizing: border-box
			font-size: 16px
			align-items: center
			color: $clr-primary-text-light
			&:not(:last-child)
				border-bottom: border-separator()
			&:hover
				background-color: $clr-grey-50
			.icon
				font-size: 30px
				line-height: 52px
				margin: 0 8px 0 0
			.text
				display: flex
				flex-direction: column
				padding: 5px 0
			.name
				line-height: 24px
			.description
				color: $clr-secondary-text-light
				font-size: 13px
</style>

<template lang="pug">
.c-admin-chat-new
	.ui-page-header
		bunt-icon-button(@click="$router.replace({name: 'admin:chat:index'})") arrow_left
		h1 New chat channel
	.error(v-if="!canCreate")
		span You do not have permission to create chat channels.
	edit-form(v-else-if="config", :config="config", :creating="true")
</template>
<script>
import { mapGetters } from 'vuex'
import ROOM_TYPES, { chatCreationTypes } from 'lib/room-types'
import { isRoomTypeAvailable } from 'lib/room-type-permissions'
import EditForm from 'views/admin/rooms/EditForm'

export default {
	components: { EditForm },
	data() {
		return {
			config: null
		}
	},
	computed: {
		...mapGetters(['hasPermission', 'isAdminMode']),
		canCreate() {
			return isRoomTypeAvailable('channel-text', this.hasPermission, this.isAdminMode)
		},
		chatType() {
			return chatCreationTypes(ROOM_TYPES)[0]
		}
	},
	created() {
		if (!this.canCreate || !this.chatType) return
		this.config = {
			name: '',
			description: '',
			sorting_priority: '',
			pretalx_id: '',
			force_join: false,
			module_config: [{type: this.chatType.startingModule, config: {}}],
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
</style>

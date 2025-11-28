<template lang="pug">
.c-admin-rooms-new
	.ui-page-header
		bunt-icon-button(@click="type ? $router.replace({name: 'admin:rooms:new'}) : $router.replace({name: 'admin:rooms:index'})") arrow_left
		h1 New room
			template(v-if="chosenType")  : {{ chosenType.name }}
	.choose-type(v-if="!type", v-scrollbar.y="")
		h2 Choose a room type
		.types
			router-link.type(v-for="type of ROOM_TYPES", :to="{name: 'admin:rooms:new', params: {type: type.id}}")
				.icon.mdi(:class="[`mdi-${type.icon}`]")
				.text
					.name {{ type.name }}
					.description {{ type.description }}
	edit-form(v-else, :config="config", :creating="true")
</template>
<script>
import { mapGetters } from 'vuex'
import ROOM_TYPES from 'lib/room-types'
import EditForm from './EditForm'

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
		...mapGetters(['hasPermission']),
		ROOM_TYPES() {
			// Filter room types based on permissions
			return this.allRoomTypes.filter(type => {
				// Stage requires world:rooms.create.stage permission
				if (type.id === 'stage') {
					return this.hasPermission('world:rooms.create.stage')
				}
				// Channel types (BBB, Janus, Zoom) require world:rooms.create.bbb permission
				if (type.id === 'channel-bbb' || type.id === 'channel-janus' || type.id === 'channel-zoom') {
					return this.hasPermission('world:rooms.create.bbb')
				}
				// Text channel requires world:rooms.create.chat permission
				if (type.id === 'channel-text') {
					return this.hasPermission('world:rooms.create.chat')
				}
				// Exhibition requires world:rooms.create.exhibition permission
				if (type.id === 'exhibition') {
					return this.hasPermission('world:rooms.create.exhibition')
				}
				// Poster requires world:rooms.create.poster permission
				if (type.id === 'posters') {
					return this.hasPermission('world:rooms.create.poster')
				}
				// Roulette and page types require room:update permission (general room management)
				if (type.id === 'channel-roulette' || type.id === 'page-static' || type.id === 'page-iframe' || type.id === 'page-landing' || type.id === 'page-userlist') {
					return this.hasPermission('room:update')
				}
				// Other types are always available
				return true
			})
		},
		chosenType() {
			return this.ROOM_TYPES.find(t => t.id === this.type)
		},
	},
	watch: {
		$route: 'updateType'
	},
	created() {
		this.updateType()
	},
	methods: {
		updateType() {
			this.type = this.$route.params.type
			if (!this.type || !this.chosenType) return
			this.config = {
				name: '',
				description: '',
				sorting_priority: '',
				pretalx_id: '',
				force_join: false,
				module_config: [{type: this.chosenType.startingModule, config: {}}],
			}
		}
	}
}
</script>
<style lang="stylus">
.c-admin-rooms-new
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

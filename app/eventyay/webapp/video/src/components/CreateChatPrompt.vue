<template lang="pug">
prompt.c-create-chat-prompt(@close="$emit('close')")
	.content
		h1 {{ $t('CreateChatPrompt:headline:text') }}
		p {{ $t('CreateChatPrompt:intro:text') }}
		form(@submit.prevent="create")
			.channel-type
				.fieldset-label {{ $t('CreateChatPrompt:type:label') }}
				.ui-radio-options
					label.ui-radio-option(v-for="option in types", :key="option.id")
						input(type="radio", name="type", :value="option.id", v-model="type")
						.radio-copy
							.ui-radio-title
								i.mdi(:class="`mdi-${option.icon}`", style="margin-right: 6px; font-size: 16px; line-height: 1;")
								span {{ option.label }}
			bunt-input.name-input(:class="{ 'has-error': !!error }", name="name", :label="$t('CreateChatPrompt:name:label')", :icon="selectedType ? selectedType.icon : null", :placeholder="$t('CreateChatPrompt:name:placeholder')", v-model="name", :validation="error ? { $error: true, $errors: [{ $message: error }] } : null")
			bunt-input-outline-container(:label="$t('CreateChatPrompt:description:label')")
				template(#default= "{focus, blur}")
					textarea(v-model="description", @focus="focus", @blur="blur")
			bunt-button(type="submit", :loading="loading", :disabled="!!error", :error="!!error") {{ $t('CreateChatPrompt:submit:label') }}
</template>
<script>
import {mapGetters} from 'vuex'
import Prompt from 'components/Prompt'
import ROOM_TYPES from 'lib/room-types'
import { isRoomTypeAvailable } from 'lib/room-type-permissions'

const JITSI_ROOM_TYPE = ROOM_TYPES.find(type => type.id === 'channel-jitsi')
const BBB_ROOM_TYPE = ROOM_TYPES.find(type => type.id === 'channel-bbb')

export default {
	components: { Prompt },
	emits: ['close'],
	data() {
		return {
			name: '',
			description: '',
			type: 'text',
			loading: false,
			error: null
		}
	},
	computed: {
		...mapGetters(['hasPermission', 'isAdminMode']),
		types() {
			const types = []
			if (this.hasPermission('world:rooms.create.chat')) {
				types.push({
					id: 'text',
					roomTypeId: 'channel-text',
					label: this.$t('CreateChatPrompt:type.text:label'),
					icon: 'pound',
					moduleType: 'chat.native',
					permission: 'world:rooms.create.chat'
				})
			}
			if (BBB_ROOM_TYPE && isRoomTypeAvailable(BBB_ROOM_TYPE.id, this.hasPermission, this.isAdminMode)) {
				types.push({
					id: 'video',
					roomTypeId: BBB_ROOM_TYPE.id,
					label: this.$t('CreateChatPrompt:type.video:label'),
					icon: 'webcam',
					moduleType: BBB_ROOM_TYPE.startingModule,
					permission: 'world:rooms.create.bbb'
				})
			}
			if (JITSI_ROOM_TYPE && isRoomTypeAvailable(JITSI_ROOM_TYPE.id, this.hasPermission, this.isAdminMode)) {
				types.push({
					id: 'jitsi',
					roomTypeId: JITSI_ROOM_TYPE.id,
					label: JITSI_ROOM_TYPE.name,
					icon: JITSI_ROOM_TYPE.icon,
					moduleType: JITSI_ROOM_TYPE.startingModule,
					permission: 'world:rooms.create.jitsi'
				})
			}
			return types
		},
		selectedType() {
			return this.types.find(type => type.id === this.type)
		}
	},
	watch: {
		name() {
			this.error = null
		},
		types: {
			immediate: true,
			handler(types) {
				// If no types available, reset to null
				if (types.length === 0) {
					this.type = null
				} else if (!types.find(t => t.id === this.type)) {
					// If current type is not available, select first available
					this.type = types[0].id
				}
			}
		}
	},
	methods: {
		async create() {
			this.error = null
			// Check if any types are available
			if (this.types.length === 0) {
				this.error = this.$t('CreateChatPrompt:error:no-permission') || 'You do not have permission to create channels.'
				return
			}
			if (!this.selectedType) {
				return
			}

			// Verify permission for selected type
			if (!isRoomTypeAvailable(this.selectedType.roomTypeId, this.hasPermission, this.isAdminMode)) {
				this.error = this.$t('CreateChatPrompt:error:no-permission') || 'You do not have permission to create channels.'
				return
			}

			this.loading = true
			const modules = [{ type: this.selectedType.moduleType }]
			let room
			try {
				({ room } = await this.$store.dispatch('createRoom', {
					name: this.name,
					description: this.description,
					modules
				}))
				this.loading = false
				this.$router.push({name: 'room', params: {roomId: room}})
				this.$emit('close')
			} catch (error) {
				this.loading = false
				this.error = String(error.message || error).replace(/^\[['"]|['"]\]$/g, '')
			}
		}
	}
}
</script>
<style lang="stylus">
.c-create-chat-prompt
	.content
		display: flex
		flex-direction: column
		padding: 32px
		position: relative
		#btn-close
			icon-button-style(style: clear)
			position: absolute
			top: 8px
			right: 8px
		h1
			margin: 0
			text-align: center
		p
			max-width: 320px
		form
			display: flex
			flex-direction: column
			align-self: stretch
			.bunt-button
				themed-button-primary()
				margin-top: 16px
			.channel-type
				margin-top: 8px
				margin-bottom: 16px
				.fieldset-label
					font-size: 12px
					font-weight: 500
					color: $clr-secondary-text-light
					margin-bottom: 8px
			.name-input
				&.has-error
					margin-bottom: 24px
			.bunt-input-outline-container
				textarea
					background-color: transparent
					border: none
					outline: none
					resize: vertical
					min-height: 64px
					padding: 0 8px
</style>

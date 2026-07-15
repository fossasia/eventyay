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
		...mapGetters(['hasPermission']),
		types() {
			const types = []
			if (this.hasPermission('world:rooms.create.chat')) {
				types.push({
					id: 'text',
					label: this.$t('CreateChatPrompt:type.text:label'),
					icon: 'pound'
				})
			}
			if (this.hasPermission('world:rooms.create.bbb')) {
				types.push({
					id: 'video',
					label: this.$t('CreateChatPrompt:type.video:label'),
					icon: 'webcam'
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

			// Verify permission for selected type
			if (this.type === 'text' && !this.hasPermission('world:rooms.create.chat')) {
				this.error = this.$t('CreateChatPrompt:error:no-text-permission') || 'You do not have permission to create text channels.'
				return
			}
			if (this.type === 'video' && !this.hasPermission('world:rooms.create.bbb')) {
				this.error = this.$t('CreateChatPrompt:error:no-video-permission') || 'You do not have permission to create video channels.'
				return
			}

			this.loading = true
			const modules = []
			if (this.type === 'text') {
				modules.push({
					type: 'chat.native'
				})
			} else {
				modules.push({
					type: 'call.bigbluebutton'
				})
			}
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

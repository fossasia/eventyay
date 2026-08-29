<template lang="pug">
prompt.c-create-chat-prompt(@close="$emit('close')")
	.content
		h1 {{ $t('Create a new channel') }}
		p {{ $t("Create a new place to discuss a topic you'd like to talk about.") }}
		form(@submit.prevent="create")
			bunt-input.name-input(:class="{ 'has-error': !!error }", name="name", :label="$t('Name')", icon="pound", :placeholder="$t('Channel name')", v-model="name", :validation="error ? { $error: true, $errors: [{ $message: error }] } : null")
			bunt-input-outline-container(:label="$t('Description')")
				template(#default= "{focus, blur}")
					textarea(v-model="description", @focus="focus", @blur="blur")
			bunt-button(type="submit", :loading="loading", :disabled="!!error", :error="!!error") {{ $t('Create') }}
</template>
<script>
import Prompt from 'components/Prompt'
import { mapGetters } from 'vuex'

export default {
	components: { Prompt },
	emits: ['close'],
	data() {
		return {
			name: '',
			description: '',
			loading: false,
			error: null
		}
	},
	computed: {
		...mapGetters(['hasPermission'])
	},
	watch: {
		name() {
			this.error = null
		}
	},
	methods: {
		async create() {
			this.error = null
			if (!this.hasPermission('world:rooms.create.chat')) {
				this.error = this.$t('You do not have permission to create channels.')
				return
			}

			this.loading = true
			try {
				const { room } = await this.$store.dispatch('createRoom', {
					name: this.name,
					description: this.description,
					modules: [{ type: 'chat.native' }]
				})
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

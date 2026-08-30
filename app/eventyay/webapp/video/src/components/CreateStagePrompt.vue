<template lang="pug">
prompt.c-create-stage-prompt(@close="$emit('close')")
	.content
		h1 {{ $t('Create a new stage') }}
		form(@submit.prevent="create")
			bunt-input(name="name", :label="$t('Name')", icon="theater", :placeholder="$t('Stage name')", v-model="name", :validation="v$.name")
			bunt-input-outline-container(:label="$t('Description')")
				template(#default="{focus, blur}")
					textarea(v-model="description", @focus="focus", @blur="blur")
			bunt-button(type="submit", :loading="loading", :error-message="error") {{ $t('Create') }}
</template>
<script>
import { useVuelidate } from '@vuelidate/core'
import { mapGetters } from 'vuex'
import Prompt from 'components/Prompt'
import { required } from 'lib/validators'
import { PLAYBACK_MODE_ALWAYS_ON } from 'lib/stage-streams'

export default {
	name: 'CreateStagePrompt',
	components: { Prompt },
	emits: ['close'],
	setup: () => ({ v$: useVuelidate() }),
	data() {
		return {
			name: '',
			description: '',
			loading: false,
			error: null,
		}
	},
	computed: {
		...mapGetters(['hasPermission']),
	},
	validations() {
		return {
			name: {
				required: required(this.$t('Name is required'))
			}
		}
	},
	methods: {
		async create() {
			this.error = null
			this.v$.$touch()
			if (this.v$.$invalid) return

			if (!this.hasPermission('world:rooms.create.stage')) {
				this.error = this.$t('You do not have permission to create stages.')
				return
			}

			this.loading = true
			const modules = [
				{
					type: 'chat.native',
					config: {
						volatile: true,
					}
				},
				{
					type: 'livestream.youtube',
					config: {
						playback_mode: PLAYBACK_MODE_ALWAYS_ON,
						ytid: '',
					}
				}
			]
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
				this.error = error.message || error
			}
		}
	}
}
</script>
<style lang="stylus">
.c-create-stage-prompt
	.content
		display: flex
		flex-direction: column
		padding: 32px
		position: relative
		h1
			margin: 0 0 16px 0
			text-align: center
			font-size: 20px
			font-weight: 600
		form
			display: flex
			flex-direction: column
			align-self: stretch
			gap: 16px
			.bunt-input-outline-container
				textarea
					background-color: transparent
					border: none
					outline: none
					resize: vertical
					min-height: 64px
					padding: 0 8px
					font-family: inherit
					font-size: 14px
			.bunt-button
				themed-button-primary()
				margin-top: 8px
</style>

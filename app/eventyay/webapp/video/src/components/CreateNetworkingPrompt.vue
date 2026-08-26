<template lang="pug">
prompt.c-create-networking-prompt(@close="$emit('close')")
	.content
		h1 {{ $t('Create random video calls') }}
		form(@submit.prevent="create")
			bunt-input(name="name", :label="$t('Name')", icon="webcam", :placeholder="$t('random video calls')", v-model="name", :validation="v$.name")
			bunt-input-outline-container(:label="$t('Description')")
				template(#default="{focus, blur}")
					textarea(v-model="description", @focus="focus", @blur="blur")
			bunt-input(name="rematchInterval", :label="$t('Rematch interval (minutes)')", icon="timer-outline", v-model="rematchInterval", :validation="v$.rematchInterval")
			bunt-button(type="submit", :loading="loading", :error-message="error") {{ $t('Create') }}
</template>
<script>
import { useVuelidate } from '@vuelidate/core'
import { mapGetters } from 'vuex'
import api from 'lib/api'
import Prompt from 'components/Prompt'
import { integer, minValue, required } from 'lib/validators'
import { isRoomTypeAvailable } from 'lib/room-type-permissions'

export default {
	components: { Prompt },
	emits: ['close'],
	setup: () => ({ v$: useVuelidate() }),
	data() {
		return {
			name: '',
			description: '',
			rematchInterval: 1440,
			loading: false,
			error: null
		}
	},
	computed: {
		...mapGetters(['hasPermission'])
	},
	validations() {
		return {
			name: {
				required: required(this.$t('Name is required'))
			},
			rematchInterval: {
				required: required(this.$t('Minimum time is required')),
				integer: integer(this.$t('must be a whole number')),
				minValue: minValue(1, this.$t('must be at least 1'))
			}
		}
	},
	methods: {
		async create() {
			this.error = null
			this.v$.$touch()
			if (this.v$.$invalid) return

			if (!isRoomTypeAvailable('channel-roulette', this.hasPermission)) {
				this.error = this.$t('You do not have permission to create random video calls.')
				return
			}

			this.loading = true
			try {
				const { room } = await this.$store.dispatch('createRoom', {
					name: this.name,
					description: this.description,
					modules: []
				})
				await api.call('room.config.patch', {
					room,
					name: this.name,
					description: this.description,
					module_config: [{
						type: 'networking.roulette',
						config: {
							rematch_interval: Number(this.rematchInterval)
						}
					}]
				})
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
.c-create-networking-prompt
	.prompt-wrapper
		width: 420px
		max-width: calc(100vw - 32px)
	.content
		display: flex
		flex-direction: column
		padding: 32px
		position: relative
		box-sizing: border-box
		min-width: 0
		h1
			margin: 0
			text-align: center
			font-size: 24px
			line-height: 1.25
		form
			display: flex
			flex-direction: column
			align-self: stretch
			min-width: 0
			.bunt-input
				min-width: 0
			.bunt-input-outline-container
				margin-top: 16px
				min-width: 0
				textarea
					background-color: transparent
					border: none
					outline: none
					resize: vertical
					min-height: 64px
					padding: 0 8px
					box-sizing: border-box
					width: 100%
			.bunt-button
				themed-button-primary()
				margin-top: 16px
</style>

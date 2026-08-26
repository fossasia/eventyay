<template lang="pug">
prompt.c-create-room-prompt(@close="$emit('close')")
	.content
		h1 {{ $t('Create a new room') }}
		form(@submit.prevent="create")
			bunt-input(name="name", :label="$t('Name')", :placeholder="$t('Room name')", v-model="name", :validation="v$.name")
			bunt-button(type="submit", :loading="loading", :error-message="error") {{ $t('Create') }}
</template>
<script>
import {useVuelidate} from '@vuelidate/core'
import Prompt from 'components/Prompt'
import { required } from 'lib/validators'

export default {
	components: { Prompt },
	emits: ['close'],
	setup:() => ({v$:useVuelidate()}),
	data() {
		return {
			name: '',
			url: '',
			description: '',
			loading: false,
			error: null
		}
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

			this.loading = true
			let room
			try {
				({ room } = await this.$store.dispatch('createRoom', {
					name: this.name,
					description: this.description,
					modules: []
				}))
				this.loading = false
				this.$router.push({name: 'admin:rooms:item', params: {roomId: room}})
				this.$emit('close')
			} catch (error) {
				console.log(error)
				this.loading = false
				this.error = error.message || error
			}
		}
	}
}
</script>
<style lang="stylus">
.c-create-room-prompt
	.content
		display: flex
		flex-direction: column
		padding: 32px
		position: relative
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
</style>

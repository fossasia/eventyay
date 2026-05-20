<template lang="pug">
prompt.c-error-dialog(@close="allowCancel && closeDialog()", :allow-cancel="allowCancel")
	.content
		.header
			.mdi.mdi-alert-circle-outline
			h2 {{ title }}
		.message {{ message }}
		.actions
			bunt-button.btn-action(@click="closeDialog()")
				| {{ buttonText }}
</template>

<script setup>
import Prompt from 'components/Prompt'

defineProps({
	title: {
		type: String,
		default: 'Error'
	},
	message: {
		type: String,
		required: true
	},
	buttonText: {
		type: String,
		default: 'OK'
	},
	allowCancel: {
		type: Boolean,
		default: false
	}
})

const emit = defineEmits(['close'])

const closeDialog = () => {
	emit('close')
}
</script>

<style lang="stylus">
.c-error-dialog
	.content
		display: flex
		flex-direction: column
		padding: 16px
		max-width: 500px
		
		.header
			display: flex
			align-items: center
			gap: 12px
			margin: 8px 0 12px 0
			
			.mdi
				font-size: 24px
				color: $clr-danger
				flex-shrink: 0
				
			h2
				margin: 0
				font-size: 18px
				font-weight: 600
				color: $clr-text
		
		.message
			font-size: 14px
			color: $clr-text-secondary
			margin: 0 0 16px 0
			line-height: 1.5
		
		.actions
			align-self: flex-end
			display: flex
			
			.btn-action
				button-style(color: $clr-danger)
</style>

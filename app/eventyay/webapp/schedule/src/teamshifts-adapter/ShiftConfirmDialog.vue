<template lang="pug">
dialog.pretalx-modal.shift-confirm-modal(ref="modal", @click="onBackdrop", @cancel.prevent="cancel")
	.dialog-inner(@click.stop="")
		button.close-button(type="button", aria-label="Close dialog", @click="cancel") ✕
		h3 {{ title }}
		p.shift-confirm-lead {{ lead }}
		dl.shift-confirm-facts(v-if="details.length")
			div(v-for="row in details", :key="row.label")
				dt {{ row.label }}
				dd {{ row.value }}
		p.shift-confirm-error(v-if="error") {{ error }}
		.shift-confirm-actions
			button.btn.btn-sm.btn-default(type="button", :disabled="busy", @click="cancel") {{ $t('Cancel') }}
			button.btn.btn-sm(:class="confirmClass", type="button", :disabled="busy", @click="$emit('confirm')") {{ confirmLabel }}
</template>

<script>
export default {
	name: 'ShiftConfirmDialog',
	emits: ['confirm', 'cancel'],
	props: {
		title: { type: String, default: 'Please confirm' },
		lead: { type: String, default: '' },
		details: { type: Array, default: () => [] },
		confirmLabel: { type: String, default: 'Confirm' },
		confirmClass: { type: String, default: 'btn-primary' },
		error: { type: String, default: '' },
		busy: { type: Boolean, default: false },
	},
	methods: {
		show () {
			this.$refs.modal?.showModal?.()
		},
		close () {
			if (this.$refs.modal?.open) this.$refs.modal.close()
		},
		cancel () {
			this.close()
			this.$emit('cancel')
		},
		onBackdrop (event) {
			if (event.target === this.$refs.modal) this.cancel()
		},
	},
}
</script>

<style lang="stylus">
.shift-confirm-modal
	max-width: 440px
	.shift-confirm-lead
		margin: 8px 0 16px
		color: $clr-grey-700
		line-height: 1.4
	.shift-confirm-facts
		margin: 0 0 16px
		display: grid
		gap: 8px
		div
			display: grid
			grid-template-columns: 120px 1fr
			gap: 8px
			font-size: 14px
		dt
			color: $clr-grey-600
			font-weight: 600
		dd
			margin: 0
			color: $clr-grey-900
	.shift-confirm-error
		color: #d9534f
		margin: 0 0 12px
	.shift-confirm-actions
		display: flex
		justify-content: flex-end
		gap: 8px
		.btn
			display: inline-block
			padding: 6px 12px
			font-size: 14px
			line-height: 1.4
			border-radius: 4px
			border: 1px solid transparent
			cursor: pointer
			&:disabled
				opacity: 0.65
				cursor: default
		.btn-default
			background: #fff
			border-color: #ccc
			color: #333
		.btn-primary
			background: #2185d0
			border-color: #2185d0
			color: #fff
		.btn-danger
			background: #d9534f
			border-color: #d9534f
			color: #fff
</style>

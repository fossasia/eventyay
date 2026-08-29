<template lang="pug">
.c-emoji-picker(ref="container")
	teleport(to="body")
		.emoji-picker-hover-tooltip(
			v-if="tooltip.text",
			:style="tooltip.style",
			role="tooltip"
		) {{ tooltip.text }}
</template>
<script>
import data from '@emoji-mart/data'
import { init, Picker } from 'emoji-mart'

let dataInitialized = false

export default {
	emits: ['selected'],
	data() {
		return {
			tooltip: {
				text: '',
				style: {},
			},
			picker: null,
		}
	},
	async mounted() {
		try {
			if (!dataInitialized) {
				await init({ data })
				dataInitialized = true
			}
			if (!this.$refs.container) return
			const picker = new Picker({
				data,
				onEmojiSelect: (emoji) => {
					this.hideTooltip()
					this.$emit('selected', emoji)
				},
				previewPosition: 'none',
				theme: 'auto',
			})
			this.picker = picker
			this.$refs.container.appendChild(picker)
			picker.addEventListener('pointerover', this.onPickerPointerOver)
			picker.addEventListener('pointerleave', this.hideTooltip)
		} catch (error) {
			console.error('Failed to initialize emoji picker', error)
		}
	},
	beforeUnmount() {
		if (!this.picker) return
		this.picker.removeEventListener('pointerover', this.onPickerPointerOver)
		this.picker.removeEventListener('pointerleave', this.hideTooltip)
	},
	methods: {
		onPickerPointerOver(event) {
			const path = typeof event.composedPath === 'function' ? event.composedPath() : []
			const button = path.find(node => node instanceof HTMLButtonElement)
			if (!button) {
				this.hideTooltip()
				return
			}
			const label = button.getAttribute('aria-label')
			if (!label) {
				this.hideTooltip()
				return
			}
			const rect = button.getBoundingClientRect()
			this.tooltip = {
				text: label,
				style: {
					left: `${rect.left + rect.width / 2}px`,
					top: `${rect.top}px`,
				},
			}
		},
		hideTooltip() {
			if (!this.tooltip.text) return
			this.tooltip = { text: '', style: {} }
		},
	},
}
</script>
<style lang="stylus">
.c-emoji-picker
	position: fixed
	z-index: 901
	em-emoji-picker
		--border-radius: 8px
		--font-family: inherit
		--rgb-background: 255, 255, 255
		--rgb-color: 51, 51, 51
		--rgb-input: 238, 238, 238

.emoji-picker-hover-tooltip
	position: fixed
	z-index: 910
	transform: translate(-50%, calc(-100% - 8px))
	padding: 4px 8px
	border-radius: 4px
	background-color: $clr-blue-grey-900
	color: $clr-primary-text-dark
	font-size: 12px
	line-height: 16px
	white-space: nowrap
	pointer-events: none
	box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18)
</style>

<template lang="pug">
.c-emoji-picker(ref="container")
</template>
<script>
import data from '@emoji-mart/data'
import { Picker } from 'emoji-mart'

export default {
	emits: ['selected'],
	mounted() {
		const container = this.$refs.container
		const picker = new Picker({
			data,
			onEmojiSelect: (emoji) => {
				this.$emit('selected', emoji)
			},
			theme: 'light',
			previewPosition: 'none',
			skinTonePosition: 'none'
		})
		if (picker) {
			container.appendChild(picker)
		}
	},
	methods: {}
}
</script>
<style lang="stylus">
.c-emoji-picker
	.emoji-mart-emoji
		-webkit-tap-highlight-color: transparent
		outline: none
		&:focus-visible
			outline: 2px solid var(--focus-color, $clr-primary)
			outline-offset: 2px
		span
			image-rendering: -webkit-optimize-contrast
</style>

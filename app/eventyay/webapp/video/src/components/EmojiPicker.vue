<template lang="pug">
.c-emoji-picker(ref="container")
</template>
<script>
import data from '@emoji-mart/data'
import { init, Picker } from 'emoji-mart'

let dataInitialized = false

export default {
	emits: ['selected'],
	async mounted() {
		if (!dataInitialized) {
			await init({ data })
			dataInitialized = true
		}
		const picker = new Picker({
			data,
			onEmojiSelect: (emoji) => {
				this.$emit('selected', emoji)
			},
			previewPosition: 'bottom',
			theme: 'auto',
		})
		this.$refs.container.appendChild(picker)
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
</style>

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
	em-emoji-picker
		--border-radius: 8px
		--font-family: inherit
		--rgb-background: var(--clr-background, #fff)
		--rgb-color: var(--clr-primary-text, #333)
		--rgb-input: var(--clr-grey-200, #eee)
</style>

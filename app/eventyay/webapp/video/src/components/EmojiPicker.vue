<template lang="pug">
.c-emoji-picker
</template>
<script>
import { h, render } from 'preact'
import 'emoji-mart/css/emoji-mart.css'
import data from 'emoji-mart/data/twitter.json'
import { NimblePicker } from 'emoji-mart'

export default {
	emits: ['selected'],
	mounted() {
		const picker = h(NimblePicker, {
			set: 'twitter',
			data,
			onSelect: this.$emit.bind(this, 'selected'),
			title: 'Emoji',
			showPreview: true
		})
		render(picker, this.$el)
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
	.emoji-mart-preview-data
		overflow: hidden
		text-overflow: ellipsis
		white-space: nowrap
		font-size: 0.5em
</style>

<template lang="pug">
.c-markdown-content(v-if="markdown", v-html="rendered")
</template>
<script>
import { renderEventyayRichText } from '../utils/eventyayRichText'

export default {
	name: 'MarkdownContent',
	props: {
		markdown: {
			type: String,
			default: ''
		}
	},
	computed: {
		rendered () {
			return renderEventyayRichText(this.markdown)
		}
	}
}
</script>
<style lang="stylus">
.c-markdown-content
	font-size: 16px
	line-height: 1.45
	p
		font-size: inherit
		margin: 0.5em 0
		&:first-child
			margin-top: 0
		&:last-child
			margin-bottom: 0
	a
		color: var(--pretalx-clr-primary, #3aa57c)
	table
		border-collapse: collapse
		width: 100%
		margin: 0.5em 0
		font-size: 0.95em
	th, td
		border: 1px solid var(--color-border, #ddd)
		padding: 0.35em 0.5em
	pre
		overflow-x: auto
		margin: 0.5em 0
		padding: 0.5em 0.75em
		background: var(--color-bg-secondary, #f5f5f5)
		border-radius: 4px
		font-size: 0.9em
	code
		font-size: 0.9em
	blockquote
		margin: 0.5em 0
		padding-left: 0.75em
		border-left: 3px solid var(--color-border, #ccc)
	ul, ol
		margin: 0.5em 0
		padding-left: 1.25em
</style>

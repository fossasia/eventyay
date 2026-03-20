<template lang="pug">
.c-markdown-content(v-if="markdown", v-html="rendered")
</template>
<script>
import MarkdownIt from 'markdown-it'

const markdownIt = MarkdownIt({
	linkify: true,
	breaks: true
})

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
			if (!this.markdown) return ''
			try {
				return markdownIt.render(this.markdown)
			} catch {
				return this.markdown
			}
		}
	}
}
</script>
<style lang="stylus">
.c-markdown-content
	p
		font-size: 16px
	a
		color: var(--pretalx-clr-primary, #3aa57c)
</style>

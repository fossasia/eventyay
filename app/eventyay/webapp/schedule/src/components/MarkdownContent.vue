<template lang="pug">
.c-markdown-content(v-if="markdown", v-html="rendered")
</template>
<script>
import MarkdownIt from 'markdown-it'

const markdownIt = MarkdownIt({
	linkify: true,
	breaks: true
})

const markdownItWithoutLinks = MarkdownIt({
	linkify: false,
	breaks: true
})

markdownItWithoutLinks.renderer.rules.link_open = () => ''
markdownItWithoutLinks.renderer.rules.link_close = () => ''

function escapeHtml(text) {
	return String(text)
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;')
		.replace(/'/g, '&#39;')
}

export default {
	name: 'MarkdownContent',
	props: {
		markdown: {
			type: String,
			default: ''
		},
		disableLinks: {
			type: Boolean,
			default: false
		}
	},
	computed: {
		rendered () {
			if (!this.markdown) return ''
			try {
				const parser = this.disableLinks ? markdownItWithoutLinks : markdownIt
				return parser.render(this.markdown)
			} catch {
				return `<p>${escapeHtml(this.markdown)}</p>`
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

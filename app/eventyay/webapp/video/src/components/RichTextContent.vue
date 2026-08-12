<template lang="pug">
.rich-text-content(v-html="sanitizedContent", @click="handleClick")
</template>
<script>
import DOMPurify from 'dompurify'
import router from 'router'

export default {
	props: {
		// HTML string (Tiptap) or legacy Quill Delta object ({ ops: [...] })
		content: [String, Array, Object],
	},
	computed: {
		sanitizedContent() {
			if (!this.content) return ''

			// Legacy Quill Delta: render ops as plain text fallback
			if (typeof this.content === 'object' && !Array.isArray(this.content) && Array.isArray(this.content?.ops)) {
				const text = this.content.ops
					.filter(op => typeof op.insert === 'string')
					.map(op => op.insert)
					.join('')
				return DOMPurify.sanitize(`<p>${text.replace(/\n/g, '<br>')}</p>`)
			}

			// HTML string from Tiptap
			if (typeof this.content === 'string') {
				return DOMPurify.sanitize(this.content, {
					ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 's', 'a', 'h1', 'h2', 'h3', 'h4', 'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'img'],
					ALLOWED_ATTR: ['href', 'target', 'rel', 'src', 'alt'],
				})
			}

			return ''
		},
	},
	methods: {
		handleClick(event) {
			const a = event.target.closest('a')
			if (!a) return
			// don't redirect with control keys
			if (event.metaKey || event.altKey || event.ctrlKey || event.shiftKey) return
			// don't redirect on right click
			if (event.button !== undefined && event.button !== 0) return
			// don't handle same page links/anchors or external links
			const url = new URL(a.href)
			if (window.location.pathname === url.pathname) return
			if (window.location.hostname !== url.hostname) return
			event.preventDefault()
			router.push(url.pathname + url.hash)
		},
	},
}
</script>
<style lang="stylus">
.rich-text-content
	font-size: 14px
	line-height: 1.6

	> * + *
		margin-top: 0.5em

	p, h1, h2, h3, h4, h5, h6
		margin: 0 16px

	blockquote
		border-left: 3px solid #ccc
		margin: 0 16px 0.5em
		padding-left: 1em
		color: #666

	ul, ol
		padding-left: calc(16px + 1.5em)
		margin: 0 0 0.5em
		max-width: none

	li
		line-height: 1.6
		max-width: none

	ul, ol
		li::before
			content: ""

	img
		margin: 0 auto
		display: block
		max-width: 100%

	a
		&:hover, &[href]:not([class]):hover
			text-decoration: underline

	pre
		margin: 0 16px 0.5em
		background: #f4f4f4
		padding: 8px 12px
		border-radius: 4px
		overflow-x: auto
		font-size: 1.1em
		code
			background: none
			padding: 0

	code
		background: #f4f4f4
		padding: 2px 4px
		border-radius: 3px
		font-size: 0.95em
</style>

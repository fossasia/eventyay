<template lang="pug">
.rich-text-content(v-html="sanitizedContent", @click="handleClick")
</template>
<script>
import DOMPurify from 'dompurify'
import router from 'router'

const RICH_TEXT_ALLOWED_TAGS = [
	'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'strike',
	'ul', 'ol', 'li', 'a', 'blockquote', 'pre', 'code',
	'h1', 'h2', 'h3', 'img',
]
const RICH_TEXT_ALLOWED_ATTR = ['href', 'title', 'target', 'rel', 'src', 'alt', 'class']

function escapeHtml (text) {
	return String(text)
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
}

export default {
	props: {
		content: [String, Array, Object],
	},
	computed: {
		sanitizedContent () {
			if (!this.content) return ''

			// Handle legacy Quill Delta — an array of ops OR { ops: [...] }
			if (typeof this.content === 'object') {
				const ops = Array.isArray(this.content)
					? this.content
					: this.content?.ops
				if (Array.isArray(ops)) {
					// Render as escaped plain text fallback (no formatting)
					const plain = ops
						.map(op => (typeof op.insert === 'string' ? op.insert : ''))
						.join('')
					const escaped = escapeHtml(plain)
					return DOMPurify.sanitize(
						'<p>' + escaped.replace(/\n/g, '<br>') + '</p>',
						{ ALLOWED_TAGS: ['p', 'br'], ALLOWED_ATTR: [] },
					)
				}
				return ''
			}

			// Regular HTML string from Tiptap
			return DOMPurify.sanitize(this.content, {
				ALLOWED_TAGS: RICH_TEXT_ALLOWED_TAGS,
				ALLOWED_ATTR: RICH_TEXT_ALLOWED_ATTR,
			})
		},
	},
	methods: {
		handleClick (event) {
			const a = event.target.closest('a')
			if (!a) return
			// Don't intercept with modifier keys
			if (event.metaKey || event.altKey || event.ctrlKey || event.shiftKey) return
			// Don't intercept right-click
			if (event.button !== undefined && event.button !== 0) return
			// Don't intercept external or same-page links
			let url
			try {
				url = new URL(a.href)
			} catch {
				return
			}
			if (window.location.pathname === url.pathname) return
			if (window.location.hostname !== url.hostname) return
			event.preventDefault()
			router.push(url.pathname + url.search + url.hash)
		},
	},
}
</script>
<style lang="stylus">
.rich-text-content
	p, h1, h2, h3, h4, h5, h6, blockquote, ul, ol, pre, li
		max-width: none
		margin: 0 16px

	ul, ol
		max-width: none
		padding-left: 2em

	img
		margin: 0 auto
		display: block
		max-width: 100%

	a, a[href]:not([class])
		&:hover
			text-decoration: underline

	li
		line-height: 1.6

	pre
		background: #f4f4f4
		border-radius: 4px
		padding: 0.75rem 1rem
		overflow-x: auto
		margin: 0 16px
		code
			background: none
			padding: 0
			font-size: 0.875em

	code
		background: rgba(0, 0, 0, 0.06)
		border-radius: 3px
		padding: 0.2em 0.4em
		font-size: 0.9em

	blockquote
		padding-left: 1em
		border-left: 3px solid #ccc
		margin: 0 16px
		color: #666

	h1, h2, h3, h4, h5, h6
		margin: 0 16px

	.text-left
		text-align: left
	.text-center
		text-align: center
	.text-right
		text-align: right

</style>

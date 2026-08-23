<template lang="pug">
.rich-text-content(v-html="sanitizedContent", @click="handleClick")
</template>
<script>
import DOMPurify from 'dompurify'
import router from 'router'

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
					// Render as plain text fallback (no formatting)
					const plain = ops
						.map(op => (typeof op.insert === 'string' ? op.insert : ''))
						.join('')
					return DOMPurify.sanitize('<p>' + plain.replace(/\n/g, '<br>') + '</p>')
				}
				return ''
			}

			// Regular HTML string
			return DOMPurify.sanitize(this.content, {
				ADD_ATTR: ['target', 'rel'],
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

	// Text-align support (set by Tiptap TextAlign extension)
	[style*="text-align: center"], .text-center
		text-align: center
	[style*="text-align: right"], .text-right
		text-align: right
	[style*="text-align: left"], .text-left
		text-align: left
</style>

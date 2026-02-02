<template lang="pug">
.rich-text-content(@click="handleClick")
	.rich-text-inner(v-html="renderedHtml")
</template>
<script>
import router from 'router'
import { richTextToHtml, sanitizeHtml } from 'lib/richText'

export default {
	props: {
		content: [String, Array, Object],
	},
	computed: {
		renderedHtml() {
			const html = richTextToHtml(this.content)
			return sanitizeHtml(html)
		}
	},
	methods: {
		handleClick(event) {
			const a = event.target.closest('a')
			if (!a) return
			// from https://github.com/vuejs/vue-router/blob/dfc289202703319cf7beb38d03c9258c806c4d62/src/components/link.js#L165
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
		}
	},
}
</script>

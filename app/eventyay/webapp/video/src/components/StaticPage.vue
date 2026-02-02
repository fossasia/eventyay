<template lang="pug">
.c-static-page(v-scrollbar.y="")
	rich-text-content(:content="module.config.content")
</template>
<script>
import RichTextContent from 'components/RichTextContent'

export default {
	components: { RichTextContent },
	props: {
		module: Object
	}
}
</script>
<style lang="stylus">
.c-static-page
	flex: auto
	.content-wrapper
		width: 100%
		max-width: 960px
		margin: 0 auto
	.rich-text-content .rich-text-inner
		margin: 16px 0

#app.override-sidebar-collapse .c-static-page .rich-text-content .rich-text-inner
	> *, li
		margin: 0 16px
</style>

<template lang="pug">
.c-page-static-settings
	rich-text-editor(v-model="modules['page.static'].config.content")
</template>
<script>
import RichTextEditor from 'components/RichTextEditor'
import mixin from './mixin'

export default {
	components: { RichTextEditor },
	mixins: [mixin]
}
</script>
<style lang="stylus">
.c-page-static-settings
	width: 100%
</style>

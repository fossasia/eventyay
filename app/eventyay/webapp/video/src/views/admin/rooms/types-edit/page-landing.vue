<template lang="pug">
.c-page-landing-settings
	upload-url-input(v-model="modules['page.landing'].config.header_image", :label="$t('Header image')", name="header-image")
	upload-url-input(v-model="modules['page.landing'].config.header_background_image", :label="$t('Header background image')", name="header-background-image")
	bunt-input(v-model="modules['page.landing'].config.header_background_color", :label="$t('Header background color')", name="headerbackgroundcolor")
	rich-text-editor(:label="$t('Main content')", v-model="modules['page.landing'].config.main_content")
</template>
<script>
import UploadUrlInput from 'components/UploadUrlInput'
import RichTextEditor from 'components/RichTextEditor'
import mixin from './mixin'

export default {
	components: { RichTextEditor, UploadUrlInput },
	mixins: [mixin],
}
</script>
<style lang="stylus">
.c-page-landing-settings
	.editor
		margin: 8px
</style>

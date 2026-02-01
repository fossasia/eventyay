<template lang="pug">
bunt-input-outline-container.c-rich-text-editor(ref="outline", :label="label")
	.editor
		editor-tinymce(
			:model-value="internalValue"
			@update:modelValue="onInternalChange"
			:init="tinymceInit"
		)

</template>
<script setup>
import { computed, ref, watch } from 'vue'
import EditorTinymce from '@tinymce/tinymce-vue'
import 'tinymce/tinymce'
import 'tinymce/icons/default'
import 'tinymce/themes/silver'
import 'tinymce/models/dom'
import 'tinymce/plugins/codesample'
import 'tinymce/plugins/link'
import 'tinymce/plugins/lists'
import 'tinymce/plugins/table'
import 'tinymce/skins/ui/oxide/skin.css'
import 'tinymce/skins/content/default/content.css'

import { deltaToHtml, looksLikeHtml, sanitizeHtml } from 'lib/richText'

const props = defineProps({
	modelValue: [String, Object, Array],
	label: String,
})
const emit = defineEmits(['update:modelValue'])

const outline = ref(null)

const internalValue = ref('')

function normalizeIncoming(value) {
	if (!value) return ''
	if (typeof value === 'string') return value
	return deltaToHtml(value)
}

watch(
	() => props.modelValue,
	(value) => {
		internalValue.value = normalizeIncoming(value)
	},
	{ immediate: true, deep: true }
)

function onInternalChange(nextValue) {
	const sanitized = sanitizeHtml(nextValue)
	if (sanitized !== internalValue.value) internalValue.value = sanitized
	if (sanitized !== normalizeIncoming(props.modelValue)) {
		emit('update:modelValue', sanitized)
	}
}

const tinymceInit = computed(() => ({
	menubar: false,
	branding: false,
	promotion: false,
	statusbar: false,
	height: 320,
	// We're bundling TinyMCE UI/content CSS via Vite imports above.
	// Prevent TinyMCE from trying to load its default skin/content CSS via network.
	skin: false,
	content_css: false,
	// TinyMCE runs content inside an iframe, so it won't inherit the app font.
	// Keep it consistent with the video app `$font-stack`.
	content_style: (
		'html, body { '
		+ 'font-family: "Open Sans", "OpenSans", "Helvetica Neue", Helvetica, Arial, "Microsoft Yahei", "微软雅黑", STXihei, "华文细黑", sans-serif; '
		+ 'font-size: 14px; line-height: 1.5; '
		+ '} '
		+ 'body * { font-family: inherit; }'
	),
	plugins: 'lists link table codesample',
	toolbar: (
		'undo redo | blocks | '
		+ 'bold italic underline strikethrough subscript superscript | '
		+ 'forecolor backcolor | '
		+ 'bullist numlist | '
		+ 'link table | codesample | removeformat'
	),
	toolbar_mode: 'sliding',
	block_formats: (
		'Paragraph=p; '
		+ 'Heading 1=h1; Heading 2=h2; Heading 3=h3; '
		+ 'Heading 4=h4; Heading 5=h5; Heading 6=h6'
	),
	extended_valid_elements: (
		'a[href|title|class|rel|target],'
		+ 'abbr[title],'
		+ 'acronym[title],'
		+ 'b,br,code,div[class|style],em,hr,i,sub,sup,'
		+ 'li,ol,p[class|style],pre[class],code[class],span[class|style|title],strong,'
		+ 'table[width],thead,tbody,tfoot,tr,td[width|align|colspan|rowspan],th[width|align|colspan|rowspan],'
		+ 'h1,h2,h3,h4,h5,h6,ul'
	),
	convert_urls: false,
	setup: (editor) => {
		editor.on('focus', () => outline.value?.focus?.())
		editor.on('blur', () => outline.value?.blur?.())
		// If legacy plain text slips through, keep it as text.
		editor.on('BeforeSetContent', (e) => {
			if (typeof e.content === 'string' && e.content && !looksLikeHtml(e.content)) {
				e.content = e.content.replaceAll('\n', '<br>')
			}
		})
	},
}))
</script>
<style lang="stylus">
.c-rich-text-editor
	padding-top: 0
	position: relative
	height: 320px

	.editor
		width: 100%
		height: 100%
		:deep(.tox)
			font-family: 'Open Sans', "OpenSans", "Helvetica Neue", Helvetica, Arial, "Microsoft Yahei", "微软雅黑", STXihei, "华文细黑", sans-serif
			border: 0
			border-radius: 0
			box-shadow: none
			// Keep TinyMCE UI typography consistent with the app.
			.tox-toolbar, .tox-toolbar__primary, .tox-toolbar__group,
			.tox-menubar, .tox-menu, .tox-collection, .tox-dialog
				font-family: inherit

/* TinyMCE popovers/menus are rendered into `.tox-tinymce-aux` near <body>.
 * Keep them above content but below fixed nav UI.
 */
.tox-tinymce-aux
	z-index: 1050
</style>

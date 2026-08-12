<template lang="pug">
bunt-input-outline-container.c-rich-text-editor(ref="outline", :label="label")
	.toolbar
		.buttongroup
			bunt-icon-button(@click="run('toggleBold')", :class="{active: isActive('bold')}", v-tooltip="$t('RichTextEditor:bold:tooltip')") format-bold
			bunt-icon-button(@click="run('toggleItalic')", :class="{active: isActive('italic')}", v-tooltip="$t('RichTextEditor:italic:tooltip')") format-italic
			bunt-icon-button(@click="run('toggleUnderline')", :class="{active: isActive('underline')}", v-tooltip="$t('RichTextEditor:underline:tooltip')") format-underline
			bunt-icon-button(@click="run('toggleStrike')", :class="{active: isActive('strike')}", v-tooltip="$t('RichTextEditor:strike:tooltip')") format-strikethrough-variant
		.buttongroup
			bunt-icon-button(@click="setHeading(1)", :class="{active: isActive('heading', {level: 1})}", v-tooltip="$t('RichTextEditor:h1:tooltip')") format-header-1
			bunt-icon-button(@click="setHeading(2)", :class="{active: isActive('heading', {level: 2})}", v-tooltip="$t('RichTextEditor:h2:tooltip')") format-header-2
			bunt-icon-button(@click="setHeading(3)", :class="{active: isActive('heading', {level: 3})}", v-tooltip="$t('RichTextEditor:h3:tooltip')") format-header-3
			bunt-icon-button(@click="setHeading(4)", :class="{active: isActive('heading', {level: 4})}", v-tooltip="$t('RichTextEditor:h4:tooltip')") format-header-4
			bunt-icon-button(@click="run('toggleBlockquote')", :class="{active: isActive('blockquote')}", v-tooltip="$t('RichTextEditor:blockquote:tooltip')") format-quote-open
			bunt-icon-button(@click="run('toggleCodeBlock')", :class="{active: isActive('codeBlock')}", v-tooltip="$t('RichTextEditor:code:tooltip')") code-tags
		.buttongroup
			bunt-icon-button(@click="run('toggleOrderedList')", :class="{active: isActive('orderedList')}", v-tooltip="$t('RichTextEditor:list-ordered:tooltip')") format-list-numbered
			bunt-icon-button(@click="run('toggleBulletList')", :class="{active: isActive('bulletList')}", v-tooltip="$t('RichTextEditor:list-bullet:tooltip')") format-list-bulleted
		.buttongroup
			bunt-icon-button(@click="setLink", :class="{active: isActive('link')}", v-tooltip="$t('RichTextEditor:link:tooltip')") link-variant
			bunt-icon-button(@click="triggerImageUpload", v-tooltip="$t('RichTextEditor:image:tooltip')") image
		.buttongroup
			bunt-icon-button(@click="run('clearNodes'); run('unsetAllMarks')", v-tooltip="$t('RichTextEditor:clean:tooltip')") format-clear
	.editor-mount(ref="editorMount")
	input.hidden-file-input(ref="fileInput", type="file", accept="image/png,image/gif,image/jpeg,image/bmp,image/x-icon", @change="onFileSelected")
	.uploading(v-if="uploading")
		bunt-progress-circular(size="huge")
	error-dialog(
		v-if="showErrorDialog"
		:title="$t('RichTextEditor:upload:error-title')"
		:message="uploadErrorMessage"
		:button-text="$t('RichTextEditor:upload:error-ok')"
		@close="showErrorDialog = false"
	)
</template>
<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import Link from '@tiptap/extension-link'
import Underline from '@tiptap/extension-underline'
import api from 'lib/api'
import i18n from 'i18n'
import ErrorDialog from 'components/ErrorDialog'

const props = defineProps({
	modelValue: [String, Object, Array], // accepts HTML string or legacy Quill Delta
	label: String,
})
const emit = defineEmits(['update:modelValue'])

const editorMount = ref(null)
const fileInput = ref(null)
const uploading = ref(false)
const showErrorDialog = ref(false)
const uploadErrorMessage = ref('')

// Normalise incoming value: Quill Delta objects → empty string on initial load
function toHtml(val) {
	if (!val) return ''
	if (typeof val === 'string') return val
	// Legacy Quill Delta ({ ops: [...] }) — start empty rather than corrupt the editor
	return ''
}

const editor = useEditor({
	extensions: [
		StarterKit,
		Underline,
		Image,
		Link.configure({ openOnClick: false, autolink: true }),
	],
	content: toHtml(props.modelValue),
	onFocus() { /* buntpapier outline handles focus visually via ref */ },
	onUpdate({ editor }) {
		emit('update:modelValue', editor.getHTML())
	},
})

// Sync when the parent sets a new value externally (e.g. after async data load)
watch(() => props.modelValue, (val) => {
	if (!editor.value) return
	const html = toHtml(val)
	if (html !== editor.value.getHTML()) {
		editor.value.commands.setContent(html, false)
	}
})

onMounted(() => {
	// Attach the ProseMirror DOM element into our mount point
	if (editorMount.value && editor.value) {
		editorMount.value.appendChild(editor.value.options.element)
	}
})

onBeforeUnmount(() => {
	editor.value?.destroy()
})

// ── Helpers ──────────────────────────────────────────────────────────────────
const isActive = (name, attrs) => editor.value?.isActive(name, attrs) ?? false

function run(command, opts) {
	const chain = editor.value?.chain().focus()
	if (!chain) return
	chain[command]?.(opts).run()
}

function setHeading(level) {
	if (isActive('heading', { level })) {
		editor.value?.chain().focus().setParagraph().run()
	} else {
		editor.value?.chain().focus().toggleHeading({ level }).run()
	}
}

function setLink() {
	const prev = editor.value?.getAttributes('link').href || ''
	const url = window.prompt('Enter URL', prev)
	if (url === null) return
	if (url === '') {
		editor.value?.chain().focus().extendMarkRange('link').unsetLink().run()
	} else {
		editor.value?.chain().focus().extendMarkRange('link').setLink({ href: url }).run()
	}
}

// ── Image upload ─────────────────────────────────────────────────────────────
function triggerImageUpload() { fileInput.value?.click() }

async function onFileSelected() {
	const file = fileInput.value?.files?.[0]
	if (!file) return
	showErrorDialog.value = false
	uploading.value = true
	try {
		const data = await api.uploadFilePromise(file, file.name)
		if (data.error) {
			uploadErrorMessage.value = i18n.t('RichTextEditor:upload:error')
			console.error('RichTextEditor image upload failed', data.error)
			showErrorDialog.value = true
		} else {
			editor.value?.chain().focus().setImage({ src: data.url }).run()
		}
	} catch (err) {
		uploadErrorMessage.value = i18n.t('RichTextEditor:upload:error')
		console.error('RichTextEditor image upload failed', err)
		showErrorDialog.value = true
	} finally {
		uploading.value = false
		if (fileInput.value) fileInput.value.value = ''
	}
}
</script>
<style lang="stylus">
.c-rich-text-editor
	padding-top: 0
	position: relative
	min-height: 30vh
	height: 30vh
	display: flex
	flex-direction: column
	overflow: visible

	.hidden-file-input
		display: none

	.uploading
		position: absolute
		left: 0
		top: 0
		width: 100%
		height: 100%
		background: rgba(255, 255, 255, 0.7)
		display: flex
		align-items: center
		justify-content: center

	.toolbar
		border-bottom: 1px solid #ccc
		display: flex
		flex-direction: row
		flex-wrap: wrap
		padding: 4px
		flex: 0 0 auto
		.buttongroup
			margin-right: 16px
		.bunt-icon-button
			border-radius: 8px
			margin-right: 2px
			.bunt-icon
				color: rgba(0, 0, 0, 0.5)
		.bunt-icon-button.active
			background: #f0f0f0
			.bunt-icon
				color: var(--clr-primary)

	.editor-mount
		flex: 1 1 auto
		min-height: 0
		overflow-y: auto
		.ProseMirror
			padding: 12px 16px
			min-height: 100%
			outline: none
			font-size: 14px
			line-height: 1.6
			> * + *
				margin-top: 0.5em
			p
				margin: 0
			h1, h2, h3, h4, h5, h6
				margin: 0.5em 0 0.25em
			ul, ol
				padding-left: 1.5em
			blockquote
				border-left: 3px solid #ccc
				padding-left: 1em
				color: #666
				margin: 0
			a
				color: var(--clr-primary)
				text-decoration: underline
			img
				max-width: 100%
				display: block
				margin: 0 auto
			pre
				background: #f4f4f4
				padding: 8px 12px
				border-radius: 4px
				overflow-x: auto
				code
					background: none
					padding: 0
			code
				background: #f4f4f4
				padding: 2px 4px
				border-radius: 3px
</style>

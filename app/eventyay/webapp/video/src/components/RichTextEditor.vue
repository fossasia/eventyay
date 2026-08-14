<template lang="pug">
bunt-input-outline-container.c-rich-text-editor(ref="outline", :label="label")
	.toolbar
		.buttongroup
			bunt-icon-button(:class="{active: isActive('bold')}", @click="cmd('toggleBold')", v-tooltip="$t('RichTextEditor:bold:tooltip')") format-bold
			bunt-icon-button(:class="{active: isActive('italic')}", @click="cmd('toggleItalic')", v-tooltip="$t('RichTextEditor:italic:tooltip')") format-italic
			bunt-icon-button(:class="{active: isActive('underline')}", @click="cmd('toggleUnderline')", v-tooltip="$t('RichTextEditor:underline:tooltip')") format-underline
			bunt-icon-button(:class="{active: isActive('strike')}", @click="cmd('toggleStrike')", v-tooltip="$t('RichTextEditor:strike:tooltip')") format-strikethrough-variant
		.buttongroup
			bunt-icon-button(:class="{active: isActive('heading', {level: 1})}", @click="cmdWith('toggleHeading', {level: 1})", v-tooltip="$t('RichTextEditor:h1:tooltip')") format-header-1
			bunt-icon-button(:class="{active: isActive('heading', {level: 2})}", @click="cmdWith('toggleHeading', {level: 2})", v-tooltip="$t('RichTextEditor:h2:tooltip')") format-header-2
			bunt-icon-button(:class="{active: isActive('heading', {level: 3})}", @click="cmdWith('toggleHeading', {level: 3})", v-tooltip="$t('RichTextEditor:h3:tooltip')") format-header-3
			bunt-icon-button(:class="{active: isActive('heading', {level: 4})}", @click="cmdWith('toggleHeading', {level: 4})", v-tooltip="$t('RichTextEditor:h4:tooltip')") format-header-4
			bunt-icon-button(:class="{active: isActive('blockquote')}", @click="cmd('toggleBlockquote')", v-tooltip="$t('RichTextEditor:blockquote:tooltip')") format-quote-open
			bunt-icon-button(:class="{active: isActive('codeBlock')}", @click="cmd('toggleCodeBlock')", v-tooltip="$t('RichTextEditor:code:tooltip')") code-tags
		.buttongroup
			bunt-icon-button(:class="{active: isActive('orderedList')}", @click="cmd('toggleOrderedList')", v-tooltip="$t('RichTextEditor:list-ordered:tooltip')") format-list-numbered
			bunt-icon-button(:class="{active: isActive('bulletList')}", @click="cmd('toggleBulletList')", v-tooltip="$t('RichTextEditor:list-bullet:tooltip')") format-list-bulleted
		.buttongroup
			bunt-icon-button(:class="{active: isActive({textAlign: 'left'})}", @click="cmdWith('setTextAlign', 'left')", v-tooltip="$t('RichTextEditor:align-left:tooltip')") format-align-left
			bunt-icon-button(:class="{active: isActive({textAlign: 'center'})}", @click="cmdWith('setTextAlign', 'center')", v-tooltip="$t('RichTextEditor:align-center:tooltip')") format-align-center
			bunt-icon-button(:class="{active: isActive({textAlign: 'right'})}", @click="cmdWith('setTextAlign', 'right')", v-tooltip="$t('RichTextEditor:align-right:tooltip')") format-align-right
		.buttongroup
			bunt-icon-button(@click="insertLink", v-tooltip="$t('RichTextEditor:link:tooltip')") link-variant
			bunt-icon-button(@click="triggerImageUpload", v-tooltip="$t('RichTextEditor:image:tooltip')") image
		.buttongroup
			bunt-icon-button(@click="clearFormatting", v-tooltip="$t('RichTextEditor:clean:tooltip')") format-clear
	.editor-mount(ref="editorMount")
	input(type="file", ref="imageInput", accept="image/png, image/gif, image/jpeg, image/bmp, image/x-icon", style="display:none", @change="handleImageUpload")
	.uploading(v-if="uploading")
		bunt-progress-circular(size="huge")
	error-dialog(
		v-if="showErrorDialog"
		:title="$t('RichTextEditor:upload:error-title')"
		:message="uploadErrorMessage"
		:button-text="$t('RichTextEditor:upload:error-ok')"
		@close="closeErrorDialog"
	)
</template>
<script setup>
/* global ENV_DEVELOPMENT */
import { ref, onMounted, onBeforeUnmount, watch, markRaw } from 'vue'
import { Editor } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import Link from '@tiptap/extension-link'
import Underline from '@tiptap/extension-underline'
import TextAlign from '@tiptap/extension-text-align'
import api from 'lib/api'
import i18n from 'i18n'
import ErrorDialog from 'components/ErrorDialog'

const props = defineProps({
	modelValue: String,
	label: String,
})
const emit = defineEmits(['update:modelValue'])

const outline = ref(null)
const editorMount = ref(null)
const imageInput = ref(null)
const uploading = ref(false)
const showErrorDialog = ref(false)
const uploadErrorMessage = ref('')

// Reactive state for toolbar active-state re-renders
const editorState = ref(null)

let editorInstance = null
let emitTimeout = null

// Toolbar helpers — read from editorState to stay reactive
const isActive = (nameOrAttrs, attrs) => {
	if (!editorInstance) return false
	if (typeof nameOrAttrs === 'string') {
		return editorInstance.isActive(nameOrAttrs, attrs)
	}
	return editorInstance.isActive(nameOrAttrs)
}

const cmd = (command) => {
	if (!editorInstance) return
	editorInstance.chain().focus()[command]().run()
}

const cmdWith = (command, arg) => {
	if (!editorInstance) return
	editorInstance.chain().focus()[command](arg).run()
}

const insertLink = () => {
	if (!editorInstance) return
	const existing = editorInstance.getAttributes('link').href || ''
	const url = prompt(i18n.t('RichTextEditor:link:prompt') || 'Enter URL', existing)
	if (url === null) return
	if (url === '') {
		editorInstance.chain().focus().unsetLink().run()
	} else {
		editorInstance.chain().focus().setLink({ href: url, target: '_blank' }).run()
	}
}

const triggerImageUpload = () => {
	imageInput.value?.click()
}

const handleImageUpload = (event) => {
	const file = event.target.files?.[0]
	if (!file) return
	showErrorDialog.value = false
	uploading.value = true
	api.uploadFilePromise(file, file.name).then(data => {
		if (data.error) {
			uploadErrorMessage.value = i18n.t('RichTextEditor:upload:error')
			console.error('RichTextEditor image upload failed', data.error, `File: ${file.name}`)
			showErrorDialog.value = true
		} else {
			editorInstance?.chain().focus().setImage({ src: data.url }).run()
		}
		uploading.value = false
		event.target.value = ''
	}).catch(error => {
		uploadErrorMessage.value = i18n.t('RichTextEditor:upload:error')
		console.error('RichTextEditor image upload failed', error, `File: ${file.name}`)
		showErrorDialog.value = true
		uploading.value = false
	})
}

const clearFormatting = () => {
	editorInstance?.chain().focus().clearNodes().unsetAllMarks().run()
}

const closeErrorDialog = () => {
	showErrorDialog.value = false
	uploadErrorMessage.value = ''
}

onMounted(() => {
	editorInstance = markRaw(new Editor({
		element: editorMount.value,
		extensions: [
			StarterKit,
			Image.configure({ inline: false, allowBase64: false }),
			Link.configure({ openOnClick: false, autolink: true }),
			Underline,
			TextAlign.configure({ types: ['heading', 'paragraph'] }),
		],
		content: props.modelValue || '',
		editorProps: {
			attributes: {
				class: 'rich-text-content',
			},
		},
		onUpdate: ({ editor }) => {
			// Trigger toolbar re-render
			editorState.value = editor.state
			clearTimeout(emitTimeout)
			emitTimeout = setTimeout(() => {
				emit('update:modelValue', editor.getHTML())
			}, 50)
		},
		onSelectionUpdate: ({ editor }) => {
			editorState.value = editor.state
		},
		onFocus: () => {
			outline.value?.focus?.()
		},
		onBlur: () => {
			outline.value?.blur?.()
		},
	}))
	editorState.value = editorInstance.state
})

onBeforeUnmount(() => {
	clearTimeout(emitTimeout)
	editorInstance?.destroy()
	editorInstance = null
})

// Sync external model changes (e.g. parent resets the field)
watch(() => props.modelValue, (newVal) => {
	if (!editorInstance) return
	const current = editorInstance.getHTML()
	if (newVal === current) return
	editorInstance.commands.setContent(newVal || '', false)
})
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
		.active
			background: #f0f0f0
		.active .bunt-icon
			color: var(--clr-primary)

	.editor-mount
		flex: 1 1 auto
		min-height: 0
		overflow-y: auto

	// ProseMirror editor styles
	.ProseMirror
		padding: 12px 16px
		min-height: 100%
		outline: none
		font-family: $font-stack
		font-size: 14px
		line-height: 1.5
		> * + *
			margin-top: 0.75em
		p
			margin: 0
		h1, h2, h3, h4, h5, h6
			margin: 0
		img
			max-width: 100%
			display: block
			margin: 0 auto
		a
			color: var(--clr-primary)
			text-decoration: underline
		ul, ol
			padding-left: 2em
			margin: 0
		pre
			background: #f4f4f4
			border-radius: 4px
			padding: 0.75rem 1rem
			code
				background: none
				padding: 0
				font-size: 0.875em
		code
			background: rgba(0,0,0,0.06)
			border-radius: 3px
			padding: 0.2em 0.4em
			font-size: 0.9em
		blockquote
			padding-left: 1em
			border-left: 3px solid #ccc
			margin: 0
			color: #666
		&.ProseMirror-focused
			outline: none
		&[data-placeholder]::before
			content: attr(data-placeholder)
			float: left
			color: #adb5bd
			pointer-events: none
			height: 0
</style>

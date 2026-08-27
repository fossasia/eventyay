<template lang="pug">
bunt-input-outline-container.c-rich-text-editor(ref="outline", :label="label")
	.tiptap-toolbar(role="toolbar", :aria-label="$t('Text formatting')")
		button.tiptap-btn(:class="{'is-active': isActive('bold')}", type="button", :title="$t('Bold')", :aria-label="$t('Bold')", @click.prevent="cmd('toggleBold')")
			b B
		button.tiptap-btn(:class="{'is-active': isActive('italic')}", type="button", :title="$t('Italic')", :aria-label="$t('Italic')", @click.prevent="cmd('toggleItalic')")
			i I
		button.tiptap-btn(:class="{'is-active': isActive('underline')}", type="button", :title="$t('Underline')", :aria-label="$t('Underline')", @click.prevent="cmd('toggleUnderline')")
			u U
		button.tiptap-btn(:class="{'is-active': isActive('strike')}", type="button", :title="$t('Strikethrough')", :aria-label="$t('Strikethrough')", @click.prevent="cmd('toggleStrike')")
			s S
		span.tiptap-separator(aria-hidden="true")
		button.tiptap-btn(:class="{'is-active': isActive('heading', {level: 1})}", type="button", :title="$t('Heading 1')", :aria-label="$t('Heading 1')", @click.prevent="cmdWith('toggleHeading', {level: 1})") H1
		button.tiptap-btn(:class="{'is-active': isActive('heading', {level: 2})}", type="button", :title="$t('Heading 2')", :aria-label="$t('Heading 2')", @click.prevent="cmdWith('toggleHeading', {level: 2})") H2
		button.tiptap-btn(:class="{'is-active': isActive('heading', {level: 3})}", type="button", :title="$t('Heading 3')", :aria-label="$t('Heading 3')", @click.prevent="cmdWith('toggleHeading', {level: 3})") H3
		button.tiptap-btn(:class="{'is-active': isActive('blockquote')}", type="button", :title="$t('Blockquote')", :aria-label="$t('Blockquote')", @click.prevent="cmd('toggleBlockquote')") ❝
		button.tiptap-btn(:class="{'is-active': isActive('codeBlock')}", type="button", :title="$t('Code block')", :aria-label="$t('Code block')", @click.prevent="cmd('toggleCodeBlock')") &lt;/&gt;
		span.tiptap-separator(aria-hidden="true")
		button.tiptap-btn(:class="{'is-active': isActive('bulletList')}", type="button", :title="$t('Bullet list')", :aria-label="$t('Bullet list')", @click.prevent="cmd('toggleBulletList')") &#8226;&#8212;
		button.tiptap-btn(:class="{'is-active': isActive('orderedList')}", type="button", :title="$t('Numbered list')", :aria-label="$t('Numbered list')", @click.prevent="cmd('toggleOrderedList')") 1.&#8212;
		span.tiptap-separator(aria-hidden="true")
		button.tiptap-btn(:class="{'is-active': isActive({textAlign: 'left'})}", type="button", :title="$t('Align left')", :aria-label="$t('Align left')", @click.prevent="cmdWith('setTextAlign', 'left')") &#8676;
		button.tiptap-btn(:class="{'is-active': isActive({textAlign: 'center'})}", type="button", :title="$t('Align center')", :aria-label="$t('Align center')", @click.prevent="cmdWith('setTextAlign', 'center')") &#8652;
		button.tiptap-btn(:class="{'is-active': isActive({textAlign: 'right'})}", type="button", :title="$t('Align right')", :aria-label="$t('Align right')", @click.prevent="cmdWith('setTextAlign', 'right')") &#8677;
		span.tiptap-separator(aria-hidden="true")
		span.tiptap-link-menu(ref="linkMenuRef")
			button.tiptap-btn(type="button", :title="$t('Insert link')", :aria-label="$t('Insert link')", @click.prevent="insertLink") &#128279;
		button.tiptap-btn(type="button", :title="$t('Insert image')", :aria-label="$t('Insert image')", @click.prevent="triggerImageUpload") &#128247;
		span.tiptap-separator(aria-hidden="true")
		button.tiptap-btn(type="button", :title="$t('Clear formatting')", :aria-label="$t('Clear formatting')", @click.prevent="clearFormatting") &#10005;
		button.tiptap-btn(type="button", :title="$t('Undo')", :aria-label="$t('Undo')", @click.prevent="cmd('undo')") &#8630;
		button.tiptap-btn(type="button", :title="$t('Redo')", :aria-label="$t('Redo')", @click.prevent="cmd('redo')") &#8631;
	.editor-mount(ref="editorMount")
	input(type="file", ref="imageInput", accept="image/png, image/gif, image/jpeg, image/bmp, image/x-icon", style="display:none", @change="handleImageUpload")
	.uploading(v-if="uploading")
		bunt-progress-circular(size="huge")
	error-dialog(
		v-if="showErrorDialog"
		:title="$t('Upload failed')"
		:message="uploadErrorMessage"
		:button-text="$t('OK')"
		@close="closeErrorDialog"
	)
</template>
<script setup>
/* global ENV_DEVELOPMENT */
import { ref, onMounted, onBeforeUnmount, watch, markRaw } from 'vue'
import { Editor } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import TextAlign from '@tiptap/extension-text-align'
import api from 'lib/api'
import i18n from 'i18n'
import ErrorDialog from 'components/ErrorDialog'

const CustomTextAlign = TextAlign.extend({
	addGlobalAttributes() {
		return [
			{
				types: this.options.types,
				attributes: {
					textAlign: {
						default: this.options.defaultAlignment,
						parseHTML: element => {
							if (element.classList.contains('text-left')) return 'left'
							if (element.classList.contains('text-center')) return 'center'
							if (element.classList.contains('text-right')) return 'right'
							return element.style.textAlign || this.options.defaultAlignment
						},
						renderHTML: attributes => {
							if (!attributes.textAlign || attributes.textAlign === this.options.defaultAlignment) {
								return {}
							}
							return { class: `text-${attributes.textAlign}` }
						},
					},
				},
			},
		]
	},
})

const props = defineProps({
	// HTML string going forward; Object/Array kept for legacy Quill Delta values
	modelValue: [String, Object, Array],
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

function escapeHtml (text) {
	return String(text)
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
}

/** Normalize v-model into HTML Tiptap can load (legacy Delta → plain HTML). */
function normalizeEditorContent (value) {
	if (!value) return ''
	if (typeof value === 'string') return value
	if (typeof value === 'object') {
		const ops = Array.isArray(value) ? value : value.ops
		if (Array.isArray(ops)) {
			const plain = ops
				.map(op => (typeof op.insert === 'string' ? op.insert : ''))
				.join('')
			return '<p>' + escapeHtml(plain).replace(/\n/g, '<br>') + '</p>'
		}
	}
	return ''
}

// Toolbar helpers — read from editorState to stay reactive
const isActive = (nameOrAttrs, attrs) => {
	if (!editorState.value || !editorInstance) return false
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
	const url = prompt(i18n.t('Enter URL'), existing)
	if (url === null) return
	if (url === '') {
		editorInstance.chain().focus().extendMarkRange('link').unsetLink().run()
	} else {
		editorInstance.chain().focus().extendMarkRange('link').setLink({ href: url, target: '_blank', rel: 'noopener noreferrer' }).run()
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
			uploadErrorMessage.value = i18n.t('Failed to upload the image')
			console.error('RichTextEditor image upload failed', data.error, `File: ${file.name}`)
			showErrorDialog.value = true
		} else {
			editorInstance?.chain().focus().setImage({ src: data.url }).run()
		}
		uploading.value = false
		event.target.value = ''
	}).catch(error => {
		uploadErrorMessage.value = i18n.t('Failed to upload the image')
		console.error('RichTextEditor image upload failed', error, `File: ${file.name}`)
		showErrorDialog.value = true
		uploading.value = false
		event.target.value = ''
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
			StarterKit.configure({
				// TipTap v3 StarterKit already includes Link + Underline.
				link: {
					openOnClick: false,
					autolink: true,
					HTMLAttributes: { rel: 'noopener noreferrer', target: '_blank' },
				},
			}),
			Image.configure({ inline: false, allowBase64: false }),
			CustomTextAlign.configure({ types: ['heading', 'paragraph'] }),
		],
		content: normalizeEditorContent(props.modelValue),
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
	const normalized = normalizeEditorContent(newVal)
	const current = editorInstance.getHTML()
	if (normalized === current) return
	editorInstance.commands.setContent(normalized, { emitUpdate: false })
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

// ── Toolbar (matches tickets/email Tiptap editor) ──────────────────────────

.tiptap-toolbar
	display: flex
	flex-wrap: wrap
	align-items: center
	gap: 2px
	padding: 4px 6px
	border-bottom: 1px solid #dee2e6
	background: #f8f9fa
	border-radius: 4px 4px 0 0
	flex: 0 0 auto

.tiptap-btn
	display: inline-flex
	align-items: center
	justify-content: center
	min-width: 30px
	height: 28px
	padding: 0 6px
	border: 1px solid transparent
	border-radius: 3px
	background: transparent
	color: #495057
	font-size: 13px
	line-height: 1
	cursor: pointer
	white-space: nowrap
	transition: background 0.1s, color 0.1s, border-color 0.1s
	&:hover
		background: #e9ecef
		border-color: #ced4da
	&.is-active
		background: rgba(13, 110, 253, 0.1)
		border-color: rgba(13, 110, 253, 0.4)
		color: #0d6efd
	&[disabled]
		opacity: 0.4
		cursor: default

.tiptap-separator
	display: inline-block
	width: 1px
	height: 20px
	background: #dee2e6
	margin: 0 3px
	vertical-align: middle

.tiptap-link-menu
	position: relative
	display: inline-block
</style>

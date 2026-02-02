<template lang="pug">
bunt-input-outline-container.c-chat-input
	textarea.editor(
		ref="editor"
		v-model="body"
		:placeholder="$t('ChatInput:input:placeholder')"
		@input="onInput"
		@keyup="onInput"
		@click="onInput"
		@keydown="onKeydown"
	)
	emoji-picker-button(@selected="addEmoji")
	upload-button#btn-file(accept="image/png, image/jpg, image/gif, application/pdf, .png, .jpg, .gif, .jpeg, .pdf", icon="paperclip", multiple=true, :tooltip="$t('ChatInput:btn-file:tooltip')", @change="attachFiles")
	bunt-icon-button#btn-send(:tooltip="$t('ChatInput:btn-send:tooltip')", tooltip-placement="top-end", @click="send") send
	.files-preview(v-if="files.length > 0 || uploading")
		template(v-for="file in files")
			.chat-file(v-if="file === null")
				i.bunt-icon.mdi.mdi-alert-circle.upload-error
				bunt-icon-button#btn-remove-attachment(@click="removeFile(file)") close-circle
			template(v-else)
				.chat-image(v-if="file.mimeType.startsWith('image/')")
					img(:src="file.url")
					bunt-icon-button#btn-remove-attachment(@click="removeFile(file)") close-circle
				.chat-file(v-else)
					a.chat-file-content(:href="file.url" target="_blank")
						i.bunt-icon.mdi.mdi-file
						| {{ file.name }}
					bunt-icon-button#btn-remove-attachment(@click="removeFile(file)") close-circle
		bunt-progress-circular(size="small", v-if="uploading")
	.ui-background-blocker(v-if="autocompleteCoordinates", @click="closeAutocomplete")
		.autocomplete-dropdown(:style="autocompleteCoordinates")
			template(v-if="autocomplete.options")
				template(v-for="option, index of autocomplete.options")
					.user(:class="{selected: index === autocomplete.selected}", :title="option.profile.display_name", @mouseover="selectMention(index)", @click.stop="handleMention")
						avatar(:user="option", :size="24")
						.name {{ option.profile.display_name }}
			bunt-progress-circular(v-else, size="large", :page="true")
</template>
<script>
/* global ENV_DEVELOPMENT */
// TODO
// - parse ascii emoticons ;)
// - parse colon emoji :+1:
// - add scrollbar when overflowing parent
import { nextTick } from 'vue'
import api from 'lib/api'
import Avatar from 'components/Avatar'
import EmojiPickerButton from 'components/EmojiPickerButton'
import UploadButton from 'components/UploadButton'

export default {
	components: { Avatar, EmojiPickerButton, UploadButton },
	emits: ['send'],
	props: {
		message: Object // initialize with existing message to edit
	},
	data() {
		return {
			body: '',
			files: [],
			uploading: false,
			autocomplete: null
		}
	},
	computed: {
		autocompleteCoordinates() {
			// TODO bound to right edge
			if (!this.autocomplete?.range) return null
			const editorRect = this.$refs.editor.getBoundingClientRect()
			const bounds = { left: 0, top: 0 }
			return {
				left: editorRect.x + 8 - Math.max(0, 240 - (editorRect.width + 60)) + 'px',
				bottom: window.innerHeight - editorRect.y + 8 + 'px'
			}
		}
	},
	watch: {
		async 'autocomplete.search'(search) {
			// TODO debounce?
			if (!this.autocomplete) return
			if (this.autocomplete.type === 'mention') {
				const { results } = await api.call('user.list.search', {search_term: search, page: 1, include_banned: false})
				this.autocomplete.options = results
				// if (results.length === 1) {
				// 	this.autocomplete.selected = 0
				// 	this.handleMention()
				// }
			}
		}
	},
	mounted() {
		if (this.message) {
			this.body = this.message.content?.body || ''
			if (this.message.content?.files?.length > 0) {
				this.files = this.message.content.files
			}
		}
	},
	methods: {
		onInput() {
			this.updateAutocomplete()
		},
		onKeydown(event) {
			if (event.key === 'Enter' && !event.shiftKey) {
				event.preventDefault()
				if (this.autocomplete) return this.handleMention()
				return this.send()
			}
			if (event.key === 'Tab') {
				if (!this.autocomplete) return true
				event.preventDefault()
				return this.handleMention()
			}
			if (event.key === 'ArrowUp') {
				if (!this.autocomplete) return true
				event.preventDefault()
				return this.handleArrayUp()
			}
			if (event.key === 'ArrowDown') {
				if (!this.autocomplete) return true
				event.preventDefault()
				return this.handleArrayDown()
			}
			if (event.key === 'Escape') {
				if (!this.autocomplete) return true
				event.preventDefault()
				return this.closeAutocomplete()
			}
			return true
		},
		updateAutocomplete() {
			const editor = this.$refs.editor
			if (!editor) return
			const caretPos = editor.selectionStart ?? 0
			const lookbackLength = Math.min(32, caretPos)
			const lookbackOffset = caretPos - lookbackLength
			const lookback = this.body.slice(lookbackOffset, caretPos)
			// only trigger when there is a space before @, except at the beginning of the message
			const startsWithMention = lookbackOffset === 0 && lookback.startsWith('@')
			const autocompleteCharIndex =
				startsWithMention
					? 0
					: lookback.lastIndexOf(' @') // TODO any whitespace
			if (autocompleteCharIndex > -1) {
				const startIndex = autocompleteCharIndex + lookbackOffset + (startsWithMention ? 0 : 1)
				this.autocomplete = {
					type: 'mention',
					search: lookback.slice(autocompleteCharIndex + 1 + (startsWithMention ? 0 : 1)),
					range: {
						start: startIndex,
						end: caretPos
					},
					selectionStart: editor.selectionStart,
					selectionEnd: editor.selectionEnd,
					options: null,
					selected: 0
				}
			} else {
				this.autocomplete = null
			}
		},
		handleArrayUp() {
			if (!this.autocomplete) return true
			this.autocomplete.selected = Math.max(0, this.autocomplete.selected - 1)
		},
		handleArrayDown() {
			if (!this.autocomplete) return true
			this.autocomplete.selected = Math.min(this.autocomplete.options.length - 1, this.autocomplete.selected + 1)
		},
		closeAutocomplete() {
			const editor = this.$refs.editor
			if (editor && this.autocomplete) {
				editor.focus()
				editor.setSelectionRange(this.autocomplete.selectionStart ?? 0, this.autocomplete.selectionEnd ?? 0)
			}
			this.autocomplete = null
		},
		selectMention(index) {
			this.autocomplete.selected = index
		},
		handleMention() {
			if (!this.autocomplete) return true
			const user = this.autocomplete.options[this.autocomplete.selected]
			if (!user) return true
			const { start, end } = this.autocomplete.range
			const insertValue = '@' + user.id + ' '
			this.body = this.body.slice(0, start) + insertValue + this.body.slice(end)
			nextTick(() => {
				const editor = this.$refs.editor
				if (!editor) return
				editor.focus()
				const caret = start + insertValue.length
				editor.setSelectionRange(caret, caret)
			})
			this.autocomplete = null
		},
		send() {
			const text = (this.body || '').trim()
			if (this.files.length > 0) {
				this.$emit('send', {
					type: 'files',
					files: this.files.filter(file => file),
					body: text
				})
				this.files = []
			} else {
				this.$emit('send', {
					type: 'text',
					body: text
				})
			}
			this.body = ''
		},
		async attachFiles(event) {
			const files = Array.from(event.target.files)
			if (files.length === 0) return

			this.uploading = true
			// TODO upload files sequentially
			const requests = files.map(file => api.uploadFilePromise(file, file.name))
			const fileInfos = (await Promise.all(requests)).map((response, i) => {
				if (response.error) {
					// TODO actually handle and display error
					return null
				} else {
					return {
						url: response.url,
						mimeType: files[i].type,
						name: files[i].name
					}
				}
			})
			this.files.push(...fileInfos)
			this.uploading = false
		},
		addEmoji(emoji) {
			const editor = this.$refs.editor
			if (!editor) return
			const start = editor.selectionStart ?? 0
			const end = editor.selectionEnd ?? start
			this.body = this.body.slice(0, start) + emoji.native + this.body.slice(end)
			nextTick(() => {
				editor.focus()
				const caret = start + emoji.native.length
				editor.setSelectionRange(caret, caret)
				this.updateAutocomplete()
			})
		},
		removeFile(file) {
			const index = this.files.indexOf(file)
			if (index > -1) {
				this.files.splice(index, 1)
			}
		}
	}
}
</script>
<style lang="stylus">
.c-chat-input
	position: relative
	display: flex
	width: calc(100% - 27px) // width of emoji picker for sidebar mode
	min-height: 36px
	box-sizing: border-box
	&.bunt-input-outline-container
		padding: 8px 60px 6px 36px
	textarea.editor
		width: 100%
		border: 0
		outline: 0
		background: transparent
		resize: none
		font-size: 16px
		line-height: 22px
		overflow-wrap: break-word
	.bunt-input
		input-style(size: compact)
		padding: 0
		input
			padding-left: 32px
	.c-emoji-picker-button .btn-emoji-picker
		position: absolute
		left: 4px
		top: 4px
		height: 28px
		width: @height
		padding: 4px
		svg
			path
				fill: $clr-secondary-text-light
	#btn-send, #btn-file .bunt-icon-button
		icon-button-style(color: $clr-secondary-text-light)
		height: 28px
		width: 28px
		.bunt-icon
			font-size: 18px
			height: 24px
			line-height: @height
	#btn-send
		position: absolute
		right: 4px
		top: 4px
	#btn-file
		position: absolute
		right: 32px
		top: 4px
	#btn-remove-attachment
		position: absolute
		right: -14px
		top: -14px
		icon-button-style(color: $clr-secondary-text-light)
		height: 28px
		width: 28px
		background: white
	.files-preview
		display: flex
		flex-wrap: wrap
		padding-top: 16px
		.chat-image, .chat-file
			position: relative
			height: 60px
			border-radius: 2px
			border: border-separator()
			margin: 0 12px 12px 0
		.chat-image
			width: 60px
			img
				object-fit: cover
				width: 100%
				height: 100%
		.chat-file
			min-width: 60px
			max-width: 100px
			text-align: center
			.upload-error
				color: $clr-danger
			.chat-file-content
				ellipsis()
				line-height: 60px
	.autocomplete-dropdown
		card()
		position: fixed
		width: 240px
		display: flex
		flex-direction: column
		.user
			display: flex
			height: 32px
			align-items: center
			gap: 8px
			padding: 0 8px
			cursor: pointer
			&.selected
				background-color: var(--clr-input-primary-bg)
				color: var(--clr-input-primary-fg)
			.c-avatar
				background-color: $clr-white
				border-radius: 50%
				padding: 1px
			.name
				ellipsis()
</style>

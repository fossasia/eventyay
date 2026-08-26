<template lang="pug">
bunt-input-outline-container.c-chat-input
	.editor(ref="editorRef")
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
				.user(v-for="(option, index) of autocomplete.options", :key="option.id", :class="{selected: index === autocomplete.selected}", :title="option.profile.display_name", @mouseover="selectMention(index)", @click.stop="handleMention")
					avatar(:user="option", :size="24")
					.name {{ option.profile.display_name }}
				button.load-more(v-if="autocomplete.nextPage", type="button", :disabled="autocomplete.loading", @click.stop="loadMoreMentionResults")
					bunt-progress-circular(v-if="autocomplete.loading", size="small")
					template(v-else) {{ $t('ChatInput:load-more:label') }}
			bunt-progress-circular(v-else, size="large", :page="true")
</template>
<script>
/* global ENV_DEVELOPMENT */
// TODO
// - parse ascii emoticons ;)
// - parse colon emoji :+1:
// - add scrollbar when overflowing parent
import { markRaw } from 'vue'
import { Editor, Node, Extension, mergeAttributes } from '@tiptap/core'
import Document from '@tiptap/extension-document'
import Paragraph from '@tiptap/extension-paragraph'
import Text from '@tiptap/extension-text'
import History from '@tiptap/extension-history'
import Placeholder from '@tiptap/extension-placeholder'
import EmojiRegex from 'emoji-regex'
import api from 'lib/api'
import { nativeToUrl } from 'lib/emoji'
import Avatar from 'components/Avatar'
import EmojiPickerButton from 'components/EmojiPickerButton'
import UploadButton from 'components/UploadButton'

// ─── Emoji regex helpers ───────────────────────────────────────────────────
const emojiRegex = EmojiRegex()
const splitEmojiRegex = new RegExp(
	`(${emojiRegex.source})`,
	emojiRegex.flags.includes('g') ? emojiRegex.flags : `${emojiRegex.flags}g`,
)

// ─── Custom Tiptap node: inline emoji image ────────────────────────────────
const EmojiNode = Node.create({
	name: 'emoji',
	group: 'inline',
	inline: true,
	atom: true,
	addAttributes () {
		return {
			native: { default: null },
		}
	},
	parseHTML () {
		return [{ tag: 'img[data-emoji]', getAttrs: node => ({ native: node.getAttribute('data-emoji') }) }]
	},
	renderHTML ({ node, HTMLAttributes }) {
		return ['img', mergeAttributes(HTMLAttributes, {
			class: 'emoji',
			src: nativeToUrl(node.attrs.native),
			alt: node.attrs.native,
			'data-emoji': node.attrs.native,
		})]
	},
})

// ─── Custom Tiptap node: inline mention ────────────────────────────────────
const MentionNode = Node.create({
	name: 'mention',
	group: 'inline',
	inline: true,
	atom: true,
	addAttributes () {
		return {
			id: { default: null },
			name: { default: null },
		}
	},
	parseHTML () {
		return [{ tag: 'span[data-mention]', getAttrs: node => ({ id: node.getAttribute('data-id'), name: node.getAttribute('data-name') }) }]
	},
	renderHTML ({ node, HTMLAttributes }) {
		return ['span', mergeAttributes(HTMLAttributes, {
			class: 'mention',
			'data-id': node.attrs.id,
			'data-name': node.attrs.name,
			'data-mention': 'true',
		}), ['span', {}, '@' + node.attrs.name]]
	},
})

// ─── Autocomplete-aware mention boundary detection ─────────────────────────
const MENTION_BOUNDARIES = new Set([' ', '\n', '\t', '(', '[', '{', '<', '.', ',', ';', ':', '!', '?', '\'', '"', '`'])
const MENTION_SEARCH_STOP_CHARS = new Set(['(', '[', '{', '<', '.', ',', ';', ':', '!', '?', '\'', '"', '`', '@'])
const MENTION_SEARCH_DEBOUNCE_MS = 250

function getMentionMatch (text) {
	let index = text.length - 1
	while (index >= 0 && !MENTION_SEARCH_STOP_CHARS.has(text[index])) {
		index -= 1
	}
	if (index < 0 || text[index] !== '@') return null
	if (index > 0 && !MENTION_BOUNDARIES.has(text[index - 1])) return null
	return {
		index,
		search: text.slice(index + 1),
	}
}

export default {
	components: { Avatar, EmojiPickerButton, UploadButton },
	emits: ['send'],
	props: {
		message: Object, // initialize with existing message to edit
	},
	data () {
		return {
			files: [],
			uploading: false,
			autocomplete: null,
			autocompleteSearchSequence: 0,
			autocompleteSearchTimeout: null,
			autocompleteUpdateTimeout: null,
		}
	},
	computed: {
		autocompleteCoordinates () {
			if (!this.autocomplete?.fromPos) return null
			try {
				const coords = this.editor.view.coordsAtPos(this.autocomplete.fromPos)
				const editorRect = this.$refs.editorRef.getBoundingClientRect()
				return {
					left: coords.left - Math.max(0, 240 - (editorRect.width + 60 - (coords.left - editorRect.x))) + 'px',
					bottom: window.innerHeight - coords.top + 8 + 'px',
				}
			} catch (error) {
				console.warn('ChatInput: mention dropdown position failed', error)
				return null
			}
		},
	},
	watch: {
		'autocomplete.search' (search) {
			if (!this.autocomplete) return
			if (this.autocomplete.type === 'mention') {
				this.scheduleMentionSearch(search)
			}
		},
	},
	mounted () {
		// Build keyboard-shortcut extension with access to component methods
		const vm = this
		const ChatKeymap = Extension.create({
			name: 'chatKeymap',
			addKeyboardShortcuts () {
				return {
					'Enter': () => {
						if (vm.autocomplete) {
							if (vm.autocomplete.options?.length) {
								vm.handleMention()
								return true
							}
							vm.closeAutocomplete()
						}
						vm.send()
						return true
					},
					'Tab': () => {
						if (vm.autocomplete) {
							vm.handleMention()
							return true
						}
						return false
					},
					'ArrowUp': () => {
						if (!vm.autocomplete?.options?.length) return false
						vm.autocomplete.selected = Math.max(0, vm.autocomplete.selected - 1)
						return true
					},
					'ArrowDown': () => {
						if (!vm.autocomplete?.options?.length) return false
						vm.autocomplete.selected = Math.min(vm.autocomplete.options.length - 1, vm.autocomplete.selected + 1)
						return true
					},
					'Escape': () => {
						if (!vm.autocomplete) return false
						vm.closeAutocomplete()
						return true
					},
				}
			},
		})

		this.editor = markRaw(new Editor({
			element: this.$refs.editorRef,
			extensions: [
				Document,
				Paragraph,
				Text,
				History,
				EmojiNode,
				MentionNode,
				ChatKeymap,
				Placeholder.configure({
					placeholder: this.$t('ChatInput:input:placeholder'),
				}),
			],
			editorProps: {
				attributes: {
					class: 'chat-prosemirror',
				},
			},
			onUpdate: () => {
				window.clearTimeout(this.autocompleteUpdateTimeout)
				this.autocompleteUpdateTimeout = window.setTimeout(this.updateAutocomplete, 0)
			},
			onSelectionUpdate: () => {
				this.updateAutocomplete()
			},
		}))

		// Pre-populate when editing an existing message
		if (this.message) {
			const body = this.message.content?.body || ''
			if (body) {
				this.editor.commands.setContent(this.parseMessageBody(body), false)
			}
			if (this.message.content?.files?.length > 0) {
				this.files = this.message.content.files
			}
		}
	},
	unmounted () {
		window.clearTimeout(this.autocompleteSearchTimeout)
		window.clearTimeout(this.autocompleteUpdateTimeout)
		this.editor?.destroy()
		this.editor = null
	},
	methods: {
		// ── Parse a plain-text message body (with native emoji) into Tiptap JSON
		parseMessageBody (text) {
			if (!text) return { type: 'doc', content: [{ type: 'paragraph' }] }
			emojiRegex.lastIndex = 0
			const parts = text.split(splitEmojiRegex)
			const nodes = parts.flatMap(part => {
				if (!part) return []
				emojiRegex.lastIndex = 0
				if (emojiRegex.test(part)) {
					return [{ type: 'emoji', attrs: { native: part } }]
				}
				return [{ type: 'text', text: part }]
			})
			return {
				type: 'doc',
				content: [{ type: 'paragraph', content: nodes.length ? nodes : undefined }],
			}
		},

		// ── Walk the Tiptap document JSON and rebuild the plain-text body for sending
		serializeContent () {
			const json = this.editor.getJSON()
			let text = ''
			const traverse = (nodes) => {
				for (const node of (nodes || [])) {
					if (node.type === 'text') {
						text += node.text || ''
					} else if (node.type === 'emoji') {
						text += node.attrs?.native || ''
					} else if (node.type === 'mention') {
						text += '@' + (node.attrs?.id || '')
					} else if (node.content) {
						traverse(node.content)
					}
					if (node.type === 'paragraph') {
						text += '\n'
					}
				}
			}
			traverse(json.content)
			return text.trim()
		},

		// ── Autocomplete: scan text before cursor for @mention pattern
		updateAutocomplete () {
			if (!this.editor) return
			const { state } = this.editor
			const { selection } = state
			if (!selection.empty) { this.autocomplete = null; return }

			const { from } = selection
			const $from = state.doc.resolve(from)
			const paragraphStart = $from.start()

			// Build text before cursor, tracking doc positions of each char
			let textBeforeCaret = ''
			const posMap = [] // posMap[i] = doc position of char at string index i

			state.doc.nodesBetween(paragraphStart, from, (node, pos) => {
				if (node.isText) {
					const sliceEnd = Math.min(pos + node.nodeSize, from)
					const slice = node.text.slice(0, sliceEnd - pos)
					for (let i = 0; i < slice.length; i++) {
						posMap.push(pos + i)
						textBeforeCaret += slice[i]
					}
				}
				// Atom nodes (emoji/mention) contribute no chars → skipped
			})

			const mentionMatch = getMentionMatch(textBeforeCaret)
			if (mentionMatch) {
				const atDocPos = posMap[mentionMatch.index] ?? from
				if (!this.autocomplete || this.autocomplete.type !== 'mention') {
					this.autocomplete = {
						type: 'mention',
						search: mentionMatch.search,
						fromPos: atDocPos,
						options: null,
						selected: 0,
						loading: false,
						nextPage: null,
					}
				} else {
					this.autocomplete.search = mentionMatch.search
					this.autocomplete.fromPos = atDocPos
				}
			} else {
				this.autocomplete = null
			}
		},

		scheduleMentionSearch (search) {
			window.clearTimeout(this.autocompleteSearchTimeout)
			const sequence = ++this.autocompleteSearchSequence
			this.autocompleteSearchTimeout = window.setTimeout(() => {
				this.loadMentionResults(search, 1, sequence)
			}, MENTION_SEARCH_DEBOUNCE_MS)
		},

		async loadMentionResults (search, page, sequence = ++this.autocompleteSearchSequence) {
			if (!this.autocomplete || this.autocomplete.type !== 'mention' || this.autocomplete.search !== search) return
			this.autocomplete.loading = true
			try {
				const newPage = await api.call('user.list.search', { search_term: search, page, include_banned: false })
				if (sequence !== this.autocompleteSearchSequence || !this.autocomplete || this.autocomplete.search !== search) return
				this.autocomplete.options = page > 1
					? [...(this.autocomplete.options || []), ...newPage.results]
					: newPage.results
				if (page === 1) {
					this.autocomplete.selected = 0
				}
				this.autocomplete.nextPage = newPage.isLastPage ? null : page + 1
			} finally {
				if (this.autocomplete && sequence === this.autocompleteSearchSequence) {
					this.autocomplete.loading = false
				}
			}
		},

		loadMoreMentionResults () {
			if (!this.autocomplete?.nextPage || this.autocomplete.loading) return
			this.loadMentionResults(this.autocomplete.search, this.autocomplete.nextPage)
		},

		closeAutocomplete () {
			window.clearTimeout(this.autocompleteSearchTimeout)
			this.autocompleteSearchSequence++
			this.editor?.commands.focus()
			this.autocomplete = null
		},

		selectMention (index) {
			if (!this.autocomplete?.options?.length) return
			this.autocomplete.selected = index
		},

		handleMention () {
			if (!this.autocomplete?.options?.length) return true
			const user = this.autocomplete.options[this.autocomplete.selected]
			if (!user) return true

			const { from } = this.editor.state.selection
			const fromPos = this.autocomplete.fromPos

			this.editor.chain()
				.focus()
				.deleteRange({ from: fromPos, to: from })
				.insertContentAt(fromPos, [
					{ type: 'mention', attrs: { id: user.id, name: user.profile.display_name } },
					{ type: 'text', text: ' ' },
				])
				.run()

			window.clearTimeout(this.autocompleteSearchTimeout)
			this.autocompleteSearchSequence++
			this.autocomplete = null
		},

		send () {
			const text = this.serializeContent()
			if (!text && this.files.length === 0) return
			if (this.files.length > 0) {
				this.$emit('send', {
					type: 'files',
					files: this.files.filter(file => file),
					body: text,
				})
				this.files = []
			} else {
				this.$emit('send', {
					type: 'text',
					body: text,
				})
			}
			this.editor?.commands.clearContent()
		},

		async attachFiles (event) {
			const files = Array.from(event.target.files)
			if (files.length === 0) return

			this.uploading = true
			const requests = files.map(file => api.uploadFilePromise(file, file.name))
			const fileInfos = (await Promise.all(requests)).map((response, i) => {
				if (response.error) {
					return null
				} else {
					return {
						url: response.url,
						mimeType: files[i].type,
						name: files[i].name,
					}
				}
			})
			this.files.push(...fileInfos)
			this.uploading = false
			event.target.value = ''
		},

		addEmoji (emoji) {
			this.editor?.chain().focus().insertContent({
				type: 'emoji',
				attrs: { native: emoji.native },
			}).run()
		},

		removeFile (file) {
			const index = this.files.indexOf(file)
			if (index > -1) {
				this.files.splice(index, 1)
			}
		},
	},
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

	// ── ProseMirror chat editor ──────────────────────────────────────────
	.editor
		line-height: 22px // collapse wrapper to content height

	.chat-prosemirror
		font-size: 16px
		line-height: 22px
		min-height: 22px
		margin: 0
		padding: 0
		outline: none
		overflow-wrap: break-word
		white-space: pre-wrap
		p
			font-size: 16px
			line-height: 22px
			overflow-wrap: break-word
			margin: 0
			padding: 0
		// Placeholder
		&.ProseMirror-focused p.is-editor-empty:first-child::before,
		p.is-editor-empty:first-child::before
			content: attr(data-placeholder)
			float: left
			color: var(--clr-text-secondary)
			pointer-events: none
			height: 0
		.emoji
			margin: 0 2px
			line-height: 22px
			width: 20px
			height: 20px
			vertical-align: middle
			display: inline-block
		.mention span
			display: inline-block
			background-color: var(--clr-input-primary-bg)
			color: var(--clr-input-primary-fg)
			font-weight: 500
			border-radius: 4px
			padding: 0 2px
			margin: 0 2px

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
		height: calc(32px * 20)
		overflow-y: auto
		.user
			display: flex
			height: 32px
			flex-shrink: 0
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
		.load-more
			height: 32px
			flex-shrink: 0
			border: 0
			border-top: border-separator()
			background: $clr-white
			color: $clr-primary
			cursor: pointer
			font-family: $font-stack
			font-size: 14px
			font-weight: 500
			&:disabled
				cursor: default
</style>

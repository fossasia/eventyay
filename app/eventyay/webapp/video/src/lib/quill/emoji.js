import Quill from 'quill'
import { nativeToUrl as nativeEmojiToUrl, objectToCssString } from 'lib/emoji'

const Embed = Quill.import('blots/embed')

class EmojiBlot extends Embed {
	static create(value) {
		const node = super.create()
		node.src = nativeEmojiToUrl(value)
		node.alt = value
		node.dataset.emoji = value
		return node
	}

	static value(node) {
		return node.dataset.emoji
	}
}

EmojiBlot.blotName = 'emoji'
EmojiBlot.className = 'emoji'
EmojiBlot.tagName = 'img'

Quill.register(EmojiBlot)

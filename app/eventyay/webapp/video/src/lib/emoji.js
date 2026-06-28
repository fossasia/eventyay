import data from '@emoji-mart/data'
import EmojiRegex from 'emoji-regex'
import MarkdownIt from 'markdown-it'

const nativeEmojiIndex = new Map()
for (const [id, emoji] of Object.entries(data.emojis)) {
	for (const skin of emoji.skins || []) {
		if (skin.native) {
			nativeEmojiIndex.set(skin.native, {
				...emoji,
				id,
				short_names: [id],
			})
		}
	}
}

const emojiRegex = EmojiRegex()
const splitEmojiRegex = new RegExp(`(${emojiRegex.source})`, 'g')
const startsWithEmojiRegex = new RegExp(`^${emojiRegex.source}`)

export function objectToCssString(object) {
	return Object.entries(object).map(([key, value]) => `${key}:${value}`).join(';')
}

export function startsWithEmoji(string) {
	return startsWithEmojiRegex.test(string)
}

export function nativeToOps(string) {
	return string.split(splitEmojiRegex).map(match => {
		if (emojiRegex.test(match)) {
			return {insert: {emoji: match}}
		} else {
			return {insert: match}
		}
	})
}

export function getEmojiDataFromNative(native) {
	return nativeEmojiIndex.get(native) || {short_names: [native]}
}

export function nativeToUrl(unicodeEmoji) {
	let codepoints = Array.from(unicodeEmoji).map(c => c.codePointAt(0).toString(16))
	if (codepoints.length === 2 && codepoints[codepoints.length - 1] === 'fe0f') {
		codepoints = codepoints.slice(0, -1)
	}
	return `https://cdn.jsdelivr.net/gh/jdecked/twemoji@latest/assets/svg/${codepoints.join('-')}.svg`
}

export function nativeToStyle(unicodeEmoji) {
	return {'background-image': `url(${nativeToUrl(unicodeEmoji)})`}
}

export function markdownEmoji(md) {
	function splitTextToken(text, Token) {
		let token
		let lastPos = 0
		const tokens = []

		text.replace(emojiRegex, function(match, offset, src) {
			if (offset > lastPos) {
				token = new Token('text', '', 0)
				token.content = text.slice(lastPos, offset)
				tokens.push(token)
			}

			token = new Token('emoji', '', 0)
			token.content = match
			tokens.push(token)
			lastPos = offset + match.length
		})

		if (lastPos < text.length) {
			token = new Token('text', '', 0)
			token.content = text.slice(lastPos)
			tokens.push(token)
		}

		return tokens
	}
	md.core.ruler.push('emoji', function emojiReplace(state) {
		let autolinkLevel = 0

		for (const blockToken of state.tokens) {
			if (blockToken.type !== 'inline') continue
			let tokens = blockToken.children

			for (let i = tokens.length - 1; i >= 0; i--) {
				const token = tokens[i]

				if (token.type === 'link_open' || token.type === 'link_close') {
					if (token.info === 'auto') autolinkLevel -= token.nesting
				}

				if (token.type === 'text' && autolinkLevel === 0 && emojiRegex.test(token.content)) {
					blockToken.children = tokens = md.utils.arrayReplaceAt(
						tokens, i, splitTextToken(token.content, state.Token)
					)
				}
			}
		}
	})
	md.renderer.rules.emoji = (tokens, idx) => {
		const isFirst = idx === 0
		const needsSpace = tokens[idx + 1] && !tokens[idx + 1].content.startsWith(' ')
		const emoji = tokens[idx].content
		return `<img class="emoji${isFirst && needsSpace ? ' needs-space' : ''}" src="${nativeToUrl(emoji)}" alt="${emoji}">`
	}
}

const markdownIt = MarkdownIt('zero', {})
markdownIt.use(markdownEmoji)

export function emojifyString(input) {
	if (input == null) return ''
	let text = input
	if (typeof text !== 'string') {
		if (typeof input.name === 'string') text = input.name
		else if (typeof input.title === 'string') text = input.title
		else if (typeof input.text === 'string') text = input.text
		else {
			return ''
		}
	}
	return markdownIt.renderInline(text)
}

export const emojiPlugin = {
	install(app) {
		app.config.globalProperties.$emojify = emojifyString
	}
}

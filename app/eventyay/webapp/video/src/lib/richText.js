import DOMPurify from 'dompurify'

const ALLOWED_TAGS = [
	'a', 'abbr', 'acronym', 'b', 'blockquote', 'br',
	'code', 'del', 'div', 'em',
	'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
	'hr', 'i',
	'li', 'ol', 'p', 'pre',
	'span', 'strong',
	'sub', 'sup',
	'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td',
	'ul'
]

const ALLOWED_ATTR = [
	'class',
	'colspan', 'rowspan',
	'href', 'rel', 'target', 'title',
	'width', 'align',
	'style'
]

const ALLOWED_STYLE_TAGS = new Set(['div', 'p', 'span'])
const ALLOWED_STYLE_PROPERTIES = new Set(['color', 'background-color', 'text-decoration'])

let dompurifyHooksInstalled = false

function installDomPurifyHooks() {
	if (dompurifyHooksInstalled) return
	dompurifyHooksInstalled = true

	DOMPurify.addHook('uponSanitizeAttribute', (node, data) => {
		if (data.attrName !== 'style') return
		const tagName = String(node.nodeName || '').toLowerCase()
		if (!ALLOWED_STYLE_TAGS.has(tagName)) {
			data.keepAttr = false
			return
		}

		const raw = String(data.attrValue || '')
		const sanitized = raw
			.split(';')
			.map((decl) => decl.trim())
			.filter(Boolean)
			.map((decl) => {
				const idx = decl.indexOf(':')
				if (idx <= 0) return null
				const prop = decl.slice(0, idx).trim().toLowerCase()
				const value = decl.slice(idx + 1).trim()
				if (!ALLOWED_STYLE_PROPERTIES.has(prop)) return null
				if (!value) return null
				return `${prop}: ${value}`
			})
			.filter(Boolean)
			.join('; ')

		if (!sanitized) {
			data.keepAttr = false
			return
		}
		data.attrValue = sanitized
	})
}

export function looksLikeHtml(value) {
	if (typeof value !== 'string') return false
	const trimmed = value.trim()
	if (!trimmed) return false
	return /<\s*\/?\s*[a-z][\s\S]*>/i.test(trimmed)
}

export function sanitizeHtml(html) {
	if (typeof html !== 'string') return ''
	installDomPurifyHooks()
	return DOMPurify.sanitize(html, {
		ALLOWED_TAGS,
		ALLOWED_ATTR,
		USE_PROFILES: { html: true },
		FORBID_TAGS: ['script', 'style'],
		FORBID_ATTR: ['srcset', 'onerror', 'onload']
	})
}

function normalizeDeltaOps(input) {
	if (!input) return null
	if (Array.isArray(input)) return input
	if (typeof input === 'object') {
		if (Array.isArray(input.ops)) return input.ops
	}
	return null
}

function escapeHtml(text) {
	return String(text)
		.replaceAll('&', '&amp;')
		.replaceAll('<', '&lt;')
		.replaceAll('>', '&gt;')
}

function escapeAttr(value) {
	return String(value)
		.replaceAll('&', '&amp;')
		.replaceAll('"', '&quot;')
		.replaceAll('<', '&lt;')
		.replaceAll('>', '&gt;')
}

function renderInlineText(text, attrs) {
	let html = escapeHtml(text)
	if (!attrs) return html

	// Inline formatting
	if (attrs.link) {
		const href = escapeAttr(attrs.link)
		html = `<a href="${href}" target="_blank" rel="noopener noreferrer">${html}</a>`
	}
	if (attrs.bold) html = `<strong>${html}</strong>`
	if (attrs.italic) html = `<em>${html}</em>`
	if (attrs.underline) html = `<span style="text-decoration: underline">${html}</span>`
	if (attrs.strike) html = `<del>${html}</del>`
	if (attrs.code) html = `<code>${html}</code>`
	if (attrs.script === 'sub') html = `<sub>${html}</sub>`
	if (attrs.script === 'super') html = `<sup>${html}</sup>`

	return html
}

function lineType(attrs) {
	if (!attrs) return { type: 'p' }
	if (attrs['code-block']) return { type: 'code' }
	if (attrs.header) return { type: 'header', level: attrs.header }
	if (attrs.list === 'bullet') return { type: 'list', listType: 'ul' }
	if (attrs.list === 'ordered') return { type: 'list', listType: 'ol' }
	if (attrs.blockquote) return { type: 'blockquote' }
	return { type: 'p' }
}

function deltaOpsToLines(ops) {
	const lines = []
	let currentInlines = []

	const pushLine = (attrs) => {
		lines.push({ inlines: currentInlines, attrs: attrs || {} })
		currentInlines = []
	}

	for (const op of ops) {
		if (!op || op.insert == null) continue
		const attrs = op.attributes || null
		const insert = op.insert
		if (typeof insert === 'string') {
			const parts = insert.split('\n')
			for (let i = 0; i < parts.length; i++) {
				const part = parts[i]
				if (part) {
					currentInlines.push({ type: 'text', text: part, attrs })
				}
				// Newline terminates a line. Attributes on the newline represent line formatting.
				if (i < parts.length - 1) {
					pushLine(attrs)
				}
			}
			continue
		}

		if (typeof insert === 'object') {
			if (typeof insert.image === 'string') {
				currentInlines.push({ type: 'image', src: insert.image })
				continue
			}
			if (typeof insert.video === 'string') {
				currentInlines.push({ type: 'video', url: insert.video })
				continue
			}
			if (typeof insert.emoji === 'string') {
				currentInlines.push({ type: 'text', text: insert.emoji, attrs: null })
				continue
			}
			if (insert.mention && typeof insert.mention === 'object') {
				const name = insert.mention.name || insert.mention.id || ''
				currentInlines.push({ type: 'mention', name: String(name) })
				continue
			}
		}
	}

	// Deltas usually end with a newline; if not, keep trailing content.
	if (currentInlines.length > 0) {
		pushLine({})
	}

	return lines
}

function renderLineInlines(inlines) {
	return (inlines || []).map((token) => {
		if (token.type === 'text') {
			return renderInlineText(token.text, token.attrs)
		}
		if (token.type === 'image') {
			const safeUrl = escapeAttr(token.src)
			return `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer">${safeUrl}</a>`
		}
		if (token.type === 'video') {
			const safeUrl = escapeAttr(token.url)
			return `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer">${safeUrl}</a>`
		}
		if (token.type === 'mention') {
			return `<span class="mention">@${escapeHtml(token.name)}</span>`
		}
		return ''
	}).join('')
}

function renderDeltaLinesToHtml(lines) {
	let html = ''
	let openList = null
	let inBlockquote = false
	let inCodeBlock = false
	let codeBuffer = []

	const closeList = () => {
		if (openList) {
			html += `</${openList}>`
			openList = null
		}
	}
	const closeBlockquote = () => {
		if (inBlockquote) {
			html += '</blockquote>'
			inBlockquote = false
		}
	}
	const flushCodeBlock = () => {
		if (!inCodeBlock) return
		html += `<pre><code>${escapeHtml(codeBuffer.join('\n'))}</code></pre>`
		codeBuffer = []
		inCodeBlock = false
	}

	for (const line of lines) {
		const lt = lineType(line.attrs)

		if (lt.type !== 'code') {
			flushCodeBlock()
		}
		if (lt.type !== 'list') {
			closeList()
		}
		if (lt.type !== 'blockquote') {
			closeBlockquote()
		}

		if (lt.type === 'code') {
			inCodeBlock = true
			// Keep code blocks as plain text for safety.
			codeBuffer.push((line.inlines || []).map((t) => (t.type === 'text' ? String(t.text) : '')).join(''))
			continue
		}

		if (lt.type === 'list') {
			if (openList !== lt.listType) {
				closeList()
				openList = lt.listType
				html += `<${openList}>`
			}
			html += `<li>${renderLineInlines(line.inlines)}</li>`
			continue
		}

		if (lt.type === 'blockquote') {
			if (!inBlockquote) {
				inBlockquote = true
				html += '<blockquote>'
			}
			html += `<p>${renderLineInlines(line.inlines)}</p>`
			continue
		}

		if (lt.type === 'header') {
			const level = Math.min(6, Math.max(1, Number(lt.level) || 1))
			html += `<h${level}>${renderLineInlines(line.inlines)}</h${level}>`
			continue
		}

		// Default paragraph
		html += `<p>${renderLineInlines(line.inlines)}</p>`
	}

	flushCodeBlock()
	closeList()
	closeBlockquote()
	return html
}

export function deltaToHtml(delta) {
	const ops = normalizeDeltaOps(delta)
	if (!ops) return ''
	const lines = deltaOpsToLines(ops)
	return renderDeltaLinesToHtml(lines)
}

export function richTextToHtml(input) {
	if (input == null) return ''
	if (typeof input === 'string') return input
	return deltaToHtml(input)
}

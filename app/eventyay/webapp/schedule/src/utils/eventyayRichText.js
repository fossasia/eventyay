/**
 * Schedule rich text (markdown + allowlisted HTML). Keep tags, per-tag attrs, and URI rules aligned
 * with `eventyay.base.templatetags.rich_text`. No safelink or target/rel like Django; DOMPurify uses a
 * global ALLOWED_ATTR union plus uponSanitizeAttribute for per-tag enforcement.
 */
import MarkdownIt from 'markdown-it'
import createDOMPurify from 'dompurify'
import multimdTable from 'markdown-it-multimd-table'

/** @type {string[]} */
export const EVENTYAY_RICH_TEXT_ALLOWED_TAGS = [
	'a',
	'abbr',
	'acronym',
	'b',
	'blockquote',
	'br',
	'code',
	'del',
	'div',
	'em',
	'hr',
	'i',
	'li',
	'ol',
	'strong',
	'u',
	'ul',
	'p',
	'pre',
	'span',
	'table',
	'tbody',
	'thead',
	'tr',
	'td',
	'th',
	'h1',
	'h2',
	'h3',
	'h4',
	'h5',
	'h6',
]

/** @type {Record<string, string[]>} Matches rich_text.ALLOWED_ATTRIBUTES */
export const EVENTYAY_RICH_TEXT_ALLOWED_ATTRIBUTES_BY_TAG = {
	a: ['href', 'title', 'class'],
	abbr: ['title'],
	acronym: ['title'],
	table: ['width'],
	td: ['width', 'align'],
	div: ['class'],
	p: ['class'],
	span: ['class', 'title'],
}

/** Union of attribute names; required by DOMPurify before per-tag hook runs */
const EVENTYAY_RICH_TEXT_ALLOWED_ATTR = [
	...new Set(Object.values(EVENTYAY_RICH_TEXT_ALLOWED_ATTRIBUTES_BY_TAG).flat()),
]


/** Browser: markdown + raw HTML, then DOMPurify. Non-browser: markdown only (no embedded HTML) to avoid XSS without a DOM. */
const markdownItWithHtml = new MarkdownIt({
	html: true,
	linkify: true,
	breaks: true,
}).use(multimdTable)

const markdownItNoHtml = new MarkdownIt({
	html: false,
	linkify: true,
	breaks: true,
}).use(multimdTable)

const PURIFY_CONFIG = {
	ALLOWED_TAGS: EVENTYAY_RICH_TEXT_ALLOWED_TAGS,
	ALLOWED_ATTR: EVENTYAY_RICH_TEXT_ALLOWED_ATTR,
	ALLOW_DATA_ATTR: false,
	ALLOW_UNKNOWN_PROTOCOLS: false,
	ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto|tel):[\s\S]*|(?![a-z][a-z0-9+.-]*:)[\s\S]*)$/i,
}

/** @type {ReturnType<typeof createDOMPurify> | null} */
let domPurifyInstance = null
let domPurifyPerTagHookInstalled = false
let domPurifyExternalLinkHookInstalled = false

function installPerTagAttributeHook (purify) {
	if (domPurifyPerTagHookInstalled) return
	domPurifyPerTagHookInstalled = true
	purify.addHook('uponSanitizeAttribute', (node, data) => {
		const tag = node.tagName.toLowerCase()
		const attr = data.attrName.toLowerCase()
		const allowed = EVENTYAY_RICH_TEXT_ALLOWED_ATTRIBUTES_BY_TAG[tag]
		if (!allowed?.includes(attr)) {
			data.keepAttr = false
		}
	})
}

function installExternalLinkHook (purify) {
	if (domPurifyExternalLinkHookInstalled) return
	domPurifyExternalLinkHookInstalled = true
	purify.addHook('afterSanitizeAttributes', (node) => {
		if (!node || node.tagName !== 'A') return
		const href = node.getAttribute('href')
		if (href && /^https?:\/\//i.test(href)) {
			node.setAttribute('target', '_blank')
			const existing = (node.getAttribute('rel') || '').split(/\s+/).filter(Boolean)
			const relSet = new Set(existing)
			relSet.add('noopener')
			relSet.add('noreferrer')
			relSet.add('nofollow')
			node.setAttribute('rel', Array.from(relSet).join(' '))
		}
	})
}

function getDomPurify () {
	if (typeof window === 'undefined') return null
	if (!domPurifyInstance) {
		domPurifyInstance = createDOMPurify(window)
		installPerTagAttributeHook(domPurifyInstance)
		installExternalLinkHook(domPurifyInstance)
	}
	return domPurifyInstance
}

/**
 * @param {string} source
 * @returns {string}
 */
export function renderEventyayRichText (source) {
	if (!source) return ''
	const md = typeof window === 'undefined' ? markdownItNoHtml : markdownItWithHtml
	let raw
	try {
		raw = md.render(String(source))
	} catch {
		return ''
	}
	const purify = getDomPurify()
	if (!purify) return raw
	return purify.sanitize(raw, PURIFY_CONFIG)
}

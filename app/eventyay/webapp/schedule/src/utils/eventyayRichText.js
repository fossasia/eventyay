/**
 * Rich text for public schedule UI: markdown + allowlisted HTML.
 *
 * Keep allowlists and URI protocol policy in sync with
 * `eventyay.base.templatetags.rich_text` (ALLOWED_TAGS, ALLOWED_ATTRIBUTES, ALLOWED_PROTOCOLS).
 *
 * Unlike the Django renderer, this path does not run bleach’s linkify `safelink_callback` (no safelink
 * redirect URLs) and does not add `target="_blank"` / `rel="noopener"` to external links. Schedule UI
 * should match server-rendered snippets where possible, but treat link behavior as intentionally
 * different unless we add a client-side post-pass.
 *
 * Attributes: DOMPurify only supports a global ALLOWED_ATTR list; we use that union for the first pass,
 * then enforce per-tag rules in uponSanitizeAttribute (same semantics as bleach attributes=).
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

/**
 * Mirrors eventyay.base.templatetags.rich_text.ALLOWED_ATTRIBUTES (tags omitted → no attributes).
 * @type {Record<string, string[]>}
 */
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
	ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto|tel):|[^a-z]|[a-z+.-]+(?:[^a-z+.-:]|$))/i,
}

/** @type {ReturnType<typeof createDOMPurify> | null} */
let domPurifyInstance = null
let domPurifyPerTagHookInstalled = false

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

function getDomPurify () {
	if (typeof window === 'undefined') return null
	if (!domPurifyInstance) {
		domPurifyInstance = createDOMPurify(window)
		installPerTagAttributeHook(domPurifyInstance)
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

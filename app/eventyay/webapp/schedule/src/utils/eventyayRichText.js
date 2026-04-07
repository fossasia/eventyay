/**
 * Rich text for public schedule UI: markdown + allowlisted HTML.
 * Keep in sync with eventyay.base.templatetags.rich_text (ALLOWED_TAGS / ALLOWED_ATTRIBUTES / protocols).
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

/** Union of attribute names allowed on at least one tag in rich_text.py */
const EVENTYAY_RICH_TEXT_ALLOWED_ATTR = ['href', 'title', 'class', 'width', 'align']

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
	ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel):|[^a-z]|[a-z+.-]+(?:[^a-z+.-:]|$))/i,
}

/** @type {ReturnType<typeof createDOMPurify> | null} */
let domPurifyInstance = null

function getDomPurify () {
	if (typeof window === 'undefined') return null
	if (!domPurifyInstance) domPurifyInstance = createDOMPurify(window)
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

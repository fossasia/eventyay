import {usableTranslations} from './catalog.js'
import {parsePo} from './po.js'

const GETTEXT_DOMAINS = ['video', 'schedule', 'schedule-editor']

export function gettextFilePath(id) {
	return String(id || '').split('?')[0].split('#')[0].replaceAll('\\', '/')
}

export function createGettextPlugin(domain) {
	const domains = GETTEXT_DOMAINS.includes(domain) ? GETTEXT_DOMAINS : [...GETTEXT_DOMAINS, domain].filter(Boolean)
	const fileRegex = new RegExp(`locale/([^/]+)/LC_MESSAGES/(?:${domains.join('|')})\\.po$`)
	return {
		name: `load-${domain}-gettext`,
		enforce: 'pre',
		transform(src, id) {
			const match = gettextFilePath(id).match(fileRegex)
			if (!match) return null
			const trimmed = String(src || '').trimStart()
			if (trimmed.startsWith('export ') || trimmed.startsWith('import ') || !trimmed.includes('msgid ')) {
				return null
			}
			const lang = match[1]
			const filtered = usableTranslations(parsePo(src), lang)
			return {
				code: `export default ${JSON.stringify(filtered)}`,
				map: {mappings: ''},
			}
		},
	}
}

import {createRequire} from 'node:module'
import path from 'node:path'
import {pathToFileURL} from 'node:url'
import {usableTranslations} from './catalog.js'

async function loadGettextConv(appRoot) {
	const require = createRequire(path.join(appRoot, 'package.json'))
	const resolved = require.resolve('i18next-conv')
	return import(pathToFileURL(resolved).href)
}

export function createGettextPlugin(domain, appRoot = process.cwd()) {
	// Video embeds schedule components, so any app may import more than one domain.
	const domains = ['video', 'schedule', 'schedule-editor']
	if (domain && !domains.includes(domain)) domains.push(domain)
	const fileRegex = new RegExp(`locale/([^/]+)/LC_MESSAGES/(?:${domains.join('|')})\\.po$`)
	let convPromise
	return {
		name: `load-${domain}-gettext`,
		enforce: 'pre',
		async transform(src, id) {
			if (!fileRegex.test(id)) return null
			if (!convPromise) convPromise = loadGettextConv(appRoot)
			const {gettextToI18next} = await convPromise
			const lang = id.match(fileRegex)[1]
			const sanitized = src.replaceAll('#~|', '#~#|')
			const mapped = await gettextToI18next(lang, sanitized)
			const translations = JSON.parse(mapped)
			const filtered = usableTranslations(translations, lang)
			return {
				code: `export default ${JSON.stringify(filtered)}`,
				map: {mappings: ''},
			}
		},
	}
}

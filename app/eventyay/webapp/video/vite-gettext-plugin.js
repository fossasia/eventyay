import { gettextToI18next } from 'i18next-conv'
import { usableTranslations } from './src/i18n-catalog.js'

const fileRegex = /locale\/(.*)\/LC_MESSAGES\/video\.po$/

export default function loadGettext() {
	return {
		name: 'load-video-gettext',
		async transform(src, id) {
			if (!fileRegex.test(id)) return null

			const lang = id.match(fileRegex)[1]
			// gettext-parser does not support #~| (see smhg/gettext-parser#79)
			const sanitized = src.replaceAll('#~|', '#~#|')
			const mapped = await gettextToI18next(lang, sanitized)
			const translations = JSON.parse(mapped)
			const filtered = usableTranslations(translations, lang)
			return {
				code: `export default ${JSON.stringify(filtered)}`,
				map: { mappings: '' }
			}
		}
	}
}

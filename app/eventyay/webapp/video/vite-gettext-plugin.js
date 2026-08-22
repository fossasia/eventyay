import { gettextToI18next } from 'i18next-conv'

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
			const isEnglish = lang === 'en' || lang.startsWith('en_') || lang.startsWith('en-')
			const filtered = Object.fromEntries(
				Object.entries(translations).filter(([key, value]) => {
					if (value === '' || value == null) return false
					// Untranslated gettext entries often copy msgid; keep those only for English.
					if (!isEnglish && value === key) return false
					return true
				})
			)
			return {
				code: `export default ${JSON.stringify(filtered)}`,
				map: { mappings: '' }
			}
		}
	}
}

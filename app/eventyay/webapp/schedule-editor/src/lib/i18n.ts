import i18next from 'i18next'
import moment from 'moment-timezone'
import {
	createEnglishCatalogLoader,
	isEnglishLocale,
	loadCatalogForLanguage,
	loadRawCatalog,
	toDjangoLanguage,
} from '../../../i18n/load.js'
import {createTranslate, notifyLocaleChange} from '../../../i18n/locale.js'

const localeLoaders = import.meta.glob('../../../locale/*/LC_MESSAGES/schedule-editor.po')
const momentLocaleModules = import.meta.glob('../../node_modules/moment/dist/locale/*.js')
const loadEnglishCatalog = createEnglishCatalogLoader(localeLoaders)

async function readCatalog(language: string) {
	const catalog = await loadCatalogForLanguage(localeLoaders, language, loadEnglishCatalog)
	if (!isEnglishLocale(language) && !(await loadRawCatalog(localeLoaders, language))) {
		console.warn('Missing schedule-editor.po catalog for "%s", falling back to English', language)
	}
	return catalog
}

export default async function (locale: string) {
	const lng = toDjangoLanguage(locale) || 'en'
	const english = await loadEnglishCatalog()
	const catalog = isEnglishLocale(lng) ? english : await readCatalog(lng)
	const momentLocale = lng.split('-')[0]
	await momentLocaleModules[`../../node_modules/moment/dist/locale/${momentLocale}.js`]?.()
	moment.locale(momentLocale)

	await i18next.init({
		lng,
		fallbackLng: 'en',
		preload: ['en'],
		returnEmptyString: false,
		returnNull: false,
		debug: false,
		nsSeparator: false,
		keySeparator: false,
		resources: {
			en: {translation: english},
			[lng]: {translation: catalog},
		},
	})
	notifyLocaleChange()

	const translate = createTranslate(i18next)
	return {
		install(app: {config: {globalProperties: Record<string, unknown>}}) {
			app.config.globalProperties.$i18n = i18next
			app.config.globalProperties.$t = translate
			if (typeof window !== 'undefined') {
				(window as { $t?: typeof translate }).$t = translate
			}
		},
	}
}

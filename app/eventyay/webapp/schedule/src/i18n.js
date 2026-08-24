import i18next from 'i18next'
import {
	createEnglishCatalogLoader,
	isEnglishLocale,
	loadCatalogForLanguage,
	loadRawCatalog,
	toDjangoLanguage,
} from '../../i18n/load.js'
import {createTranslate, notifyLocaleChange} from '../../i18n/locale.js'

export default i18next

const localeLoaders = import.meta.glob('../../../locale/*/LC_MESSAGES/schedule.po')
const loadEnglishCatalog = createEnglishCatalogLoader(localeLoaders)
const englishCatalog = await loadEnglishCatalog()

await i18next.init({
	lng: 'en',
	fallbackLng: 'en',
	preload: ['en'],
	returnEmptyString: false,
	returnNull: false,
	keySeparator: false,
	nsSeparator: false,
	resources: {
		en: {translation: englishCatalog},
	},
})

async function readCatalog(language) {
	const catalog = await loadCatalogForLanguage(localeLoaders, language, loadEnglishCatalog)
	if (!isEnglishLocale(language) && !(await loadRawCatalog(localeLoaders, language))) {
		console.warn('Missing schedule.po catalog for "%s", falling back to English', language)
	}
	return catalog
}

export async function changeScheduleLanguage(language) {
	const lng = toDjangoLanguage(language) || 'en'
	try {
		if (!isEnglishLocale(lng) && !i18next.hasResourceBundle(lng, 'translation')) {
			i18next.addResourceBundle(lng, 'translation', await readCatalog(lng), true, true)
		}
		await i18next.changeLanguage(isEnglishLocale(lng) ? 'en' : lng)
		notifyLocaleChange()
	} catch (error) {
		console.error('Failed to load schedule catalog for "%s"', lng, error)
		await i18next.changeLanguage('en')
		notifyLocaleChange()
	}
}

export function createI18nPlugin() {
	const translate = createTranslate(i18next)
	return {
		install(app) {
			app.config.globalProperties.$i18n = i18next
			app.config.globalProperties.$t = translate
		},
	}
}

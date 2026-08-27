import {
	createEnglishCatalogLoader,
	isEnglishLocale,
	loadCatalogForLanguage,
	loadRawCatalog,
	toDjangoLanguage,
} from './load.js'
import {createTranslate, notifyLocaleChange} from './locale.js'

export const I18N_INIT_OPTIONS = {
	fallbackLng: 'en',
	preload: ['en'],
	returnEmptyString: false,
	returnNull: false,
	keySeparator: false,
	nsSeparator: false,
}

export function localizeWithI18n(i18n, value, track = () => {}) {
	track()
	if (!value) return ''
	if (typeof value === 'string') return value
	for (const lang of i18n.languages || []) {
		if (value[lang]) return value[lang]
	}
	const django = toDjangoLanguage(i18n.language)
	if (django && value[django]) return value[django]
	if (value.en) return value.en
	return Object.values(value)[0] || ''
}

export function createGettextRuntime({
	domain,
	i18next: i18n,
	localeLoaders,
	debug = false,
	warnOnMissing = true,
	assignWindowTranslate = false,
	track = () => {},
	extraPlugins = [],
	extraInitOptions = {},
}) {
	if (!domain) throw new Error('createGettextRuntime requires a gettext domain')
	if (!i18n) throw new Error('createGettextRuntime requires an i18next instance')

	const loadEnglishCatalog = createEnglishCatalogLoader(localeLoaders)
	const translate = createTranslate(i18n, track)
	let pluginsRegistered = false

	function localize(value) {
		return localizeWithI18n(i18n, value, track)
	}

	async function readCatalog(language) {
		const catalog = await loadCatalogForLanguage(localeLoaders, language, loadEnglishCatalog)
		if (warnOnMissing && !isEnglishLocale(language) && !(await loadRawCatalog(localeLoaders, language))) {
			console.warn('Missing %s.po catalog for "%s", falling back to English', domain, language)
		}
		return catalog
	}

	function registerPlugins() {
		if (pluginsRegistered) return
		for (const plugin of extraPlugins) {
			i18n.use(plugin)
		}
		pluginsRegistered = true
	}

	async function changeLanguage(language) {
		const lng = toDjangoLanguage(language) || 'en'
		try {
			if (!isEnglishLocale(lng) && !i18n.hasResourceBundle(lng, 'translation')) {
				i18n.addResourceBundle(lng, 'translation', await readCatalog(lng), true, true)
			}
			await i18n.changeLanguage(isEnglishLocale(lng) ? 'en' : lng)
		} catch (error) {
			console.error('Failed to load %s catalog for "%s"', domain, lng, error)
			await i18n.changeLanguage('en')
		}
		notifyLocaleChange()
		return i18n.language
	}

	async function init({lng = 'en'} = {}) {
		registerPlugins()
		const language = toDjangoLanguage(lng) || 'en'
		let english = {}
		try {
			english = await loadEnglishCatalog()
		} catch (error) {
			console.error('Failed to load %s English catalog', domain, error)
		}
		if (warnOnMissing && Object.keys(localeLoaders || {}).length === 0) {
			console.warn('No %s.po locale loaders were bundled', domain)
		}
		if (!i18n.isInitialized) {
			await i18n.init({
				lng: 'en',
				debug,
				resources: {
					en: {translation: english},
				},
				...extraInitOptions,
				...I18N_INIT_OPTIONS,
			})
		}
		return changeLanguage(language)
	}

	function createPlugin() {
		return {
			install(app) {
				app.config.globalProperties.$i18n = i18n
				app.config.globalProperties.$t = translate
				app.config.globalProperties.$localize = localize
				if (assignWindowTranslate && typeof window !== 'undefined') {
					window.$t = translate
				}
			},
		}
	}

	function install(app) {
		createPlugin().install(app)
	}

	return {
		domain,
		i18n,
		translate,
		localize,
		init,
		changeLanguage,
		createPlugin,
		install,
		loadEnglishCatalog,
		readCatalog,
	}
}

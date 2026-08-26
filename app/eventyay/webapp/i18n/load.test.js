import test from 'node:test'
import assert from 'node:assert/strict'
import {importFromApp} from './app-deps.js'
import {
	createEnglishCatalogLoader,
	loadCatalogForLanguage,
	loadRawCatalog,
	resolveLocaleLoader,
	toGettextLocale,
} from './load.js'

const {default: i18next} = await importFromApp('i18next')

function loadersFromCatalogs(catalogs) {
	return Object.fromEntries(
		Object.entries(catalogs).map(([lang, catalog]) => [
			`/locale/${lang}/LC_MESSAGES/schedule.po`,
			async () => ({default: catalog}),
		])
	)
}

test('locale aliases resolve Ukrainian, Persian, Japanese, and English variants', () => {
	const loaders = {
		'/locale/ua/LC_MESSAGES/schedule.po': () => 'ua',
		'/locale/fa/LC_MESSAGES/schedule.po': () => 'fa',
		'/locale/en/LC_MESSAGES/schedule.po': () => 'en',
		'/locale/ja/LC_MESSAGES/schedule.po': () => 'ja',
		'/locale/de_Formal/LC_MESSAGES/schedule.po': () => 'de_Formal',
		'/locale/zh_Hans/LC_MESSAGES/schedule.po': () => 'zh_Hans',
		'/locale/pt_BR/LC_MESSAGES/schedule.po': () => 'pt_BR',
	}
	assert.equal(resolveLocaleLoader(loaders, 'uk')(), 'ua')
	assert.equal(resolveLocaleLoader(loaders, 'fa-ir')(), 'fa')
	assert.equal(resolveLocaleLoader(loaders, 'en-GB')(), 'en')
	assert.equal(resolveLocaleLoader(loaders, 'en_US')(), 'en')
	assert.equal(resolveLocaleLoader(loaders, 'ja-jp')(), 'ja')
	assert.equal(resolveLocaleLoader(loaders, 'de-formal')(), 'de_Formal')
	assert.equal(resolveLocaleLoader(loaders, 'zh-hans')(), 'zh_Hans')
	assert.equal(resolveLocaleLoader(loaders, 'pt-br')(), 'pt_BR')
	assert.equal(resolveLocaleLoader(loaders, 'xx'), null)
	assert.equal(toGettextLocale('zh-hans'), 'zh_Hans')
	assert.equal(toGettextLocale('pt-br'), 'pt_BR')
	assert.equal(toGettextLocale('de-formal'), 'de_Formal')
})

test('loadCatalogForLanguage overlays partial catalogs and ignores missing locales', async () => {
	const localeLoaders = loadersFromCatalogs({
		en: {
			Save: 'Save',
			Search: 'Search',
			'RoomsSidebar:schedule:label': 'Schedule',
		},
		de: {
			Save: '',
			Search: 'Search',
			'RoomsSidebar:schedule:label': 'Zeitplan',
		},
	})
	const loadEnglish = createEnglishCatalogLoader(localeLoaders)
	const german = await loadCatalogForLanguage(localeLoaders, 'de', loadEnglish)
	assert.equal(german.Save, 'Save')
	assert.equal(german.Search, 'Search')
	assert.equal(german['RoomsSidebar:schedule:label'], 'Zeitplan')
	assert.equal(await loadRawCatalog(localeLoaders, 'hi'), null)
	const hindi = await loadCatalogForLanguage(localeLoaders, 'hi', loadEnglish)
	assert.equal(hindi.Save, 'Save')
	assert.equal(hindi['RoomsSidebar:schedule:label'], 'Schedule')
	const english = await loadCatalogForLanguage(localeLoaders, 'en-gb', loadEnglish)
	assert.equal(english.Save, 'Save')
})

test('i18next still returns English after a Hindi fallback merge', async () => {
	const english = {Save: 'Save', Search: 'Search'}
	const hindi = {Save: '', Search: ''}
	const i18n = i18next.createInstance()
	await i18n.init({
		lng: 'hi',
		fallbackLng: 'en',
		returnEmptyString: false,
		keySeparator: false,
		nsSeparator: false,
		resources: {
			en: {translation: english},
			hi: {translation: {Save: 'Save', Search: 'Search'}},
		},
	})
	assert.equal(i18n.t('Save'), 'Save')
	assert.equal(i18n.t(hindi.Save || 'Save'), 'Save')
})

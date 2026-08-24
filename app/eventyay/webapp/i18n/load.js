import {isEnglishLocale, mergeCatalogWithEnglish, toDjangoLanguage, usableTranslations} from './catalog.js'

export {isEnglishLocale, mergeCatalogWithEnglish, toDjangoLanguage, usableTranslations}

export function toGettextLocale(language) {
	const django = toDjangoLanguage(language)
	const separator = django.indexOf('-')
	if (separator < 0) return django
	const head = django.slice(0, separator)
	const rest = django.slice(separator + 1)
	if (rest.length > 2) {
		return `${head}_${rest.charAt(0).toUpperCase()}${rest.slice(1).toLowerCase()}`
	}
	return `${head}_${rest.toUpperCase()}`
}

const GETTEXT_DIR_ALIASES = {
	uk: ['ua'],
	'fa-ir': ['fa'],
	'ja-jp': ['ja'],
	'en-us': ['en'],
	'en-gb': ['en'],
	'en-au': ['en'],
	'en-ca': ['en'],
}

export function resolveLocaleLoader(localeLoaders, language) {
	if (!language) return null
	const django = toDjangoLanguage(language)
	const gettextLocale = toGettextLocale(django)
	const [base] = django.split('-')
	const candidates = new Set([
		language,
		django,
		gettextLocale,
		django.replaceAll('-', '_'),
		...(GETTEXT_DIR_ALIASES[django] || []),
	])
	if (base) candidates.add(base)

	for (const candidate of candidates) {
		const needle = `/locale/${candidate}/LC_MESSAGES/`
		const match = Object.entries(localeLoaders).find(([path]) => path.includes(needle))
		if (match) return match[1]
	}
	return null
}

export async function loadRawCatalog(localeLoaders, language) {
	const loader = resolveLocaleLoader(localeLoaders, language)
	if (!loader) return null
	const locale = await loader()
	return locale.default || {}
}

export function createEnglishCatalogLoader(localeLoaders) {
	let englishCatalogPromise
	return function loadEnglishCatalog() {
		if (!englishCatalogPromise) {
			englishCatalogPromise = loadRawCatalog(localeLoaders, 'en').then((catalog) =>
				usableTranslations(catalog || {}, 'en')
			)
		}
		return englishCatalogPromise
	}
}

export async function loadCatalogForLanguage(localeLoaders, language, loadEnglishCatalog) {
	const english = await loadEnglishCatalog()
	const raw = isEnglishLocale(language) ? english : await loadRawCatalog(localeLoaders, language)
	return mergeCatalogWithEnglish(english, raw, language)
}

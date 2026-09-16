export function toDjangoLanguage(language) {
	if (!language) return language
	return String(language).replaceAll('_', '-').toLowerCase()
}

export function isEnglishLocale(language) {
	const django = toDjangoLanguage(language)
	return django === 'en' || String(django).startsWith('en-')
}

export function usableTranslations(catalog, language) {
	const keepMsgidCopies = isEnglishLocale(language)
	return Object.fromEntries(
		Object.entries(catalog || {}).filter(([key, value]) => {
			if (value == null || value === '') return false
			if (!keepMsgidCopies && value === key) return false
			return true
		})
	)
}

export function mergeCatalogWithEnglish(english, catalog, language) {
	const fallback = usableTranslations(english, 'en')
	if (isEnglishLocale(language)) {
		return fallback
	}
	if (!catalog) {
		return fallback
	}
	return {
		...fallback,
		...usableTranslations(catalog, language),
	}
}

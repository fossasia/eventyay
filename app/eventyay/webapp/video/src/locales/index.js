export const locales = [{
	code: 'en',
	nativeLabel: 'English',
	englishLabel: 'English'
}, {
	code: 'en-us',
	nativeLabel: 'English (United States)',
	englishLabel: 'English (United States)'
}, {
	code: 'en-gb',
	nativeLabel: 'English (United Kingdom)',
	englishLabel: 'English (United Kingdom)'
}, {
	code: 'en-au',
	nativeLabel: 'English (Australia)',
	englishLabel: 'English (Australia)'
}, {
	code: 'en-ca',
	nativeLabel: 'English (Canada)',
	englishLabel: 'English (Canada)'
}, {
	code: 'de',
	nativeLabel: 'Deutsch',
	englishLabel: 'German'
}, {
	code: 'de-formal',
	nativeLabel: 'Deutsch',
	englishLabel: 'German (formal)'
}, {
	code: 'ar',
	nativeLabel: 'العربية',
	englishLabel: 'Arabic'
}, {
	code: 'bg',
	nativeLabel: 'Български',
	englishLabel: 'Bulgarian'
}, {
	code: 'bn',
	nativeLabel: 'বাংলা',
	englishLabel: 'Bengali'
}, {
	code: 'ca',
	nativeLabel: 'Català',
	englishLabel: 'Catalan'
}, {
	code: 'cs',
	nativeLabel: 'Česky',
	englishLabel: 'Czech'
}, {
	code: 'da',
	nativeLabel: 'Dansk',
	englishLabel: 'Danish'
}, {
	code: 'el',
	nativeLabel: 'Ελληνικά',
	englishLabel: 'Greek'
}, {
	code: 'es',
	nativeLabel: 'Español',
	englishLabel: 'Spanish'
}, {
	code: 'fa-ir',
	nativeLabel: 'قارسی',
	englishLabel: 'Persian'
}, {
	code: 'fi',
	nativeLabel: 'Suomi',
	englishLabel: 'Finnish'
}, {
	code: 'fr',
	nativeLabel: 'Français',
	englishLabel: 'French'
}, {
	code: 'hu',
	nativeLabel: 'Magyar',
	englishLabel: 'Hungarian'
}, {
	code: 'hi',
	nativeLabel: 'हिन्दी',
	englishLabel: 'Hindi'
}, {
	code: 'gu',
	nativeLabel: 'ગુજરાતી',
	englishLabel: 'Gujarati'
}, {
	code: 'ha',
	nativeLabel: 'Hausa',
	englishLabel: 'Hausa'
}, {
	code: 'id',
	nativeLabel: 'Bahasa Indonesia',
	englishLabel: 'Indonesian'
}, {
	code: 'it',
	nativeLabel: 'Italiano',
	englishLabel: 'Italian'
}, {
	code: 'ja-jp',
	nativeLabel: '日本語',
	englishLabel: 'Japanese'
}, {
	code: 'ko',
	nativeLabel: '한국어',
	englishLabel: 'Korean'
}, {
	code: 'km',
	nativeLabel: 'ខ្មែរ',
	englishLabel: 'Khmer'
}, {
	code: 'lv',
	nativeLabel: 'Latviešu',
	englishLabel: 'Latvian'
}, {
	code: 'ms',
	nativeLabel: 'Bahasa Melayu',
	englishLabel: 'Malay'
}, {
	code: 'ml',
	nativeLabel: 'മലയാളം',
	englishLabel: 'Malayalam'
}, {
	code: 'mr',
	nativeLabel: 'मराठी',
	englishLabel: 'Marathi'
}, {
	code: 'nb-no',
	nativeLabel: 'Norsk bokmål',
	englishLabel: 'Norwegian Bokmål'
}, {
	code: 'nl',
	nativeLabel: 'Nederlands',
	englishLabel: 'Dutch'
}, {
	code: 'nl-informal',
	nativeLabel: 'Nederlands',
	englishLabel: 'Dutch (informal)'
}, {
	code: 'pl',
	nativeLabel: 'Polski',
	englishLabel: 'Polish'
}, {
	code: 'pl-informal',
	nativeLabel: 'Polski (nieformalny)',
	englishLabel: 'Polish (informal)'
}, {
	code: 'pt-br',
	nativeLabel: 'Português brasileiro',
	englishLabel: 'Portuguese (Brazil)'
}, {
	code: 'pt-pt',
	nativeLabel: 'Português',
	englishLabel: 'Portuguese'
}, {
	code: 'ro',
	nativeLabel: 'Română',
	englishLabel: 'Romanian'
}, {
	code: 'ru',
	nativeLabel: 'Русский',
	englishLabel: 'Russian'
}, {
	code: 'si',
	nativeLabel: 'සිංහල',
	englishLabel: 'Sinhala'
}, {
	code: 'sl',
	nativeLabel: 'Slovenščina',
	englishLabel: 'Slovenian'
}, {
	code: 'sv',
	nativeLabel: 'Svenska',
	englishLabel: 'Swedish'
}, {
	code: 'sw',
	nativeLabel: 'Kiswahili',
	englishLabel: 'Swahili'
}, {
	code: 'ta',
	nativeLabel: 'தமிழ்',
	englishLabel: 'Tamil'
}, {
	code: 'te',
	nativeLabel: 'తెలుగు',
	englishLabel: 'Telugu'
}, {
	code: 'th',
	nativeLabel: 'ไทย',
	englishLabel: 'Thai'
}, {
	code: 'tr',
	nativeLabel: 'Türkçe',
	englishLabel: 'Turkish'
}, {
	code: 'uk',
	nativeLabel: 'Українська',
	englishLabel: 'Ukrainian'
}, {
	code: 'ur',
	nativeLabel: 'اردو',
	englishLabel: 'Urdu'
}, {
	code: 'vi',
	nativeLabel: 'Tiếng Việt',
	englishLabel: 'Vietnamese'
}, {
	code: 'zh-hans',
	nativeLabel: '简体中文',
	englishLabel: 'Chinese Simplified'
}, {
	code: 'zh-hant',
	nativeLabel: '繁體中文',
	englishLabel: 'Chinese Traditional'
}]

export function resolveLanguageOptions(configLocales) {
	if (Array.isArray(configLocales) && configLocales.length > 0 && typeof configLocales[0] === 'object') {
		return configLocales.map(item => ({
			code: item.code,
			nativeLabel: item.nativeLabel || item.label,
			englishLabel: item.englishLabel || item.nativeLabel || item.label,
		}))
	}
	if (Array.isArray(configLocales) && configLocales.length > 0 && typeof configLocales[0] === 'string') {
		const wanted = new Set(configLocales.map(code => String(code).replaceAll('_', '-').toLowerCase()))
		const matched = locales.filter(locale => wanted.has(locale.code.toLowerCase()))
		return matched.length ? matched : locales
	}
	return locales
}

export function resolveCurrentLanguage(availableLanguages, preferredLanguage) {
	const langs = Array.isArray(availableLanguages) && availableLanguages.length > 0
		? availableLanguages
		: locales
	const raw = preferredLanguage || 'en'
	const candidate = String(raw).replaceAll('_', '-').toLowerCase()

	// 1. Exact match
	const exact = langs.find(l => l && l.code && l.code.toLowerCase() === candidate)
	if (exact) return exact.code

	// 2. Progressively shorter subtags (e.g. zh-hant-hk -> zh-hant)
	const parts = candidate.split('-')
	for (let i = parts.length - 1; i > 1; i--) {
		const subtag = parts.slice(0, i).join('-')
		const subtagMatch = langs.find(l => l && l.code && l.code.toLowerCase() === subtag)
		if (subtagMatch) return subtagMatch.code
	}

	// 3. Exact base language match
	const base = parts[0]
	const baseExact = langs.find(l => l && l.code && l.code.toLowerCase() === base)
	if (baseExact) return baseExact.code

	// 4. Any variant starting with base prefix
	const prefixMatch = langs.find(l => l && l.code && l.code.toLowerCase().startsWith(`${base}-`))
	if (prefixMatch) return prefixMatch.code

	const en = langs.find(l => l && l.code && l.code.toLowerCase() === 'en')
	if (en) return en.code

	return langs[0]?.code || 'en'
}

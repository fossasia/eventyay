/* global ENV_DEVELOPMENT */
import i18next from 'i18next'
import config from 'config'
// Vue.use(VueI18n)
//
// function loadLocaleMessages () {
// 	const locales = require.context('./locales', true, /[A-Za-z0-9-_,\s]+\.js$/i)
// 	const messages = {}
// 	locales.keys().forEach(key => {
// 		const matched = key.match(/([A-Za-z0-9-_]+)\./i)
// 		if (matched && matched.length > 1) {
// 			const locale = matched[1]
// 			messages[locale] = Object.assign({}, locales(key).default, config.theme?.textOverwrites ?? {})
// 		}
// 	})
// 	return messages
// }
//
// export default new VueI18n({
// 	locale: config.locale || 'en',
// 	fallbackLocale: 'en',
// 	messages: loadLocaleMessages()
// })

export default i18next

const LANGUAGE_COOKIE_NAME = 'eventyay_language'
const localeLoaders = import.meta.glob('./locales/*.json')

export function localize(string) {
	if (typeof string === 'string') return string
	for (const lang of i18next.languages) {
		if (string[lang]) return string[lang]
	}
	return Object.values(string)[0]
}

function getStoredLanguage() {
	try {
		return localStorage.userLanguage
	} catch (error) {
		return null
	}
}

function setStoredLanguage(language) {
	try {
		localStorage.userLanguage = language
	} catch (error) {
		// Ignore localStorage access errors (e.g. disabled storage, private mode, quota exceeded)
	}
}

function getLanguageFromCookie() {
	try {
		const cookieName = `${LANGUAGE_COOKIE_NAME}=`
		const raw = document.cookie.split('; ').find(entry => entry.startsWith(cookieName))
		return raw ? decodeURIComponent(raw.substring(cookieName.length)) : null
	} catch (error) {
		return null
	}
}

function resolveLocaleLoader(language) {
	if (!language) return null
	const normalized = language.replace('-', '_')
	const [base, region] = normalized.split('_')
	const candidates = new Set([language, normalized])
	if (base && region) {
		candidates.add(`${base}-${region}`)
		candidates.add(`${base}-${region.toUpperCase()}`)
		candidates.add(`${base}_${region.toUpperCase()}`)
	}
	if (base) {
		candidates.add(base)
	}

	for (const candidate of candidates) {
		const path = `./locales/${candidate}.json`
		if (localeLoaders[path]) {
			return localeLoaders[path]
		}
	}
	return null
}

function getInitialLanguage() {
	const stored = getStoredLanguage()
	const cookie = getLanguageFromCookie()
	const language = stored || cookie || config.defaultLocale || config.locale || 'en'
	if (!stored && cookie) {
		setStoredLanguage(cookie)
	}
	return language
}

export async function init(app) {
	const initialLanguage = getInitialLanguage()
	await i18next
		// dynamic locale loader using webpack chunks
		.use({
			type: 'backend',
			init(services, backendOptions, i18nextOptions) {},
			async read(language, namespace, callback) {
				try {
					const loader = resolveLocaleLoader(language)
					if (!loader) {
						throw new Error(`Missing locale bundle for "${language}"`)
					}
					const locale = await loader()
					callback(null, locale.default)
				} catch (error) {
					callback(error)
				}
			}
		})
		// inject custom theme text overwrites
		.use({
			type: 'postProcessor',
			name: 'themeOverwrites',
			process(value, key, options, translator) {
				return config.theme?.textOverwrites?.[key[0]] ?? value
			}
		})
		.init({
			lng: initialLanguage,
			fallbackLng: 'en',
			debug: ENV_DEVELOPMENT,
			keySeparator: false,
			nsSeparator: false,
			postProcess: ['themeOverwrites']
		})
	app.config.globalProperties.$i18n = i18next
	app.config.globalProperties.$t = i18next.t.bind(i18next)
	app.config.globalProperties.$localize = localize
}

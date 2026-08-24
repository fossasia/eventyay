/* global ENV_DEVELOPMENT */
import i18next from 'i18next'
import config from 'config'
import {
	createEnglishCatalogLoader,
	isEnglishLocale,
	loadCatalogForLanguage as mergeLoadedCatalog,
	loadRawCatalog,
	toDjangoLanguage,
} from '../../i18n/load.js'
import {createTranslate, notifyLocaleChange, trackLocale} from '../../i18n/locale.js'

export default i18next
export {notifyLocaleChange}

export const LANGUAGE_COOKIE_NAME = 'eventyay_language'
const localeLoaders = import.meta.glob('../../../locale/*/LC_MESSAGES/video.po')

export const translate = createTranslate(i18next)

export function localize(string) {
	trackLocale()
	if (!string) return ''
	if (typeof string === 'string') return string
	for (const lang of i18next.languages || []) {
		if (string[lang]) return string[lang]
	}
	return Object.values(string)[0] || ''
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

function getCsrfToken() {
	try {
		const match = document.cookie.match(/(?:^|; )eventyay_csrftoken=([^;]+)/)
		return match ? decodeURIComponent(match[1]) : null
	} catch (error) {
		return null
	}
}

function localeSwitchUrl() {
	const { protocol, host } = window.location
	const basePath = config?.basePath ?? ''
	if (!basePath) {
		return `${protocol}//${host}/common/account/locale`
	}
	const segments = basePath.split('/').filter(Boolean)
	const videoIndex = segments.lastIndexOf('video')
	if (videoIndex === -1) {
		return `${protocol}//${host}/common/account/locale`
	}
	const prefixEnd = Math.max(0, videoIndex - 2)
	const prefixSegments = segments.slice(0, prefixEnd)
	const prefix = prefixSegments.length > 0 ? `/${prefixSegments.join('/')}` : ''
	return `${protocol}//${host}${prefix}/common/account/locale`
}

export function setLanguageCookie(language) {
	try {
		const maxAge = 10 * 365 * 24 * 60 * 60
		document.cookie = `${LANGUAGE_COOKIE_NAME}=${encodeURIComponent(language)}; path=/; max-age=${maxAge}; SameSite=Lax`
	} catch (error) {
		console.error('Failed to persist language cookie', error)
	}
}

export async function syncLanguageToServer(language) {
	const csrf = getCsrfToken()
	if (!csrf) return
	try {
		const body = new URLSearchParams({
			locale: language,
			next: window.location.href,
			csrfmiddlewaretoken: csrf,
		})
		if (config?.eventSlug) body.set('event', config.eventSlug)
		if (config?.organizerSlug) body.set('organizer', config.organizerSlug)
		await fetch(localeSwitchUrl(), {
			method: 'POST',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded',
				'X-CSRFToken': csrf,
			},
			body,
			credentials: 'same-origin',
			redirect: 'manual',
		})
	} catch (error) {
		console.error('Failed to persist language on the server', error)
	}
}

export async function persistLanguage(language) {
	const djangoLanguage = toDjangoLanguage(language)
	setStoredLanguage(djangoLanguage)
	setLanguageCookie(djangoLanguage)
	await syncLanguageToServer(djangoLanguage)
}

const loadEnglishCatalog = createEnglishCatalogLoader(localeLoaders)

async function loadCatalogForLanguage(language) {
	const catalog = await mergeLoadedCatalog(localeLoaders, language, loadEnglishCatalog)
	if (!isEnglishLocale(language) && ENV_DEVELOPMENT && !(await loadRawCatalog(localeLoaders, language))) {
		console.warn('Missing video.po catalog for "%s", falling back to English', language)
	}
	return catalog
}

function getInitialLanguage() {
	const stored = toDjangoLanguage(getStoredLanguage())
	const cookie = toDjangoLanguage(getLanguageFromCookie())
	const language = stored || cookie || toDjangoLanguage(config.defaultLocale) || toDjangoLanguage(config.locale) || 'en'
	if (!stored && cookie) {
		setStoredLanguage(cookie)
	}
	return language
}

export async function init(app) {
	const initialLanguage = getInitialLanguage()
	try {
		await i18next
			.use({
				type: 'backend',
				init() {},
				async read(language, namespace, callback) {
					try {
						callback(null, await loadCatalogForLanguage(language))
					} catch (error) {
						console.error('Failed to load video catalog for "%s"', language, error)
						try {
							callback(null, await loadEnglishCatalog())
						} catch (fallbackError) {
							console.error('Failed to load English video catalog', fallbackError)
							callback(null, {})
						}
					}
				}
			})
			.use({
				type: 'postProcessor',
				name: 'themeOverwrites',
				process(value, key) {
					return config.theme?.textOverwrites?.[key[0]] ?? value
				}
			})
			.init({
				lng: initialLanguage,
				fallbackLng: 'en',
				preload: ['en'],
				returnEmptyString: false,
				returnNull: false,
				debug: ENV_DEVELOPMENT,
				keySeparator: false,
				nsSeparator: false,
				postProcess: ['themeOverwrites']
			})
	} catch (error) {
		console.error('Failed to initialize Video translations', error)
	}
	notifyLocaleChange()
	app.config.globalProperties.$i18n = i18next
	app.config.globalProperties.$t = translate
	app.config.globalProperties.$localize = localize
}

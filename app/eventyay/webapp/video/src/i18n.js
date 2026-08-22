/* global ENV_DEVELOPMENT */
import i18next from 'i18next'
import config from 'config'

export default i18next

export const LANGUAGE_COOKIE_NAME = 'eventyay_language'
const localeLoaders = import.meta.glob('../../../locale/*/LC_MESSAGES/video.po')

export function localize(string) {
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

function toDjangoLanguage(language) {
	if (!language) return language
	return String(language).replaceAll('_', '-').toLowerCase()
}

function toGettextLocale(language) {
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

function resolveLocaleLoader(language) {
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
		const path = `../../../locale/${candidate}/LC_MESSAGES/video.po`
		if (localeLoaders[path]) {
			return localeLoaders[path]
		}
	}
	return null
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
	await i18next
		.use({
			type: 'backend',
			init() {},
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
			returnEmptyString: false,
			returnNull: false,
			debug: ENV_DEVELOPMENT,
			keySeparator: false,
			nsSeparator: false,
			postProcess: ['themeOverwrites']
		})
	app.config.globalProperties.$i18n = i18next
	app.config.globalProperties.$t = i18next.t.bind(i18next)
	app.config.globalProperties.$localize = localize
}

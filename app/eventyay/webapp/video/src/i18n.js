/* global ENV_DEVELOPMENT */
import i18next from 'i18next'
import config from 'config'
import {createVueGettextRuntime} from '../../i18n/vue-runtime.js'
import {notifyLocaleChange, toDjangoLanguage} from '../../i18n/index.js'

export default i18next
export {notifyLocaleChange}

export const LANGUAGE_COOKIE_NAME = 'eventyay_language'
const runtime = createVueGettextRuntime({
	domain: 'video',
	i18next,
	localeLoaders: import.meta.glob('../../../locale/*/LC_MESSAGES/video.po'),
	debug: ENV_DEVELOPMENT,
	warnOnMissing: Boolean(ENV_DEVELOPMENT),
	extraPlugins: [
		{
			type: 'postProcessor',
			name: 'themeOverwrites',
			process(value, key) {
				return config.theme?.textOverwrites?.[key[0]] ?? value
			},
		},
	],
	extraInitOptions: {
		postProcess: ['themeOverwrites'],
	},
})

export const translate = runtime.translate
export const localize = runtime.localize
export const changeLanguage = runtime.changeLanguage

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
	try {
		await runtime.init({lng: getInitialLanguage()})
	} catch (error) {
		console.error('Failed to initialize Video translations', error)
	}
	runtime.install(app)
}

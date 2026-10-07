/**
 * Lazy loader for moment.js locales
 *
 * Locales are loaded on demand instead of being imported upfront,
 * which keeps them out of the initial bundle. Each locale becomes
 * its own chunk that is fetched only when the locale is actually set.
 *
 * The dynamic imports below use static specifiers so Vite can
 * analyze and code-split them at build time. The explicit `.js`
 * extension keeps the specifiers resolvable by both Vite and
 * Node's ESM resolver (used by the test runner).
 */

const MOMENT_LOCALE_LOADERS = {
	'de': () => import('moment/locale/de.js'),
	'fr': () => import('moment/locale/fr.js'),
	'es': () => import('moment/locale/es.js'),
	'ar': () => import('moment/locale/ar.js'),
	'zh-cn': () => import('moment/locale/zh-cn.js'),
	'zh-tw': () => import('moment/locale/zh-tw.js'),
	'pt': () => import('moment/locale/pt.js'),
	'ja': () => import('moment/locale/ja.js'),
	'ko': () => import('moment/locale/ko.js'),
	'nl': () => import('moment/locale/nl.js'),
	'nb': () => import('moment/locale/nb.js'),
	'nn': () => import('moment/locale/nn.js'),
	'it': () => import('moment/locale/it.js'),
	'ru': () => import('moment/locale/ru.js'),
	'pl': () => import('moment/locale/pl.js'),
	'sv': () => import('moment/locale/sv.js'),
	'da': () => import('moment/locale/da.js'),
	'fi': () => import('moment/locale/fi.js'),
	'tr': () => import('moment/locale/tr.js'),
	'he': () => import('moment/locale/he.js'),
	'th': () => import('moment/locale/th.js'),
	'vi': () => import('moment/locale/vi.js'),
	'id': () => import('moment/locale/id.js'),
	'ms': () => import('moment/locale/ms.js'),
	'et': () => import('moment/locale/et.js'),
	'lt': () => import('moment/locale/lt.js'),
	'lv': () => import('moment/locale/lv.js'),
	'sl': () => import('moment/locale/sl.js'),
	'sk': () => import('moment/locale/sk.js'),
	'hu': () => import('moment/locale/hu.js'),
	'cs': () => import('moment/locale/cs.js'),
	'el': () => import('moment/locale/el.js'),
	'ro': () => import('moment/locale/ro.js'),
	'bg': () => import('moment/locale/bg.js'),
	'hr': () => import('moment/locale/hr.js'),
	'sr': () => import('moment/locale/sr.js'),
	'mk': () => import('moment/locale/mk.js'),
	'sq': () => import('moment/locale/sq.js'),
	'mt': () => import('moment/locale/mt.js'),
	'is': () => import('moment/locale/is.js'),
	'fa': () => import('moment/locale/fa.js'),
	'ur': () => import('moment/locale/ur.js'),
	'ps': () => import('moment/locale/ps.js'),
	'ku': () => import('moment/locale/ku.js'),
	'bn': () => import('moment/locale/bn.js'),
	'gu': () => import('moment/locale/gu.js'),
	'mr': () => import('moment/locale/mr.js'),
	'ta': () => import('moment/locale/ta.js'),
	'te': () => import('moment/locale/te.js'),
	'ml': () => import('moment/locale/ml.js'),
	'kn': () => import('moment/locale/kn.js'),
}

// 'en' is bundled with moment core and needs no separate load
const loadedLocales = new Set(['en'])
const pendingLoads = new Map()
const loadingStates = new Map() // locale -> 'loading' | 'idle' | 'error'

// Common locales to preload on startup (whitelisted + high-usage)
const COMMON_LOCALES = ['en', 'pt', 'es', 'fr', 'de', 'ru', 'zh-cn', 'ja', 'ko', 'it', 'pl', 'tr']

// Retry configuration
const MAX_RETRIES = 2
const BASE_RETRY_DELAY = 300 // ms

/**
 * Normalize a locale code for loader lookup
 */
function normalizeLocaleCode(locale) {
	return typeof locale === 'string' ? locale.toLowerCase().trim() : ''
}

/**
 * Check whether a moment locale has already been loaded
 *
 * @param {string} locale - Locale code (e.g. 'de', 'zh-cn')
 * @returns {boolean}
 */
export function isMomentLocaleLoaded(locale) {
	return loadedLocales.has(normalizeLocaleCode(locale))
}

/**
 * Load a moment.js locale on demand with retry logic
 *
 * @param {string} locale - Locale code to load (e.g. 'de', 'zh-cn')
 * @param {Object} options - Options
 * @param {number} options.maxRetries - Max retry attempts (default: 2)
 * @returns {Promise<Object>} Result with success status, locale, and cached flag
 */
export async function loadMomentLocale(locale, options = {}) {
	const { maxRetries = MAX_RETRIES } = options
	const code = normalizeLocaleCode(locale)

	if (!code) {
		return {
			success: false,
			locale,
			error: 'Invalid locale: expected a non-empty string'
		}
	}

	if (loadedLocales.has(code)) {
		return { success: true, locale: code, cached: true }
	}

	const loader = MOMENT_LOCALE_LOADERS[code]

	if (!loader) {
		return {
			success: false,
			locale: code,
			error: `No lazy loader available for locale: ${code}`
		}
	}

	// Dedupe concurrent loads of the same locale
	if (pendingLoads.has(code)) {
		await pendingLoads.get(code)
		return { success: true, locale: code, cached: true }
	}

	let attempt = 0
	const loadWithRetry = async () => {
		const loadPromise = loader()
		pendingLoads.set(code, loadPromise)
		loadingStates.set(code, 'loading')

		try {
			await loadPromise
			loadedLocales.add(code)
			loadingStates.set(code, 'idle')
			return { success: true, locale: code, cached: false }
		} catch (error) {
			pendingLoads.delete(code)
			loadingStates.set(code, 'error')
			
			if (attempt < maxRetries) {
				attempt++
				const delay = BASE_RETRY_DELAY * Math.pow(2, attempt - 1)
				console.warn(`Locale load failed (attempt ${attempt}/${maxRetries}), retrying in ${delay}ms:`, code, error)
				await new Promise(r => setTimeout(r, delay))
				return loadWithRetry()
			}
			
			console.error(`Failed to load moment locale after ${maxRetries + 1} attempts: ${code}`, error)
			return {
				success: false,
				locale: code,
				error: error?.message || String(error)
			}
		}
	}

	return loadWithRetry()
}

/**
 * Preload multiple moment locales in parallel
 *
 * @param {string[]} locales - Locale codes to preload
 * @returns {Promise<Object[]>} Results from loadMomentLocale for each locale
 */
export async function preloadMomentLocales(locales) {
	if (!Array.isArray(locales)) {
		return []
	}

	return Promise.all(locales.map(locale => loadMomentLocale(locale)))
}

/**
 * Preload commonly used locales on startup for better UX
 *
 * @returns {Promise<Object[]>} Results from preloadMomentLocales
 */
export async function preloadCommonLocales() {
	return preloadMomentLocales(COMMON_LOCALES)
}

/**
 * Get the loading state of a locale
 *
 * @param {string} locale - Locale code
 * @returns {string} 'idle' | 'loading' | 'error' | 'loaded'
 */
export function getLoadingState(locale) {
	const code = normalizeLocaleCode(locale)
	if (loadedLocales.has(code)) return 'loaded'
	return loadingStates.get(code) || 'idle'
}

/**
 * Get all locales that have been loaded so far
 *
 * @returns {string[]}
 */
export function getLoadedMomentLocales() {
	return [...loadedLocales]
}

/**
 * Get lazy loading statistics
 *
 * @returns {Object} Loading stats with counts and locale lists
 */
export function getMomentLocaleLoadStats() {
	return {
		loadedCount: loadedLocales.size,
		availableCount: Object.keys(MOMENT_LOCALE_LOADERS).length + 1,
		loadedLocales: getLoadedMomentLocales(),
		availableLocales: ['en', ...Object.keys(MOMENT_LOCALE_LOADERS)]
	}
}

/**
 * Reset loader state (mainly useful for tests)
 */
export function resetMomentLocaleLoader() {
	loadedLocales.clear()
	loadedLocales.add('en')
	pendingLoads.clear()
}

export { MOMENT_LOCALE_LOADERS, COMMON_LOCALES }

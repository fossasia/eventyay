import config from 'config'

const RTL_LOCALES = ['ar', 'fa', 'he', 'ur']

/**
 * Check if the given locale (or current config locale) is a Right-to-Left language.
 *
 * @param {string} [locale] - Language code to check. If not provided, uses config.locale.
 * @returns {boolean} True if the language is RTL (e.g., Arabic, Hebrew, Persian, Urdu), False otherwise.
 */
export function isRtl(locale) {
	if (!locale) {
		locale = config.locale
	}

	if (!locale) {
		return false
	}

	// Normalize: trim whitespace and lowercase for consistent matching
	locale = locale.trim().toLowerCase()

	// Check both full locale (e.g., 'ar-sa') and base language (e.g., 'ar')
	if (RTL_LOCALES.includes(locale)) {
		return true
	}

	const baseLang = locale.split('-')[0].split('_')[0]
	return RTL_LOCALES.includes(baseLang)
}

/**
 * Get the current RTL state based on config.
 * @returns {boolean}
 */
export function getRtlState() {
	return isRtl(config.rtl) || isRtl(config.locale)
}

/**
 * Apply RTL direction to the document.
 * Sets dir="rtl" on the HTML element and adds the "rtl" class.
 */
export function applyRtlDirection() {
	const isRtl = getRtlState()
	if (typeof document !== 'undefined' && document.documentElement) {
		if (isRtl) {
			document.documentElement.setAttribute('dir', 'rtl')
			document.documentElement.classList.add('rtl')
		} else {
			document.documentElement.setAttribute('dir', 'ltr')
			document.documentElement.classList.remove('rtl')
		}
	}
	return isRtl
}

export default {
	isRtl,
	getRtlState,
	applyRtlDirection,
}
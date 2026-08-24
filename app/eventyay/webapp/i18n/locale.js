import {shallowRef} from 'vue'

export const localeRevision = shallowRef(0)

export function notifyLocaleChange() {
	localeRevision.value += 1
}

export function trackLocale() {
	void localeRevision.value
}

export function createTranslate(i18n) {
	return function translate(key, options) {
		trackLocale()
		return i18n.t(key, options)
	}
}

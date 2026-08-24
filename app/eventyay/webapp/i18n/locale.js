let revision = 0
const listeners = new Set()

export function notifyLocaleChange() {
	revision += 1
	for (const listener of listeners) listener(revision)
}

export function subscribeLocale(listener) {
	listeners.add(listener)
	return () => listeners.delete(listener)
}

export function localeRevisionValue() {
	return revision
}

export function createTranslate(i18n, track = localeRevisionValue) {
	return function translate(key, options) {
		track()
		return i18n.t(key, options)
	}
}

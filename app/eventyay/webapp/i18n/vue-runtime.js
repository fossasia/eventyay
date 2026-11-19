import {shallowRef} from 'vue'
import {createI18nRuntime} from './runtime.js'
import {subscribeLocale} from './locale.js'

export function createVueI18nRuntime(options) {
	const localeRevision = shallowRef(0)
	subscribeLocale(() => {
		localeRevision.value += 1
	})
	return createI18nRuntime({
		...options,
		track() {
			void localeRevision.value
		},
	})
}

export const createVueGettextRuntime = createVueI18nRuntime


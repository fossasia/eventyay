import {shallowRef} from 'vue'
import {createGettextRuntime} from './runtime.js'
import {subscribeLocale} from './locale.js'

export function createVueGettextRuntime(options) {
	const localeRevision = shallowRef(0)
	subscribeLocale(() => {
		localeRevision.value += 1
	})
	return createGettextRuntime({
		...options,
		track() {
			void localeRevision.value
		},
	})
}

import {createGettextPlugin} from '../i18n/vite-plugin.js'

export default function loadGettext() {
	return createGettextPlugin('video', import.meta.dirname)
}

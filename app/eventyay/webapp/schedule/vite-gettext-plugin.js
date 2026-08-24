import {createGettextPlugin} from '../i18n/vite-plugin.js'

export default function loadGettext() {
	return createGettextPlugin('schedule', import.meta.dirname)
}

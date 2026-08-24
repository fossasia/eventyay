import i18next from 'i18next'
import moment from 'moment-timezone'
import {createVueGettextRuntime} from '../../../i18n/vue-runtime.js'
import {toDjangoLanguage} from '../../../i18n/index.js'

const runtime = createVueGettextRuntime({
	domain: 'schedule-editor',
	i18next,
	localeLoaders: import.meta.glob('../../../locale/*/LC_MESSAGES/schedule-editor.po'),
	assignWindowTranslate: true,
})
const momentLocaleModules = import.meta.glob('../../node_modules/moment/dist/locale/*.js')

export const translate = runtime.translate

export default async function (locale: string) {
	const lng = toDjangoLanguage(locale) || 'en'
	const momentLocale = lng.split('-')[0]
	await momentLocaleModules[`../../node_modules/moment/dist/locale/${momentLocale}.js`]?.()
	moment.locale(momentLocale)
	await runtime.init({lng})
	return runtime.createPlugin()
}

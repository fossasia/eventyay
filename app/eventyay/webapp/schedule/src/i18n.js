import i18next from 'i18next'
import {createVueGettextRuntime} from '../../i18n/vue-runtime.js'

const runtime = createVueGettextRuntime({
	domain: 'schedule',
	i18next,
	localeLoaders: import.meta.glob('../../../locale/*/LC_MESSAGES/schedule.po'),
})

await runtime.init({lng: 'en'})

export default i18next
export const translate = runtime.translate
export const changeScheduleLanguage = runtime.changeLanguage
export const createI18nPlugin = runtime.createPlugin

import i18next from 'i18next'
import {createVueI18nRuntime} from '../../i18n/vue-runtime.js'

const runtime = createVueI18nRuntime({
	domain: 'schedule',
	i18next,
	localeLoaders: import.meta.glob('../../locales/*.json'),
})

await runtime.init({lng: 'en'})

export default i18next
export const translate = runtime.translate
export const changeScheduleLanguage = runtime.changeLanguage
export const createI18nPlugin = runtime.createPlugin

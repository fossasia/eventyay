import { createApp, defineCustomElement } from 'vue'
import Buntpapier from 'buntpapier'
import App from '~/App.vue'
import { createI18nPlugin } from './i18n.js'

const PretalxSchedule = defineCustomElement(App, {
	configureApp(app) {
		app.use(Buntpapier)
		app.use(createI18nPlugin())
	}
})
customElements.define('pretalx-schedule', PretalxSchedule)

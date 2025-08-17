import { createApp, defineCustomElement } from 'vue'
import Buntpapier from 'buntpapier'
import ClickAway from '@manusanchev/vue3-clickaway'
import App from '~/App.vue'

const PretalxSchedule = defineCustomElement(App, {
	configureApp(app) {
		app.use(Buntpapier)
		app.use(ClickAway)
	}
})
customElements.define('pretalx-schedule', PretalxSchedule)

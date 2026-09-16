// This file is used for the development server, and for the default production build.
// It is not used for the web component build, which is handled by the `main-wc.js` file.
import { createApp } from 'vue'
import Buntpapier from 'buntpapier'
import App from '~/App.vue'
import { createI18nPlugin, changeScheduleLanguage } from './i18n.js'
import '~/styles/global.styl'

const app = createApp(
	App,
	{
		eventUrl: 'https://pretalx.com/democon/',
		locale: 'en-ie',
		// format: 'list',
	}
)
app.use(Buntpapier)
app.use(createI18nPlugin())
await changeScheduleLanguage('en-ie')
app.mount('#app')

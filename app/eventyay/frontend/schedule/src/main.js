// This file is used for the development server, and for the default production build.
// It is not used for the web component build, which is handled by the `main-wc.js` file.
import { createApp } from 'vue'
import Buntpapier from 'buntpapier'
import App from '~/App.vue'
import '~/styles/global.styl'

createApp(
	App,
	{
		eventUrl: 'https://pretalx.com/democon/',
		locale: 'en-ie',
		// format: 'list',
	}
).use(Buntpapier).mount('#app')

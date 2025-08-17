// This file is used for the development server, and for the default production build.
// It is not used for the web component build, which is handled by the `main-wc.js` file.
import { createApp } from 'vue'
import Buntpapier from 'buntpapier'
import ClickAway from '@manusanchev/vue3-clickaway'
import App from '~/App.vue'
import '~/styles/global.styl'

createApp(
	App,
	{
		eventUrl: 'https://quan.hoabinh.vn/democon/',
		locale: 'en-ie',
		// format: 'list',
	}
).use(Buntpapier).use(ClickAway).mount('#app')

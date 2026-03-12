import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import Buntpapier from 'buntpapier'
import '@/styles/global.styl'

const app = createApp(App)

app.use(Buntpapier)
app.use(createPinia())
app.use(router)

app.mount('#app')

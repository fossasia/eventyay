import { fileURLToPath, URL } from 'node:url'
import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/


export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
  ],
  css: {
		preprocessorOptions: {
			stylus: {
        additionalData: `
          @import "buntpapier/buntpapier/index.styl"
          @import "${path.resolve(__dirname, 'src/styles/variables.styl')}"
        `}
		}
	},
  server:{
    port: 3000
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '~': path.resolve(__dirname, 'src')
    },
  },
})

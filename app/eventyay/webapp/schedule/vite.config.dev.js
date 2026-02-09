// @ts-nocheck
import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const stylusOptions = {
	paths: [
		path.resolve(__dirname, './src/styles'),
		'node_modules'
	],
	imports: [
		'buntpapier/buntpapier/index.styl',
		path.resolve(__dirname, 'src/styles/variables.styl')
	]
}

export default defineConfig({
	plugins: [
		vue(),
	],
	css: {
		preprocessorOptions: {
			stylus: stylusOptions,
			styl: stylusOptions
		}
	},
	resolve: {
		extensions: ['.js', '.json', '.vue'],
		alias: {
			'~': path.resolve(__dirname, 'src')
		}
	},
	build: {
		rollupOptions: {
			// output: {
			// 	globals: {
			// 		vue: 'Vue'
			// 	}
			// }
		}
	}
})

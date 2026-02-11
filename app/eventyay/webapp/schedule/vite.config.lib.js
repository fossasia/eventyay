// @ts-nocheck
import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import BuntpapierStylus from 'buntpapier/stylus.js'
// import ReactivityTransform from '@vue-macros/reactivity-transform/vite'

const stylusOptions = {
	paths: [
		path.resolve(__dirname, './src/styles'),
		'node_modules'
	],
	use: [BuntpapierStylus({implicit: false})],
	imports: [
		'buntpapier/buntpapier/index.styl',
		path.resolve(__dirname, 'src/styles/variables.styl')
	]
}

export default defineConfig({
	plugins: [
		vue(),
		// ReactivityTransform(),
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
		lib: {
			entry: path.resolve(__dirname, 'src/lib.js'),
			formats: ['es'],
			name: 'PretalxSchedule',
			fileName: 'pretalx-schedule'
		},
		rollupOptions: {
			external: ['vue', 'buntpapier', 'markdown-it'],
			// output: {
			// 	globals: {
			// 		vue: 'Vue'
			// 	}
			// }
		}
	}
})

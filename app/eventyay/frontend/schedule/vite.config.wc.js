// @ts-nocheck
import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import BuntpapierStylus from 'buntpapier/stylus.js'

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
	define: {
		"process.env.NODE_ENV": JSON.stringify(process.env.NODE_ENV),
	},
	plugins: [
		vue({
			template: {
				compilerOptions: {
					isCustomElement: tag => tag === 'pretalx-schedule'
				},
			},
			features: {
				customElement: true
			}
		}),
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
			entry: path.resolve(__dirname, 'src/main-wc.js'),
			name: 'PretalxSchedule',
			fileName: 'pretalx-schedule'
		},
		rollupOptions: {
			// output: {
			// 	globals: {
			// 		vue: 'Vue'
			// 	}
			// }
		}
	}
})

// @ts-nocheck
import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import BuntpapierStylus from 'buntpapier/stylus.js'
import {createGettextPlugin} from '../i18n/vite-plugin.js'

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

const outDir = process.env.OUT_DIR
	? path.resolve(process.env.OUT_DIR, 'schedule')
	: 'dist'

export default defineConfig({
	server: {
		host: '0.0.0.0',
		port: 8082,
		fs: {
			allow: [
				path.resolve(__dirname),
				path.resolve(__dirname, '../../locale'),
				path.resolve(__dirname, '../i18n'),
			]
		},
	},
	define: {
		"process.env.NODE_ENV": JSON.stringify(process.env.NODE_ENV),
		__BUNDLED_DEV__: 'false',
		__SERVER_FORWARD_CONSOLE__: 'false',
	},
	plugins: [
		createGettextPlugin('schedule'),
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
		preprocessorMaxWorkers: 0,
		preprocessorOptions: {
			stylus: stylusOptions,
			styl: stylusOptions
		}
	},
	resolve: {
		dedupe: ['vue'],
		extensions: ['.js', '.json', '.vue'],
		alias: [
			{ find: '~', replacement: path.resolve(__dirname, 'src') },
			{ find: /^buntpapier$/, replacement: path.resolve(__dirname, 'node_modules/buntpapier/src/index.js') },
		],
	},
	build: {
		outDir,
		emptyOutDir: true,
		cssCodeSplit: false,
		sourcemap: false,
		lib: {
			entry: path.resolve(__dirname, 'src/main-wc.js'),
			name: 'PretalxSchedule',
			fileName: 'pretalx-schedule',
			formats: ['es']
		},
		target: 'es2022',
		rollupOptions: {
			output: {
				entryFileNames: 'pretalx-schedule.js',
				chunkFileNames: 'pretalx-schedule-[name].js',
				assetFileNames: 'pretalx-schedule.[ext]',
				manualChunks(id) {
					if (id.includes('node_modules')) {
						if (id.includes('/vue/')) return 'vendor-vue'
						if (id.includes('moment')) return 'vendor-moment'
						if (id.includes('markdown-it')) return 'vendor-markdown'
						if (id.includes('dompurify')) return 'vendor-dompurify'
						if (id.includes('i18next')) return 'vendor-i18n'
						return 'vendor'
					}
					if (id.includes('/src/components/GridSchedule')) return 'chunk-grid'
					if (id.includes('/src/components/ScheduleToolbar')) return 'chunk-toolbar'
					if (id.includes('/src/components/SessionModal')) return 'chunk-modal'
					return undefined
				},
			}
		}
	},
	optimizeDeps: {
		exclude: ['buntpapier'],
		include: ['fuzzysearch', 'popper.js', 'resize-observer-polyfill'],
	},
})

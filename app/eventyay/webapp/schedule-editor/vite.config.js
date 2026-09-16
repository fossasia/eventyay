import path from 'path'
import vue from '@vitejs/plugin-vue'
import {createGettextPlugin} from '../i18n/vite-plugin.js'
import BuntpapierStylus from 'buntpapier/stylus.js'

const stylusOptions = {
	paths: [
		// stylus does not allow for dynamic resolves, so we just list all paths here and hope it won't explode
		path.resolve(__dirname, './src/styles'),
		'node_modules'
	],
	use: [BuntpapierStylus({implicit: false})],
	imports: ['buntpapier/buntpapier/index.styl', `${path.resolve(__dirname, './src/styles/variables.styl')}`]
}

export default {
	define: {
		'process.env': {},
		__BUNDLED_DEV__: 'false',
		__SERVER_FORWARD_CONSOLE__: 'false',
	},
	base: process.env.BASE_URL || '/',
	plugins: [
		createGettextPlugin('schedule-editor'), vue()
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
		mainFields: ['browser', 'module', 'jsnext:main', 'jsnext'],
		extensions: ['.js', '.json', '.vue', '.ts', '.tsx'],
		alias: [
			{ find: '~', replacement: path.resolve(__dirname, './src') },
			{ find: '@', replacement: path.resolve(__dirname, './src') },
			{ find: 'moment-timezone', replacement: 'moment-timezone/builds/moment-timezone-with-data-10-year-range.js' },
			{ find: /^buntpapier$/, replacement: path.resolve(__dirname, 'node_modules/buntpapier/src/index.js') },
		],
	},
	build: {
		outDir: process.env.OUT_DIR ? `${process.env.OUT_DIR}/schedule-editor` : 'dist',
		emptyOutDir: true,
		manifest: 'schedule-editor-manifest.json',
		assetsDir: '',
		sourcemap: false,
		rollupOptions: {
			input: 'src/main.ts',
			output: {
				manualChunks(id) {
					if (id.includes('node_modules/vue/') || id.endsWith('/vue')) {
						return 'vue'
					}
					if (id.includes('moment-timezone') || id.includes('/moment/')) {
						return 'moment'
					}
					if (id.includes('node_modules/i18next')) {
						return 'i18n'
					}
					if (id.includes('node_modules/zod')) {
						return 'zod'
					}
				},
			}
		},
		target: 'es2022',
	},
	optimizeDeps: {
		exclude: ['moment', 'buntpapier'],
		include: ['fuzzysearch', 'popper.js', 'resize-observer-polyfill'],
	},
	server: {
	  port: '8080',
	  fs: {
		allow: [
			path.resolve(__dirname),
			path.resolve(__dirname, '../../locale'),
			path.resolve(__dirname, '../i18n'),
		]
	  }
	}
}

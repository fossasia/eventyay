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

const outDir = process.env.OUT_DIR
	? path.resolve(process.env.OUT_DIR, 'schedule')
	: 'dist'

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
						if (id.includes('buntpapier')) return 'vendor-buntpapier'
						return 'vendor'
					}
					if (id.includes('/src/components/GridSchedule')) return 'chunk-grid'
					if (id.includes('/src/components/ScheduleToolbar')) return 'chunk-toolbar'
					if (id.includes('/src/components/SessionModal')) return 'chunk-modal'
					return undefined
				},
			}
		}
	}
})

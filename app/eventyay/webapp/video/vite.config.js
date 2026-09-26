import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import ReactivityTransform from '@vue-macros/reactivity-transform/vite'
import { VitePWA } from 'vite-plugin-pwa'
import visualizer from 'rollup-plugin-visualizer'
import path from 'node:path'
import eslint from 'vite-plugin-eslint'
import {createGettextPlugin} from '../i18n/vite-plugin.js'

const dirname = import.meta.dirname
const stylusOptions = {
  paths: [
    path.resolve(dirname, './src/styles'),
    path.resolve(dirname, '../schedule/src/styles'),
    path.resolve(dirname, 'node_modules'),
    path.resolve(dirname, 'node_modules/buntpapier')
  ],
  imports: [
    'buntpapier/buntpapier/index.styl',
    path.resolve(dirname, 'src/styles/variables.styl'),
    path.resolve(dirname, 'src/styles/themed-buntpapier.styl'),
  ]
}

function exportJanusGateway() {
  return {
    name: 'export-janus-gateway',
    transform(code, id) {
      const cleanId = id.split('?')[0]
      if (!cleanId.includes('janus-gateway') || !cleanId.endsWith('html/janus.js')) return null
      return {
        code: `${code}\nexport default Janus;\n`,
        map: null
      }
    }
  }
}

// Icon font is referenced from CSS, so the browser only discovers it after
// that file arrives. Start it with the rest of the first load.
function preloadVideoAppGraph() {
  return {
    name: 'preload-video-app-graph',
    apply: 'build',
    enforce: 'post',
    generateBundle(_options, bundle) {
      const htmlAsset = bundle['index.html']
      if (!htmlAsset || htmlAsset.type !== 'asset') return
      const font = Object.values(bundle).find((item) => (
        item.type === 'asset'
        && item.fileName.includes('materialdesignicons')
        && item.fileName.endsWith('.woff2')
      ))
      if (!font) return
      const html = htmlAsset.source.toString()
      if (html.includes(font.fileName)) return
      const link = `<link rel="preload" as="font" type="font/woff2" crossorigin href="./${font.fileName}">`
      htmlAsset.source = html.replace('</head>', `${link}</head>`)
    }
  }
}

export default defineConfig(({ mode }) => {
  const currentYear = new Date().getFullYear()
  const env = loadEnv(mode, process.cwd(), '')

  // Use full Vite dev server URL during development so CSS url() references
  // (fonts, images) resolve against Vite, not the Django proxy.
  // Production builds fall back to a relative base so the bundle works from nested paths.
  const base = mode === 'development' ? '/' : './'

  return {
    base,
    server: {
      host: '0.0.0.0',
      port: 8880,
      origin: mode === 'development' ? 'http://localhost:8880' : undefined,
      fs: {
        allow: [
          path.resolve(dirname),
          path.resolve(dirname, '../../locale'),
          path.resolve(dirname, '../i18n'),
        ]
      },
      hmr: {
        host: 'localhost',
        port: 8880
      },
      allowedHosts: [
        '.localhost',
        '.eventyay.com',
        'app-test.eventyay.com',
        'app.eventyay.com',
        'wikimedia.eventyay.com'
      ]
    },
    plugins: [
      exportJanusGateway(),
      preloadVideoAppGraph(),
      createGettextPlugin('video'),
      vue(),
      ReactivityTransform(),
      // Enable PWA only in production builds (avoid SW claim issues during dev)
      mode === 'production' && VitePWA({
        registerType: 'autoUpdate',
        manifest: {
          name: 'eventyay',
          theme_color: '#180044',
          icons: [
            {
              src: 'eventyay-logo.192.png',
              type: 'image/png',
              sizes: '192x192'
            },
            {
              src: 'eventyay-logo.512.png',
              type: 'image/png',
              sizes: '512x512'
            },
            {
              src: 'eventyay-logo.svg',
              sizes: '192x192',
              type: 'image/svg+xml'
            },
            {
              src: 'eventyay-logo.svg',
              sizes: '512x512',
              type: 'image/svg+xml'
            }
          ]
        },
        // Avoid precaching index.html (parity with previous Workbox exclude)
        workbox: {
          skipWaiting: true,
          clientsClaim: true,
          // The HTML shell is rendered by Django, so it cannot be a precached file.
          navigateFallback: null,
          // Hashed JS and CSS are already cached by the browser. Precaching them
          // makes the service worker download the whole app again on first open.
          globPatterns: ['**/*.{ico,png,svg}'],
          // Allow larger assets (default is ~2MB); needed for 2.5MB PNG
          maximumFileSizeToCacheInBytes: 3 * 1024 * 1024
        }
      }),
      // Lint during dev only; production uses `npm run lint`
      mode === 'development' && eslint({
        include: ['src/**/*.js', 'src/**/*.vue'],
        cache: true
      }),
      mode === 'production' && process.env.ANALYZE && visualizer({
        open: true,
        filename: 'dist/bundle-report.html'
      })
    ].filter(Boolean),
    css: {
      preprocessorMaxWorkers: 0,
      preprocessorOptions: {
        stylus: stylusOptions,
        styl: stylusOptions
      }
    },
    resolve: {
      extensions: ['.js', '.json', '.vue'],
      preserveSymlinks: true,
      dedupe: ['vue', 'i18next'],
      alias: [
        { find: 'i18next', replacement: path.resolve(dirname, 'node_modules/i18next') },
        { find: 'vue', replacement: path.resolve(dirname, 'node_modules/vue') },
        { find: 'lodash', replacement: 'lodash-es' },
        { find: '~', replacement: path.resolve(dirname, 'src') },
        { find: /^buntpapier$/, replacement: path.resolve(dirname, 'node_modules/buntpapier/src/index.js') },
        { find: 'config', replacement: path.resolve(dirname, 'config.js') },
        { find: 'react', replacement: 'preact/compat' },
        { find: 'react-dom', replacement: 'preact/compat' },
        { find: 'preact/hooks/dist/hooks.js', replacement: 'preact/hooks' },
        { find: 'assets', replacement: path.resolve(dirname, 'src/assets') },
        { find: 'components', replacement: path.resolve(dirname, 'src/components') },
        { find: 'lib', replacement: path.resolve(dirname, 'src/lib') },
        { find: 'locales', replacement: path.resolve(dirname, 'src/locales') },
        { find: 'router', replacement: path.resolve(dirname, 'src/router') },
        { find: 'store', replacement: path.resolve(dirname, 'src/store') },
        { find: 'styles', replacement: path.resolve(dirname, 'src/styles') },
        { find: 'views', replacement: path.resolve(dirname, 'src/views') },
        { find: '@schedule', replacement: path.resolve(dirname, '../schedule/src') },
        { find: 'features', replacement: path.resolve(dirname, 'src/features') },
        { find: 'i18n', replacement: path.resolve(dirname, 'src/i18n') },
        { find: 'theme', replacement: path.resolve(dirname, 'src/theme') },
        { find: 'has-emoji', replacement: path.resolve(dirname, 'build/has-emoji/emoji.json') },
        { find: 'moment-timezone', replacement: path.resolve(dirname, 'node_modules/moment-timezone/builds/moment-timezone-with-data-10-year-range.js') },
        { find: 'markdown-it', replacement: path.resolve(dirname, 'node_modules/markdown-it') },
        { find: 'markdown-it-multimd-table', replacement: path.resolve(dirname, 'node_modules/markdown-it-multimd-table') },
        { find: 'dompurify', replacement: path.resolve(dirname, 'node_modules/dompurify') },
        { find: 'sdp', replacement: path.resolve(dirname, 'src/shims/sdp-default.js') },
      ]
    },
    optimizeDeps: {
      include: [
        'color',
        'moment-timezone',
        'fuzzysearch',
        'popper.js',
        'resize-observer-polyfill',
      ],
      exclude: [
        'janus-gateway',
        'janus-gateway/html/janus.js',
        'buntpapier',
      ]
    },
    build: {
      outDir: process.env.OUT_DIR ? `${process.env.OUT_DIR}/video` : 'dist',
      emptyOutDir: true,
      target: 'esnext',
      sourcemap: false, // Added for debugging vendor-webrtc issue
      cssCodeSplit: false,
      chunkSizeWarningLimit: 1250,
      rollupOptions: {
        checks: {
          pluginTimings: false,
        },
        input: {
          main: path.resolve(dirname, 'index.html'),
          preloader: path.resolve(dirname, 'src/preloader.js')
        },
        output: {
          // Every entry, including the preloader, gets a content hash. The video
          // HTML is rendered per request and points at that name, so a deploy
          // stops using the previous cached preloader and the chunks it imported.
          entryFileNames: 'assets/[name]-[hash].js',
          codeSplitting: {
            groups: [
              { name: 'vendor-rtc', test: /janus-gateway|webrtc-adapter/, priority: 30 },
              { name: 'vendor-hls', test: /hls\.js/, priority: 30 },
              { name: 'vendor-mux', test: /mux-embed|[\\/]mux\.js/, priority: 30 },
              { name: 'vendor-emoji', test: /emoji-mart|emoji-datasource-twitter|emoji-regex|twemoji-emojis/, priority: 25 },
              { name: 'vendor', test: /node_modules/, priority: 10 },
              { name: 'app', tags: ['$initial'], priority: 1 },
            ],
          },
        }
      }
    },
    define: {
      ENV_DEVELOPMENT: mode === 'development',
      RELEASE: `'${process.env.VENUELESS_COMMIT_SHA}'`,
      BASE_URL: `'${process.env.BASE_URL || '/'}'`,
      global: 'globalThis',
      'process.env.NODE_PATH': `'${process.env.NODE_PATH}'`,
      __CURRENT_YEAR__: currentYear,
      __BUNDLED_DEV__: 'false',
      __SERVER_FORWARD_CONSOLE__: 'false',
    }
  }
})

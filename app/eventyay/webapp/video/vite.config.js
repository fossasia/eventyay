import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import ReactivityTransform from '@vue-macros/reactivity-transform/vite'
import { VitePWA } from 'vite-plugin-pwa'
import visualizer from 'rollup-plugin-visualizer'
import path from 'path'
import commonjs from '@rollup/plugin-commonjs'
import eslint from 'vite-plugin-eslint'

const stylusOptions = {
  paths: [
    path.resolve(__dirname, './src/styles'),
    path.resolve(__dirname, '../schedule/src/styles'),
    path.resolve(__dirname, 'node_modules'),
    path.resolve(__dirname, 'node_modules/buntpapier')
  ],
  imports: [
    'buntpapier/buntpapier/index.styl',
    path.resolve(__dirname, 'src/styles/variables.styl'),
    path.resolve(__dirname, 'src/styles/themed-buntpapier.styl'),
  ]
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
          // Only precache static assets; exclude HTML documents
          globPatterns: ['**/*.{js,css,ico,png,svg}'],
          // Allow larger assets (default is ~2MB); needed for 2.5MB PNG
          maximumFileSizeToCacheInBytes: 3 * 1024 * 1024
        }
      }),
      // Added ESLint plugin to support lintOnSave functionality
      eslint({
        include: ['src/**/*.js', 'src/**/*.vue'],
        cache: false
      }),
  // Modernizr removed; using native feature checks in preloader instead
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
      dedupe: ['vue'],
      alias: [
        { find: 'lodash', replacement: 'lodash-es' },
        { find: '~', replacement: path.resolve(__dirname, 'src') },
        { find: /^buntpapier$/, replacement: path.resolve(__dirname, 'node_modules/buntpapier/src/index.js') },
        { find: 'config', replacement: path.resolve(__dirname, 'config.js') },
        { find: 'react', replacement: 'preact/compat' },
        { find: 'react-dom', replacement: 'preact/compat' },
        { find: 'preact/hooks/dist/hooks.js', replacement: 'preact/hooks' },
        { find: 'assets', replacement: path.resolve(__dirname, 'src/assets') },
        { find: 'components', replacement: path.resolve(__dirname, 'src/components') },
        { find: 'lib', replacement: path.resolve(__dirname, 'src/lib') },
        { find: 'locales', replacement: path.resolve(__dirname, 'src/locales') },
        { find: 'router', replacement: path.resolve(__dirname, 'src/router') },
        { find: 'store', replacement: path.resolve(__dirname, 'src/store') },
        { find: 'styles', replacement: path.resolve(__dirname, 'src/styles') },
        { find: 'views', replacement: path.resolve(__dirname, 'src/views') },
        { find: '@schedule', replacement: path.resolve(__dirname, '../schedule/src') },
        { find: 'features', replacement: path.resolve(__dirname, 'src/features') },
        { find: 'i18n', replacement: path.resolve(__dirname, 'src/i18n') },
        { find: 'theme', replacement: path.resolve(__dirname, 'src/theme') },
        { find: 'has-emoji', replacement: path.resolve(__dirname, 'build/has-emoji/emoji.json') },
        { find: 'moment-timezone', replacement: path.resolve(__dirname, 'node_modules/moment-timezone/builds/moment-timezone-with-data-10-year-range.js') },
        { find: 'markdown-it', replacement: path.resolve(__dirname, 'node_modules/markdown-it') },
        { find: 'markdown-it-multimd-table', replacement: path.resolve(__dirname, 'node_modules/markdown-it-multimd-table') },
        { find: 'dompurify', replacement: path.resolve(__dirname, 'node_modules/dompurify') },
        { find: 'sdp', replacement: path.resolve(__dirname, 'src/shims/sdp-default.js') },
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
        'pdfjs-dist',
        'buntpapier',
      ],
      esbuildOptions: {
        target: 'esnext'
      }
    },
    build: {
      outDir: process.env.OUT_DIR ? `${process.env.OUT_DIR}/video` : 'dist',
      emptyOutDir: false,
      target: 'esnext',
      sourcemap: false, // Added for debugging vendor-webrtc issue
      chunkSizeWarningLimit: 1250,
      rollupOptions: {
        input: {
          main: path.resolve(__dirname, 'index.html'),
          preloader: path.resolve(__dirname, 'src/preloader.js')
        },
        output: {
          entryFileNames: (chunkInfo) => {
            return chunkInfo.name === 'preloader'
              ? '[name].js'
              : 'assets/[name]-[hash].js'
          },
          // Manual chunking to keep the main app bundle small and
          // isolate large vendor assets.
          manualChunks(id) {
            if (id.includes('node_modules')) {
              // Consolidate WebRTC libs to a single chunk to avoid evaluation order races
              if (id.includes('janus-gateway') || id.includes('webrtc-adapter')) return 'vendor-rtc'
              if (id.includes('materialdesignicons-webfont') || id.match(/materialdesignicons/)) return 'vendor-mdi'
              if (id.includes('pdfjs-dist')) return 'vendor-pdfjs'
              if (id.includes('moment') || id.includes('moment-timezone')) return 'vendor-moment'
              if (id.includes('lodash') || id.includes('lodash-es')) return 'vendor-lodash'
              if (id.includes('quill')) return 'vendor-quill'
              if (id.includes('markdown-it')) return 'vendor-markdown'
              if (id.includes('i18next')) return 'vendor-i18n'
              if (id.includes('preact')) return 'vendor-preact'
              if (id.includes('vue') || id.includes('vue-router') || id.includes('vuex') || id.includes('vue-virtual-scroller')) return 'vendor-vue'
              // removed pretalx chunk assignment since library removed from usage
              if (id.includes('emoji-mart') || id.includes('emoji-datasource-twitter') || id.includes('emoji-regex') || id.includes('twemoji-emojis')) return 'vendor-emoji'
              if (id.includes('hls.js')) return 'vendor-hls'
              if (id.includes('core-js')) return 'vendor-corejs'
              if (id.includes('dompurify')) return 'vendor-dompurify'
              if (id.includes('sanitize-html')) return 'vendor-sanitizehtml'
              if (id.includes('js-md5')) return 'vendor-md5'
              if (id.includes('uuid')) return 'vendor-uuid'
              if (id.includes('register-service-worker')) return 'vendor-sw'
              if (id.includes('mux-embed') || id.includes('mux.js')) return 'vendor-mux'
              if (id.includes('random-js')) return 'vendor-randomjs'
              if (id.includes('web-animations-js')) return 'vendor-webanimations'
              return 'vendor'
            }
          }
        },
        plugins: [
          commonjs({
            include: /node_modules\/janus-gateway/,
            requireReturnsDefault: 'auto'
          })
        ]
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
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'node:path'

export default defineConfig(() => {
  const outDir =
    process.env.OUT_DIR ||
    resolve(
      __dirname,
      '../../plugins/webcheckin/static/pretixplugins/webcheckin/dist/webcheckin'
    )

  return {
    // Ensure generated chunk/asset URLs are relative to the entry file so they work
    // when served from Django's static URL.
    base: './',
    plugins: [vue()],
    build: {
      outDir,
      emptyOutDir: true,
      sourcemap: true,
      target: 'es2018',
      rollupOptions: {
        input: resolve(__dirname, 'src/webcheckin.js'),
        output: {
          // Stable entry file name for Django template.
          entryFileNames: 'webcheckin.js',
          // Multiple output files (code-splitting) to avoid a single monolith.
          // Keep chunk filenames stable to reduce the chance of module import 404s
          // if static assets are cached/stale across deploys.
          chunkFileNames: (chunkInfo) => {
            if (chunkInfo.name === 'vendor') {
              return 'vendor.js'
            }
            return '[name].js'
          },
          assetFileNames: 'assets/[name]-[hash][extname]',
          // Force at least one additional file by splitting vendor deps.
          manualChunks(id) {
            if (id.includes('node_modules')) {
              return 'vendor'
            }
          }
        }
      }
    }
  }
})

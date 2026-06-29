import { defineConfig } from 'vite'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  base: './',
  build: {
    outDir: process.env.OUT_DIR
      ? resolve(process.env.OUT_DIR, 'editor')
      : resolve(__dirname, '../../data/compiled-frontend/editor'),
    emptyOutDir: true,
    sourcemap: true,
    target: 'es2020',
    minify: 'esbuild',
    lib: {
      entry: resolve(__dirname, 'src/index.js'),
      name: 'eventyayEditor',
      formats: ['iife'],
      fileName: () => 'editor.js',
    },
    rollupOptions: {
      output: {
        assetFileNames: (assetInfo) => {
          if (assetInfo.name && assetInfo.name.endsWith('.css')) return 'editor.css'
          return 'assets/[name]-[hash][extname]'
        },
      },
    },
  },
})

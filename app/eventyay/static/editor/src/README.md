# Tiptap Editor Source

This directory contains the original source files used to build the Tiptap editor bundle for Eventyay.
We vendor the compiled bundle (`../editor.js` and `../editor.css`) to avoid introducing a new webapp build step into the main production CI/CD pipeline.

If you ever need to modify the editor logic (e.g., extensions, toolbar, or profiles), you can rebuild the bundle manually.

## How to rebuild

Since there is no `package.json` here to avoid CI overhead, you can build the bundle manually using a temporary environment or `npx`:

1. Initialize a temporary project and install dependencies:
   ```bash
   npm init -y
   npm install vite@^5.0.0 @tiptap/core @tiptap/pm @tiptap/starter-kit @tiptap/extension-link @tiptap/extension-underline
   ```

2. Create a temporary `vite.config.js`:
   ```javascript
   import { defineConfig } from 'vite'
   export default defineConfig({
     build: {
       outDir: '../',
       emptyOutDir: false,
       lib: {
         entry: 'index.js',
         name: 'eventyayEditor',
         formats: ['iife'],
         fileName: () => 'editor.js',
       },
       rollupOptions: {
         output: {
           assetFileNames: (assetInfo) => assetInfo.name.endsWith('.css') ? 'editor.css' : 'assets/[name]-[hash][extname]',
         },
       },
     },
   })
   ```

3. Run `npx vite build` from within the `src` directory.

4. Check the updated `editor.js` and `editor.css` into the repository.

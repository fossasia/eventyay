import { defineConfig, presetWind3, presetIcons, Preset } from 'unocss'
import presetWebFonts from '@unocss/preset-web-fonts'

export default defineConfig({
  presets: [
    presetWind3({
      preflight: 'on-demand',
    }),
    presetIcons({
      collections: {
        fa: () => import('@iconify-json/fa/icons.json').then(i => i.default),
      },
    }),
    presetWebFonts({
      provider: 'google',
      fonts: {
        sans: 'Open Sans',
        mono: 'Fira Code',
      },
    }) as Preset,
  ]
})

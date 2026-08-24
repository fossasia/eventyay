declare module '*.vue' {
  import { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, unknown>
  export default component
}

declare module 'buntpapier' {
  import { Plugin } from 'vue'
  const plugin: Plugin
  export default plugin
}

declare module '~/lib/i18n' {
  import { Plugin } from 'vue'
  export function translate(key: string, options?: Record<string, unknown>): string
  const plugin: (locale: string) => Promise<Plugin>
  export default plugin
}

declare module '*.po' {
  const catalog: Record<string, string>
  export default catalog
}

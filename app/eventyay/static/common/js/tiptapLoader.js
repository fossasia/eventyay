/* Lazy-load the Tiptap editor bundle only on pages that contain Tiptap fields.
 *
 * The <script> tag carrying this file must have data-tiptap-js and
 * data-tiptap-css attributes pointing to the compiled bundle URLs.
 * This mirrors the pattern used by toastuiLoader.js.
 *
 * Because django-compressor may merge this file into a bundle whose
 * <script> tag does not carry our data attributes, we search the DOM for
 * the real loader tag as a fallback.
 */

  const resolveLoaderEl = () => {
    const cur = document.currentScript
    if (cur?.dataset?.tiptapJs) return cur
    const candidates = document.querySelectorAll('script[src*="tiptapLoader"]')
    for (const el of candidates) {
      if (el?.dataset?.tiptapJs) return el
    }
    return cur
  }

  const scriptEl = resolveLoaderEl()
  const tiptapJsUrl = scriptEl?.dataset?.tiptapJs
  const tiptapCssUrl = scriptEl?.dataset?.tiptapCss

  const SELECTOR = 'textarea[data-tiptap-profile]'

  const ensureLink = (href) => {
    if (!href) return
    if (document.querySelector(`link[rel="stylesheet"][href="${href}"]`)) return
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.type = 'text/css'
    link.href = href
    document.head?.appendChild(link)
  }

  const ensureScript = (src) => {
    if (!src) return
    if (document.querySelector(`script[src="${src}"]`)) return
    const script = document.createElement('script')
    script.src = src
    script.defer = true
    document.head?.appendChild(script)
  }

  const load = () => {
    if (window.__eventyayTiptapLoaded) return
    window.__eventyayTiptapLoaded = true
    ensureLink(tiptapCssUrl)
    ensureScript(tiptapJsUrl)
  }

  const checkAndLoad = () => {
    if (document.querySelector(SELECTOR)) {
      load()
      return true
    }
    return false
  }

  const startObserver = () => {
    if (!window.MutationObserver) return
    const observer = new MutationObserver(() => {
      if (checkAndLoad()) observer.disconnect()
    })
    if (!document.documentElement) return
    observer.observe(document.documentElement, { childList: true, subtree: true })
  }

  const boot = () => {
    if (!tiptapJsUrl) return
    if (checkAndLoad()) return
    startObserver()
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true })
  } else {
    boot()
  }

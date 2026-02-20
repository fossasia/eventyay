/* Lazy-load Toast UI Editor assets only when needed. */

(() => {
    const scriptEl = document.currentScript
    const toastUiCssUrl = scriptEl?.dataset?.toastuiCss
    const toastUiJsUrl = scriptEl?.dataset?.toastuiJs

    window.eventyayEditorConfig = {
        lang: scriptEl?.dataset?.toastuiLang || 'en',
        t: {
            undo: scriptEl?.dataset?.toastuiTUndo || 'Undo',
            redo: scriptEl?.dataset?.toastuiTRedo || 'Redo',
            underline: scriptEl?.dataset?.toastuiTUnderline || 'Underline',
        },
    }

    const selector = 'textarea[data-markdown-field="true"], .markdown-wrapper textarea'

    const markLoaded = () => {
        window.__eventyayToastUiLoaded = true
        if (typeof window.dispatchEvent !== 'function') return

        let eventObj = null
        if (typeof window.Event === 'function') {
            eventObj = new Event('eventyay:toastui-ready')
        } else if (typeof document.createEvent === 'function') {
            eventObj = document.createEvent('Event')
            eventObj.initEvent('eventyay:toastui-ready', false, false)
        }

        if (eventObj) window.dispatchEvent(eventObj)
    }

    const hasToastUi = () => !!window.toastui?.Editor

    const ensureLink = (href) => {
        if (!href) return
        const existing = document.querySelector(`link[rel="stylesheet"][href="${href}"]`)
        if (existing) return
        const link = document.createElement('link')
        link.rel = 'stylesheet'
        link.type = 'text/css'
        link.href = href
        document.head?.appendChild(link)
    }

    const ensureScript = (src, onReady) => {
        if (!src) return
        const existing = document.querySelector(`script[src="${src}"]`)
        if (existing) {
            if (hasToastUi()) {
                onReady?.()
            } else {
                existing.addEventListener?.('load', () => onReady?.(), { once: true })
            }
            return
        }

        const script = document.createElement('script')
        script.src = src
        script.defer = true
        script.addEventListener('load', () => onReady?.(), { once: true })
        document.head?.appendChild(script)
    }

    const loadToastUi = () => {
        if (window.__eventyayToastUiLoading || window.__eventyayToastUiLoaded) return
        window.__eventyayToastUiLoading = true

        ensureLink(toastUiCssUrl)

        ensureScript(toastUiJsUrl, () => {
            window.__eventyayToastUiLoading = false
            if (hasToastUi()) markLoaded()
        })
    }

    const checkNow = () => {
        if (document.querySelector(selector)) {
            loadToastUi()
            return true
        }
        return false
    }

    const startObserver = () => {
        if (!window.MutationObserver) return
        const observer = new MutationObserver(() => {
            if (checkNow()) observer.disconnect()
        })
        if (!document.documentElement) return
        observer.observe(document.documentElement, { childList: true, subtree: true })
    }

    const boot = () => {
        if (!toastUiCssUrl || !toastUiJsUrl) return
        if (checkNow()) return
        startObserver()
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot, { once: true })
    } else {
        boot()
    }
})()

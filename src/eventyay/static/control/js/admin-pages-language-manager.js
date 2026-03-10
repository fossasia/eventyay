/* Language visibility controls for admin page title/content fields. */

(() => {
    const defaultLocale = 'en'
    const groupConfigs = [
        {
            selector: '#id_title.i18n-form-group',
            fieldSelector: 'input[lang]',
            groupName: 'title',
        },
        {
            selector: '#id_text.i18n-form-group',
            fieldSelector: 'textarea[lang]',
            groupName: 'text',
        },
    ]

    const normalizeLocale = (value) => String(value || '').toLowerCase()
    const getContainer = (fieldEl) => fieldEl?.closest?.('.markdown-toastui-wrapper') || fieldEl

    const getFieldValue = (fieldEl) => {
        if (!fieldEl) return ''
        const editor = fieldEl.__eventyayToastUiEditor
        if (editor && typeof editor.getMarkdown === 'function') {
            return String(editor.getMarkdown() || '')
        }
        return String(fieldEl.value || '')
    }

    const clearFieldValue = (fieldEl) => {
        if (!fieldEl) return
        const editor = fieldEl.__eventyayToastUiEditor
        if (editor && typeof editor.setMarkdown === 'function') {
            editor.setMarkdown('')
        }
        fieldEl.value = ''
    }

    class LocaleGroupManager {
        constructor(config) {
            this.config = config
            this.group = null
            this.localeEntries = new Map()
            this.visibleLocales = new Set()
            this.localeHeaders = new Map()
            this.controlsWrap = null
            this.localeSelect = null
            this.addButton = null
            this.mutationObserver = null
            this.initialized = false
            this.rendering = false
        }

        ensureGroup() {
            if (this.group && document.body.contains(this.group)) return true
            this.group = document.querySelector(this.config.selector)
            if (this.group) this.group.classList.add('page-language-managed')
            return !!this.group
        }

        collectLocaleEntries() {
            if (!this.ensureGroup()) return
            const nextEntries = new Map()
            const fields = Array.from(this.group.querySelectorAll(this.config.fieldSelector))

            for (const fieldEl of fields) {
                const locale = normalizeLocale(fieldEl.getAttribute('lang') || fieldEl.lang)
                if (!locale || nextEntries.has(locale)) continue
                nextEntries.set(locale, {
                    locale,
                    label: fieldEl.getAttribute('title') || fieldEl.getAttribute('placeholder') || locale,
                    fieldEl,
                })
            }

            this.localeEntries = nextEntries
        }

        getDefaultLocale() {
            if (this.localeEntries.has(defaultLocale)) return defaultLocale
            const firstEntry = this.localeEntries.values().next()?.value
            return firstEntry?.locale || null
        }

        setLocaleVisible(entry, visible) {
            const container = getContainer(entry.fieldEl)
            if (!container) return
            container.hidden = !visible
            container.style.display = visible ? '' : 'none'
        }

        ensureControls() {
            if (this.controlsWrap) return

            this.controlsWrap = document.createElement('div')
            this.controlsWrap.className = 'page-language-controls'

            this.localeSelect = document.createElement('select')
            this.localeSelect.className = 'form-control input-sm'
            this.localeSelect.setAttribute('aria-label', 'Select language')

            this.addButton = document.createElement('button')
            this.addButton.type = 'button'
            this.addButton.className = 'btn btn-default btn-sm'
            this.addButton.textContent = 'Add language'
            this.addButton.addEventListener('click', () => {
                const locale = normalizeLocale(this.localeSelect?.value)
                if (!locale || !this.localeEntries.has(locale)) return

                this.visibleLocales.add(locale)
                this.render()

                const entry = this.localeEntries.get(locale)
                const editor = entry?.fieldEl?.__eventyayToastUiEditor
                if (editor && typeof editor.focus === 'function') {
                    editor.focus()
                    return
                }
                entry?.fieldEl?.focus?.()
            })

            this.controlsWrap.appendChild(this.localeSelect)
            this.controlsWrap.appendChild(this.addButton)
        }

        ensureHeader(entry, activeDefaultLocale) {
            if (entry.locale === activeDefaultLocale) return null

            let header = this.localeHeaders.get(entry.locale)
            if (header) return header

            header = document.createElement('div')
            header.className = 'page-language-header'

            const label = document.createElement('span')
            label.className = 'page-language-label'
            label.textContent = entry.label

            const removeButton = document.createElement('button')
            removeButton.type = 'button'
            removeButton.className = 'btn btn-default btn-xs page-language-remove'
            removeButton.textContent = 'Remove'
            removeButton.title = `Remove ${entry.label}`
            removeButton.addEventListener('click', () => {
                clearFieldValue(entry.fieldEl)
                this.visibleLocales.delete(entry.locale)
                this.render()
            })

            header.appendChild(label)
            header.appendChild(removeButton)
            this.localeHeaders.set(entry.locale, header)
            return header
        }

        placeControls(activeDefaultLocale) {
            if (!this.controlsWrap) return
            const defaultEntry = this.localeEntries.get(activeDefaultLocale) || this.localeEntries.values().next()?.value
            const defaultContainer = defaultEntry ? getContainer(defaultEntry.fieldEl) : null
            if (!defaultContainer?.parentNode) return

            if (this.controlsWrap.parentNode !== defaultContainer.parentNode || this.controlsWrap.previousSibling !== defaultContainer) {
                defaultContainer.parentNode.insertBefore(this.controlsWrap, defaultContainer.nextSibling)
            }
        }

        fillSelect(activeDefaultLocale) {
            if (!this.localeSelect || !this.addButton) return
            this.localeSelect.innerHTML = ''

            const placeholder = document.createElement('option')
            placeholder.value = ''
            placeholder.textContent = 'Select language'
            this.localeSelect.appendChild(placeholder)

            let optionCount = 0
            for (const entry of this.localeEntries.values()) {
                if (entry.locale === activeDefaultLocale) continue
                if (this.visibleLocales.has(entry.locale)) continue

                const option = document.createElement('option')
                option.value = entry.locale
                option.textContent = entry.label
                this.localeSelect.appendChild(option)
                optionCount += 1
            }

            this.localeSelect.disabled = optionCount === 0
            this.addButton.disabled = optionCount === 0
        }

        seedInitialVisibleLocales() {
            const activeDefaultLocale = this.getDefaultLocale()
            if (!activeDefaultLocale) return

            this.visibleLocales = new Set([activeDefaultLocale])

            for (const entry of this.localeEntries.values()) {
                if (entry.locale === activeDefaultLocale) continue
                if (getFieldValue(entry.fieldEl).trim().length > 0) {
                    this.visibleLocales.add(entry.locale)
                }
            }
        }

        startObserver() {
            if (!window.MutationObserver || this.mutationObserver || !this.group) return
            this.mutationObserver = new MutationObserver(() => this.render())
            this.mutationObserver.observe(this.group, { childList: true })
        }

        render() {
            if (this.rendering) return
            if (!this.ensureGroup()) return

            this.collectLocaleEntries()
            const activeDefaultLocale = this.getDefaultLocale()
            if (!activeDefaultLocale) return

            this.rendering = true
            this.visibleLocales.add(activeDefaultLocale)

            for (const entry of this.localeEntries.values()) {
                const visible = this.visibleLocales.has(entry.locale)
                this.setLocaleVisible(entry, visible)

                const header = this.ensureHeader(entry, activeDefaultLocale)
                if (!header) continue

                const container = getContainer(entry.fieldEl)
                if (!container?.parentNode) continue

                if (visible) {
                    if (header.parentNode !== container.parentNode || header.nextSibling !== container) {
                        container.parentNode.insertBefore(header, container)
                    }
                    header.hidden = false
                    header.style.display = ''
                } else {
                    header.hidden = true
                    header.style.display = 'none'
                }
            }

            this.ensureControls()
            this.placeControls(activeDefaultLocale)
            this.fillSelect(activeDefaultLocale)

            this.rendering = false
        }

        init() {
            if (!this.ensureGroup()) return
            this.collectLocaleEntries()
            if (!this.localeEntries.size) return

            if (!this.initialized) {
                this.seedInitialVisibleLocales()
                this.initialized = true
                this.startObserver()
            }

            this.render()
        }
    }

    const managers = groupConfigs.map((config) => new LocaleGroupManager(config))
    const initAll = () => managers.forEach((manager) => manager.init())

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll, { once: true })
    } else {
        initAll()
    }

    window.addEventListener('eventyay:toastui-ready', () => {
        window.setTimeout(initAll, 0)
    })
})()

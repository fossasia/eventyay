/* This script will be included on all pages with forms.
 * (And on all pages on the backend in general). */

let eventyayToastuiIdSeq = 0

const createEventyayUnderlinePlugin = () => {
    const convertUnderlineSyntax = (src) => {
        const input = String(src || "")
        if (!input.includes('++')) return input

        const codeSpanRe = /(`+)([\s\S]*?)\1/g
        let out = ''
        let last = 0
        let match

        const convertTextSegment = (segment) =>
            segment.replace(/\+\+([^\n]+?)\+\+/g, '<u>$1</u>')

        while ((match = codeSpanRe.exec(input)) !== null) {
            const start = match.index
            const end = start + match[0].length
            out += convertTextSegment(input.slice(last, start))
            out += match[0]
            last = end
        }

        out += convertTextSegment(input.slice(last))
        return out
    }

    const applyParser = (node, { entering }) => {
        if (!entering) return
        if (!node || typeof node.stringContent !== 'string') return
        node.stringContent = convertUnderlineSyntax(node.stringContent)
    }

    const toggleMark = (markType, state, dispatch) => {
        if (!markType) return false
        const { from, to, empty, $from } = state.selection

        let tr = state.tr
        if (empty) {
            const active = markType.isInSet(state.storedMarks || $from.marks())
            tr = active
                ? tr.removeStoredMark(markType)
                : tr.addStoredMark(markType.create())
        } else {
            const active = state.doc.rangeHasMark(from, to, markType)
            tr = active
                ? tr.removeMark(from, to, markType)
                : tr.addMark(from, to, markType.create())
        }

        if (dispatch) dispatch(tr.scrollIntoView())
        return true
    }

    return (context) => ({
        toHTMLRenderers: {
            htmlInline: {
                u(node, { entering }) {
                    return entering
                        ? { type: 'openTag', tagName: 'u' }
                        : { type: 'closeTag', tagName: 'u' }
                },
            },
        },
        toMarkdownRenderers: {
            u() {
                return { rawHTML: ['<u>', '</u>'] }
            },
        },
        markdownParsers: {
            paragraph: applyParser,
            heading: applyParser,
            tableCell: applyParser,
        },
        markdownCommands: {
            underline(payload, state, dispatch) {
                const markType = state.schema.marks.u
                if (markType) return toggleMark(markType, state, dispatch)
                const TextSelection = context?.pmState?.TextSelection
                const { from, to, empty } = state.selection
                let tr = state.tr

                const openTag = '<u>'
                const closeTag = '</u>'

                if (empty) {
                    tr = tr.insertText(`${openTag}${closeTag}`, from, to)
                    if (TextSelection) {
                        tr = tr.setSelection(TextSelection.create(tr.doc, from + openTag.length, from + openTag.length))
                    }
                } else {
                    tr = tr.insertText(closeTag, to, to)
                    tr = tr.insertText(openTag, from, from)
                }

                if (dispatch) dispatch(tr.scrollIntoView())
                return true
            },
        },
        wysiwygCommands: {
            underline(payload, state, dispatch) {
                return toggleMark(state.schema.marks.u, state, dispatch)
            },
        },
    })
}

const initToastUiMarkdownTextarea = (textarea) => {
    if (!textarea || textarea.dataset.toastuiBound === 'true') return
    if (!window.toastui?.Editor) return

    if (!textarea.parentNode) return

    textarea.dataset.toastuiBound = 'true'

    const wrapper = document.createElement('div')
    wrapper.className = 'markdown-toastui-wrapper'

    const mount = document.createElement('div')
    mount.className = 'markdown-toastui'
    mount.setAttribute('data-md-toastui', 'true')

    textarea.parentNode.insertBefore(wrapper, textarea)
    wrapper.appendChild(mount)
    wrapper.appendChild(textarea)

    textarea.classList.add('d-none')
    textarea.hidden = true
    textarea.style.display = 'none'

    const underlinePlugin = createEventyayUnderlinePlugin()
    const makeSimpleIconButton = ({ name, tooltip, command, extraClassName }) => {
        const button = document.createElement('button')
        button.type = 'button'
        button.className = `toastui-editor-toolbar-icons ${extraClassName || ''}`.trim()
        button.setAttribute('aria-label', tooltip)
        button.title = tooltip
        button.addEventListener('mousedown', (event) => event.preventDefault())

        return {
            name,
            tooltip,
            el: button,
            onMounted(execCommand) {
                button.addEventListener('click', () => execCommand(command))
            },
            onUpdated({ active, disabled }) {
                button.disabled = !!disabled
                button.classList.toggle('active', !!active)
            },
        }
    }

    const undoToolbarItem = makeSimpleIconButton({
        name: 'eventyayUndo',
        tooltip: window.eventyayEditorConfig?.t?.undo || 'Undo',
        command: 'undo',
        extraClassName: 'eventyay-undo',
    })

    const redoToolbarItem = makeSimpleIconButton({
        name: 'eventyayRedo',
        tooltip: window.eventyayEditorConfig?.t?.redo || 'Redo',
        command: 'redo',
        extraClassName: 'eventyay-redo',
    })

    const underlineToolbarItem = (() => {
        const button = document.createElement('button')
        const underlineLabel = window.eventyayEditorConfig?.t?.underline || 'Underline'
        button.type = 'button'
        button.className = 'toastui-editor-toolbar-icons eventyay-underline'
        button.setAttribute('aria-label', underlineLabel)
        button.title = underlineLabel
        button.addEventListener('mousedown', (event) => event.preventDefault())

        return {
            name: 'underline',
            tooltip: underlineLabel,
            el: button,
            onMounted(execCommand) {
                button.addEventListener('click', () => execCommand('underline'))
            },
            onUpdated({ active, disabled }) {
                button.disabled = !!disabled
                button.classList.toggle('active', !!active)
            },
        }
    })()

    const editor = new window.toastui.Editor({
        el: mount,
        height: textarea.dataset.editorHeight || '320px',
        initialEditType: 'wysiwyg',
        previewStyle: 'vertical',
        usageStatistics: false,
        hideModeSwitch: true,
        initialValue: String(textarea.value || ''),
        plugins: [underlinePlugin],
        toolbarItems: [
            [undoToolbarItem, redoToolbarItem, 'heading', 'bold', 'italic', underlineToolbarItem, 'quote'],
            ['ul', 'ol', 'hr', 'link'],
        ],
    })
    textarea.__eventyayToastUiEditor = editor
    mount.__eventyayToastUiEditor = editor

    const fieldLang = textarea.getAttribute('lang') || textarea.lang
    if (fieldLang) {
        const ww = mount.querySelector?.('.toastui-editor-ww-container')
        if (ww) ww.setAttribute('lang', fieldLang)
        const md = mount.querySelector?.('.toastui-editor-md-container')
        if (md) md.setAttribute('lang', fieldLang)
    }

    const installAbsoluteLinkOnlyValidation = () => {
        if (!window.MutationObserver) return () => { }

        const root = mount.querySelector?.('.toastui-editor-defaultUI')
        if (!root || root.dataset.eventyayAbsoluteLinkOnlyBound === 'true') return () => { }

        root.dataset.eventyayAbsoluteLinkOnlyBound = 'true'

        const isAbsoluteHttpUrl = (value) => {
            const url = String(value || '').trim()
            if (!url) return false
            if (!/^https?:\/\//i.test(url)) return false
            try {
                const parsed = new URL(url)
                if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return false
                return Boolean(parsed.hostname)
            } catch {
                return false
            }
        }

        const enhancePopup = (popupEl) => {
            if (!popupEl || popupEl.dataset.eventyayEnhanced === 'true') return
            popupEl.dataset.eventyayEnhanced = 'true'

            const inputs = popupEl.querySelectorAll('input[type="text"]')
            const urlInput = inputs?.[0]
            if (!(urlInput instanceof HTMLInputElement)) return

            urlInput.placeholder = 'https://example.com'

            const okButton = popupEl.querySelector('button.toastui-editor-ok-button')
            const idSeq = ++eventyayToastuiIdSeq
            const helpId = `eventyay-toastui-link-help-${idSeq}`
            const errorId = `eventyay-toastui-link-error-${idSeq}`

            const helpText = document.createElement('div')
            helpText.className = 'eventyay-toastui-link-help'
            helpText.id = helpId
            helpText.textContent = 'Use an absolute URL starting with https:// or http://'

            const errorText = document.createElement('div')
            errorText.className = 'eventyay-toastui-link-error'
            errorText.id = errorId
            errorText.textContent = 'Please enter a valid absolute URL.'
            errorText.hidden = true

            let showError = false

            const describedBy = [urlInput.getAttribute('aria-describedby'), helpId, errorId]
                .filter(Boolean)
                .join(' ')
            urlInput.setAttribute('aria-describedby', describedBy)

            if (typeof urlInput.insertAdjacentElement === 'function') {
                urlInput.insertAdjacentElement('afterend', errorText)
                urlInput.insertAdjacentElement('afterend', helpText)
            } else if (urlInput.parentNode) {
                const parent = urlInput.parentNode
                const next = urlInput.nextSibling
                parent.insertBefore(helpText, next)
                parent.insertBefore(errorText, helpText.nextSibling)
            }

            const updateState = () => {
                const valid = isAbsoluteHttpUrl(urlInput.value)
                const hasValue = String(urlInput.value || '').trim().length > 0
                const shouldShowError = !valid && (hasValue || showError)

                if (okButton instanceof HTMLButtonElement) {
                    okButton.disabled = !valid
                }

                errorText.hidden = !shouldShowError
                urlInput.classList.toggle('wrong', shouldShowError)
            }

            urlInput.addEventListener('input', updateState)
            urlInput.addEventListener('change', updateState)
            urlInput.addEventListener('blur', () => {
                showError = true
                updateState()
            })

            if (okButton instanceof HTMLButtonElement) {
                okButton.addEventListener(
                    'click',
                    (event) => {
                        const valid = isAbsoluteHttpUrl(urlInput.value)
                        if (valid) return
                        showError = true
                        event.preventDefault()
                        event.stopPropagation()
                        updateState()
                        if (typeof urlInput.focus === 'function') urlInput.focus()
                    },
                    true
                )
            }

            updateState()
        }

        const popupObserver = new MutationObserver(() => {
            const popupEl = root.querySelector?.('.toastui-editor-popup-add-link')
            if (popupEl) enhancePopup(popupEl)
        })

        popupObserver.observe(root, { childList: true, subtree: true })

        const existingPopup = root.querySelector?.('.toastui-editor-popup-add-link')
        if (existingPopup) enhancePopup(existingPopup)

        return () => popupObserver.disconnect()
    }

    installAbsoluteLinkOnlyValidation()

    const root = mount.querySelector?.('.toastui-editor-defaultUI')
    root?.addEventListener?.('click', (event) => {
        if (typeof event.detail === 'number' && event.detail > 1) return
        const selection = window.getSelection?.()
        if (selection && !selection.isCollapsed) return

        const target = event.target
        if (!(target instanceof Element)) return
        if (target.closest('.toastui-editor-defaultUI-toolbar')) return
        if (target.closest('.toastui-editor-popup, .toastui-editor-modal')) return
        if (target.closest('[contenteditable="true"], textarea, input')) return
        if (target.closest('.ProseMirror')) return
        if (target.closest('.toastui-editor-md-container')) return
        if (!target.closest('.toastui-editor-main')) return

        if (typeof editor.focus === 'function') editor.focus()
    })

    const modeSwitch = mount.querySelector?.('.toastui-editor-mode-switch')
    if (modeSwitch instanceof HTMLElement) {
        modeSwitch.classList?.add('d-none')
        modeSwitch.hidden = true
        modeSwitch.style.display = 'none'
    }

    const syncToTextarea = () => {
        if (typeof editor.getMarkdown !== 'function') return
        textarea.value = editor.getMarkdown()
    }

    if (typeof editor.on === 'function') editor.on('change', syncToTextarea)

    let isMarkdownMode = false

    const updateModeToggleUi = (toggleButton) => {
        if (!(toggleButton instanceof HTMLButtonElement)) return
        const label = isMarkdownMode ? 'RTF' : 'MD'
        const title = isMarkdownMode ? 'View as Rich Text' : 'View as Markdown'
        toggleButton.textContent = label
        toggleButton.title = title
        toggleButton.setAttribute('aria-label', title)
        toggleButton.setAttribute('aria-pressed', isMarkdownMode ? 'true' : 'false')
    }

    const insertToggleIntoToolbar = () => {
        const toolbarRoot = mount.querySelector?.('.toastui-editor-defaultUI-toolbar')
        if (!toolbarRoot) return null

        const toggleWrap = document.createElement('div')
        toggleWrap.className = 'eventyay-toastui-md-toggle-wrap'

        const toggleButton = document.createElement('button')
        toggleButton.type = 'button'
        toggleButton.className = 'eventyay-toastui-md-toggle-btn'
        updateModeToggleUi(toggleButton)

        toggleWrap.appendChild(toggleButton)
        toolbarRoot.appendChild(toggleWrap)
        return toggleButton
    }

    const toggleButton = insertToggleIntoToolbar()
    if (toggleButton) {
        toggleButton.addEventListener('click', () => {
            isMarkdownMode = !isMarkdownMode
            updateModeToggleUi(toggleButton)

            if (typeof editor.changeMode === 'function') {
                editor.changeMode(isMarkdownMode ? 'markdown' : 'wysiwyg', true)
            }

            syncToTextarea()
        })
        updateModeToggleUi(toggleButton)
    }

    // Ensure we always submit the latest value.
    textarea.form?.addEventListener?.('submit', syncToTextarea)

    syncToTextarea()
}

const upgradeMarkdownEditors = (root) => {
    const searchRoot = root || document
    if (!searchRoot?.querySelectorAll) return
    searchRoot
        .querySelectorAll('textarea[data-markdown-field="true"], .markdown-wrapper textarea')
        .forEach((element) => initToastUiMarkdownTextarea(element))
}

const startMarkdownEditorObserver = () => {
    if (typeof window === 'undefined') return
    if (window.__eventyayMarkdownEditorObserverStarted) return
    if (!window.MutationObserver) return

    const selector = 'textarea[data-markdown-field="true"], .markdown-wrapper textarea'
    const isInsideToastUiEditor = (element) =>
        !!element?.closest?.('.toastui-editor-defaultUI, .markdown-toastui-wrapper, .markdown-toastui')

    const observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            // ProseMirror (Toast UI) mutates the DOM while typing; ignore those mutations.
            if (mutation.target instanceof Element && isInsideToastUiEditor(mutation.target)) {
                continue
            }
            if (!mutation.addedNodes || mutation.addedNodes.length === 0) continue
            for (const node of mutation.addedNodes || []) {
                if (!(node instanceof Element)) continue
                if (isInsideToastUiEditor(node)) continue
                if (
                    node.matches?.(selector)
                ) {
                    initToastUiMarkdownTextarea(node)
                    continue
                }
                const nested = node.querySelectorAll?.(selector)
                if (nested && nested.length) {
                    nested.forEach((el) => initToastUiMarkdownTextarea(el))
                }
            }
        }
    })

    const observeRoot = document.body || document.documentElement
    if (!observeRoot) return
    observer.observe(observeRoot, { childList: true, subtree: true })
    window.__eventyayMarkdownEditorObserverStarted = true
}

const warnFileSize = (element) => {
    const warning = document.createElement("div")
    warning.classList = ["invalid-feedback"]
    warning.textContent = element.dataset.sizewarning
    element.parentElement.appendChild(warning)
    element.classList.add("is-invalid")
}
const unwarnFileSize = (element) => {
    element.classList.remove("is-invalid")
    const warning = element.parentElement.querySelector(".invalid-feedback")
    if (warning) element.parentElement.removeChild(warning)
}

const initFileSizeCheck = (element) => {
    const checkFileSize = () => {
        const files = element.files
        if (!files || !files.length) {
            unwarnFileSize(element)
        } else {
            maxsize = parseInt(element.dataset.maxsize)
            if (files[0].size > maxsize) {
                warnFileSize(element)
            } else {
                unwarnFileSize(element)
            }
        }
    }
    element.addEventListener("change", checkFileSize, false)
}

const isVisible = (element) => {
    if (!element) return false
    return !element.hidden && !element.classList.contains("d-none") && !element.style.display === "none"
}

const initSelect = (element) => {
    const removeItemButton =
        !element.readonly && (!element.required || element.multiple)
    let showPlaceholder = !!element.title
    if (showPlaceholder) {
        // Make sure we don't show a placeholder that is obvious from context
        if (element.getAttribute("aria-describedby")) {
            const describedBy = document.getElementById(
                element.getAttribute("aria-describedby"),
            )
            if (isVisible(describedBy)) {
                showPlaceholder = describedBy.textContent !== element.title
            }
        }
    }
    if (showPlaceholder) {
        const label = document.querySelector(`label[for=${element.id}]`)
        if (isVisible(label)) {
            showPlaceholder = label.textContent !== element.title
        }
    }
    const realPlaceholder = element.getAttribute("placeholder")
    showPlaceholder = showPlaceholder || (realPlaceholder && realPlaceholder.length > 0)
    const choicesOptions = {
        removeItems: !element.readonly,
        removeItemButton:
            !element.readonly && (!element.required || element.multiple),
        removeItemButtonAlignLeft: true,
        searchFields: ["label"],
        searchEnabled: true,
        searchResultLimit: -1,
        resetScrollPosition: false,
        shouldSort: false,
        placeholderValue: showPlaceholder ? (element.title || realPlaceholder) : null,
        itemSelectText: "",
        addItemText: "",
        removeItemLabelText: "×",
        removeItemIconText: "×",
        maxItemText: "",
        allowHTML: true,
    }
    if (element.querySelectorAll("option[data-description]").length || element.querySelectorAll("option[data-color]").length) {
        choicesOptions.callbackOnCreateTemplates = (strToEl, escapeForTemplates, getClassNames) => ({
            choice: (allowHTML, classNames, choice, selectedText, groupName) => {
                let originalResult = Choices.defaults.templates.choice(allowHTML, classNames, choice, selectedText, groupName)
                if (classNames.element && classNames.element.dataset.description && classNames.element.dataset.description.length > 0) {
                    originalResult.innerHTML += `<div class="choice-item-description">${classNames.element.dataset.description}</div>`
                }
                if (classNames.element && classNames.element.dataset.color && classNames.element.dataset.color.length > 0) {
                    let color = classNames.element.dataset.color
                    if (color.startsWith("--")) {
                        color = `var(${color})`
                    }
                    originalResult.classList.add("choice-item-color")
                    originalResult.style.setProperty("--choice-color", color)
                }
                return originalResult
            },
            item: (_a, choice, removeItemButton) => {
                let originalResult = Choices.defaults.templates.item(_a, choice, removeItemButton)
                if (choice.element && choice.element.dataset.color && choice.element.dataset.color.length > 0) {
                    let color = choice.element.dataset.color
                    if (color.startsWith("--")) {
                        color = `var(${color})`
                    }
                    originalResult.classList.add("choice-item-color")
                    originalResult.style.setProperty("--choice-color", color)
                }
                return originalResult
            }
        })
    }
    new Choices(element, choicesOptions)
}

const originalData = {}

const handleUnload = (e) => {
    const form = e.target.form
    if (isDirty(form)) {
        e.preventDefault()
    }
}

const isDirty = (form) => {
    if (!!!form) return false
    if (Object.keys(originalData[form.id]).length === 0) return false
    const currentData = {}
    new FormData(form).forEach((value, key) => (currentData[key] = value))
    /* We have to compare all the current form's fields individually, because
     * there may be multiple forms with no/the same ID on the page. */
    for (const key in currentData) {
        if (JSON.stringify(currentData[key]) !== JSON.stringify(originalData[form.id][key])) {
            return true
        }
    }
    return false
}


// Make sure the main form doesn't have unsaved changes before leaving
const initFormChanges = (form) => {
    // Populate original data after a short delay to make sure the form is fully loaded
    // and that any script interactions have run
    setTimeout(() => {
        originalData[form.id] = {}
        new FormData(form).forEach((value, key) => (originalData[form.id][key] = value))
    }, 1000)

    form.addEventListener("submit", () => {
        window.removeEventListener("beforeunload", handleUnload)
    })
    window.addEventListener("beforeunload", handleUnload)
}

const initFormButton = (form) => {
    form.querySelectorAll("button[type=submit]").forEach(submitButton => {
        const submitButtonText = submitButton.textContent
        let lastSubmit = 0
        form.addEventListener("submit", () => {
            // We can't disable the button immediately, because then, the browser will
            // not send the button's value to the server. Instead, we'll just delay the
            // disabling a bit.
            submitButton.innerHTML = `<i class="fa fa-spinner fa-spin pr-0"></i> ${submitButtonText}`
            lastSubmit = Date.now()
            setTimeout(() => {
                submitButton.classList.add("disabled")
            }, 1)
        })

        // If people submit the form, then navigate back with the back button,
        // the button will still be disabled.
        // We can’t fix this on page load, because the browser will not actually load
        // the page again, and we can’t fix it via a single timeout, because that might
        // take place while we’re away from the page.
        // So instead, we’ll check periodically if the button is still disabled, and if
        // it’s been more than 5 seconds since the last submit, we’ll re-enable it.
        const checkButton = () => {
            if (submitButton.classList.contains("disabled")) {
                if (Date.now() - lastSubmit > 5000) {
                    submitButton.classList.remove("disabled")
                    submitButton.innerHTML = submitButtonText
                }
            }
        }
        window.setInterval(checkButton, 1000)
    })
}

const addDateLimit = (element, other, limit) => {
    const otherElement = document.querySelector(other)
    if (otherElement) {
        otherElement.addEventListener("change", () => {
            element.setAttribute(limit, otherElement.value)
        })
        element.setAttribute(limit, otherElement.value)
    }
}

const initTextarea = (element, other, limit) => {
    const submitButtons = Array.from(element.form.querySelectorAll("button, input[type=submit]")).filter(button => !button.disabled && button.type === "submit")
    const buttonsWithName = submitButtons.filter(button => button.name.length > 0)
    if (submitButtons.length <= 1 && buttonsWithName.length === 0) {
        // We use classic form submit whenever we can, to be on the safe side
        element.addEventListener("keydown", (ev) => {
            if (ev.key === "Enter" && ev.ctrlKey) {
                ev.preventDefault()
                // We need to remove the "are you sure" dialog that will show now otherwise
                window.removeEventListener("beforeunload", handleUnload)
                element.form.removeEventListener("submit", handleUnload)
                element.form.submit()
            }
        })
    } else {
        // But if there are multiple submit buttons, we click the first one,
        // to make sure the correct name/value is attached to the form data
        element.addEventListener("keydown", (ev) => {
            if (ev.key === "Enter" && ev.ctrlKey) {
                ev.preventDefault()
                submitButtons[0].click()
            }
        })
    }
}

// Handle date and datetime fields:
// - Make sure the picker opens on focus
// - Use the data-date-after and data-date-before attributes to set min/max dynamically on change
const initDateFields = () => {
    document
        .querySelectorAll("input[type=date], input[type=datetime-local]")
        .forEach((element) => {
            if (element.readOnly || element.disabled) return
            // Delay, because otherwise clicking the *icon* in FF will make the picker immediately disappear again
            element.addEventListener("focus", () =>
                setTimeout(() => element.showPicker(), 70),
            )
            if (element.dataset.dateBefore)
                addDateLimit(element, element.dataset.dateBefore, "max")
            if (element.dataset.dateAfter)
                addDateLimit(element, element.dataset.dateAfter, "min")
        })
}

if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
    window.addEventListener('eventyay:toastui-ready', () => {
        upgradeMarkdownEditors(document)
        startMarkdownEditorObserver()
    })
    if (window.__eventyayToastUiLoaded) {
        upgradeMarkdownEditors(document)
        startMarkdownEditorObserver()
    }
}

/**
 * Wrap bare <input type="file"> elements with a styled button + filename label,
 * matching the pattern used in common/avatar.html.
 * Skips inputs already inside .avatar-upload (handled by profile.js)
 * or already wrapped by a previous call.
 *
 * Translated labels come from the hidden #eventyay-file-input-i18n div
 * rendered by forms_header.html via Django's {% translate %} tags.
 */
let _fileInputIdCounter = 0
const initFileInputWrappers = () => {
    const i18nEl = document.getElementById('eventyay-file-input-i18n')
    const defaultChooseLabel = i18nEl?.dataset?.chooseFile || 'Choose file'
    const defaultNoFileLabel = i18nEl?.dataset?.noFile || 'No file chosen'

    document.querySelectorAll('input[type="file"]').forEach((input) => {
        // Skip if already handled by the avatar template or already wrapped
        if (input.closest('.avatar-upload')) return
        if (input.closest('.eventyay-file-pick-wrapper')) return
        if (input.dataset.eventyayFileWrapped === 'true') return
        // Allow explicit opt-out for integrations that manage their own file UI
        if (input.dataset.eventyayFileWrapper === 'disabled') return
        // Skip inputs that are already inside known custom upload/button wrappers
        if (input.closest('.fileinput-button')) return
        if (input.closest('.btn')) return

        input.dataset.eventyayFileWrapped = 'true'

        const chooseLabel = input.dataset.chooseFileLabel || defaultChooseLabel
        const noFileText = input.dataset.noFileLabel || defaultNoFileLabel

        // Build the wrapper
        const wrapper = document.createElement('div')
        wrapper.className = 'eventyay-file-pick-wrapper'

        // Delegate clicks on the wrapper (e.g. the white area) to the input
        wrapper.addEventListener('click', (event) => {
            if (event.target !== label && event.target !== input) {
                input.click()
            }
        })

        // Styled button label
        const label = document.createElement('label')
        label.setAttribute('for', input.id || '')
        label.textContent = chooseLabel

        // Filename display span
        const nameSpan = document.createElement('span')
        nameSpan.className = 'eventyay-file-name text-muted small ms-2'
        nameSpan.dataset.noFile = noFileText
        nameSpan.textContent = noFileText

        // Insert wrapper before the input, then move input inside
        input.parentNode.insertBefore(wrapper, input)
        wrapper.appendChild(label)
        wrapper.appendChild(nameSpan)
        wrapper.appendChild(input)

        // If input has no id, generate one so the label works
        if (!input.id) {
            input.id = 'eventyay-file-' + (++_fileInputIdCounter)
            label.setAttribute('for', input.id)
        }

        // Update filename display on change
        input.addEventListener('change', () => {
            nameSpan.textContent = (input.files && input.files.length > 0)
                ? input.files[0].name
                : noFileText
        })
    })
}

/* Register handlers */
onReady(() => {
    upgradeMarkdownEditors(document)
    startMarkdownEditorObserver()
    initFileInputWrappers()
    document
        .querySelectorAll("input[data-maxsize][type=file]")
        .forEach((element) => initFileSizeCheck(element))
    document
        .querySelectorAll("select.enhanced")
        .forEach((element) => initSelect(element))
    document
        .querySelectorAll("form[method=post]")
        .forEach((form) => {
            initFormChanges(form)
            initFormButton(form)
        })
    document.querySelectorAll("form textarea").forEach(element => initTextarea(element))
    initDateFields()
})

/**
 * Shared session video URL row controller and entry points.
 * Standardizes row management, limits, and controls between the quick-edit
 * modal dialog on the proposals list and the proposal edit formset.
 */

let submissionVideoController = null

function readCsrfToken() {
    const prefix = 'eventyay_csrftoken='
    const cookie = document.cookie
        .split(';')
        .map((part) => part.trim())
        .find((part) => part.startsWith(prefix))
    if (!cookie) {
        throw new Error('Missing CSRF cookie eventyay_csrftoken')
    }
    return decodeURIComponent(cookie.slice(prefix.length))
}

/**
 * Creates and binds a unified session video row list manager.
 *
 * @param {Object} options
 * @param {HTMLElement} options.container - Container holding the row elements.
 * @param {HTMLTemplateElement} [options.rowTemplate] - Template element used to clone new rows.
 * @param {HTMLButtonElement} [options.addButton] - Button that appends a new row.
 * @param {HTMLButtonElement} [options.clearButton] - Button that clears all rows.
 * @param {number} [options.maxRows=20] - Maximum allowed URL rows.
 * @param {string} [options.urlLabel] - Accessible label for the URL input.
 * @param {string} [options.removeLabel] - Accessible label and tooltip for the remove button.
 * @param {string} [options.inputName] - Name attribute for created inputs.
 * @param {Function} [options.onClear] - Optional callback triggered on clear.
 * @param {Function} [options.onChange] - Optional callback triggered when rows are added/removed.
 * @returns {Object} Row manager API.
 */
function createSessionVideoRowList({
    container,
    rowTemplate = null,
    addButton = null,
    clearButton = null,
    maxRows = 20,
    urlLabel = 'YouTube, Vimeo, or Wikimedia Commons URL',
    removeLabel = 'Remove',
    inputName = 'session_video_urls',
    onClear = null,
    onChange = null,
}) {
    let rowIndex = 0

    const getRows = () => Array.from(
        container.querySelectorAll('.submission-video-url-row, [data-session-video-row]')
    )

    const isAtLimit = () => Number.isFinite(maxRows) && getRows().length >= maxRows

    const syncControls = () => {
        if (addButton) {
            addButton.disabled = isAtLimit()
        }
        onChange?.()
    }

    const bindRemoveButton = (row) => {
        const removeBtn = row.querySelector('.submission-video-remove, [data-session-video-remove]')
        if (!removeBtn || removeBtn.dataset.sessionVideoBound === 'true') return
        removeBtn.dataset.sessionVideoBound = 'true'
        removeBtn.addEventListener('click', (event) => {
            event.preventDefault()
            row.remove()
            if (getRows().length === 0) {
                addRow('')
            }
            syncControls()
        })
    }

    const addRow = (value = '') => {
        if (isAtLimit()) return null
        rowIndex += 1

        let row = null
        if (rowTemplate instanceof HTMLTemplateElement) {
            const fragment = rowTemplate.content.cloneNode(true)
            row = fragment.querySelector('[data-session-video-row]') || fragment.firstElementChild
            if (row) {
                const input = row.querySelector('input')
                if (input) {
                    input.value = value
                }
            }
        }

        if (!row) {
            row = document.createElement('div')
            row.className = 'submission-video-url-row'
            row.setAttribute('data-session-video-row', '')
            const inputId = `submission-video-url-input-${rowIndex}`
            row.innerHTML = `
                <div class="form-group form-group-inline">
                    <label for="${inputId}"></label>
                    <div class="submission-video-url-controls">
                        <input
                            type="text"
                            class="form-control"
                            id="${inputId}"
                            name="${inputName}"
                            inputmode="url"
                            placeholder="https://www.youtube.com/watch?v=…"
                            autocomplete="off"
                            autocapitalize="off"
                            spellcheck="false"
                            data-lpignore="true"
                        >
                        <button type="button" class="btn btn-sm btn-outline-danger submission-video-remove" data-session-video-remove>
                            <i class="fa fa-trash" aria-hidden="true"></i>
                        </button>
                    </div>
                </div>
            `
            const label = row.querySelector('label')
            if (label) label.textContent = urlLabel
            const removeBtn = row.querySelector('.submission-video-remove')
            if (removeBtn) {
                removeBtn.title = removeLabel
                removeBtn.setAttribute('aria-label', removeLabel)
            }
            const input = row.querySelector('input')
            if (input) {
                input.value = value
                input.setAttribute('aria-label', urlLabel)
            }
        }

        bindRemoveButton(row)
        container.appendChild(row)
        syncControls()
        return row.querySelector('input')
    }

    const clearAll = () => {
        if (typeof onClear === 'function') {
            onClear()
            return
        }
        container.innerHTML = ''
        const input = addRow('')
        if (input) input.focus()
    }

    const setValues = (urls) => {
        container.innerHTML = ''
        const values = Array.isArray(urls) && urls.length > 0 ? urls : ['']
        values.slice(0, maxRows).forEach((url) => {
            addRow(url)
        })
    }

    const getValues = () => {
        return Array.from(container.querySelectorAll('input'))
            .map((input) => input.value.trim())
            .filter(Boolean)
    }

    // Bind any existing server-rendered rows
    const initialRows = getRows()
    if (initialRows.length > 0) {
        initialRows.forEach(bindRemoveButton)
    } else {
        addRow('')
    }
    syncControls()

    if (addButton && addButton.dataset.sessionVideoBound !== 'true') {
        addButton.dataset.sessionVideoBound = 'true'
        addButton.addEventListener('click', (event) => {
            event.preventDefault()
            const input = addRow('')
            if (input) input.focus()
        })
    }

    if (clearButton && clearButton.dataset.sessionVideoBound !== 'true') {
        clearButton.dataset.sessionVideoBound = 'true'
        clearButton.addEventListener('click', (event) => {
            event.preventDefault()
            clearAll()
        })
    }

    return {
        addRow,
        clearAll,
        getRows,
        getValues,
        setValues,
        syncControls,
    }
}

const getSubmissionVideoDialog = () => {
    if (submissionVideoController) return submissionVideoController

    const dialog = document.getElementById('submission-video-dialog')
    const form = document.getElementById('submission-video-form')
    const listEl = document.getElementById('submission-video-url-list')
    const errorEl = document.getElementById('submission-video-error')
    const titleEl = document.getElementById('submission-video-session-title')
    const clearBtn = document.getElementById('submission-video-clear')
    const addBtn = document.getElementById('submission-video-add')
    if (!dialog || !form || !listEl) return null

    let activeButton = null
    let saveUrl = ''

    const showError = (message) => {
        if (!errorEl) return
        errorEl.textContent = message || ''
        errorEl.classList.toggle('d-none', !message)
    }

    const parseUrlsFromButton = (button) => {
        const raw = button?.dataset?.videoUrls
        if (!raw) return []
        try {
            const parsed = JSON.parse(raw)
            if (!Array.isArray(parsed)) return []
            return parsed.map((item) => String(item).trim()).filter(Boolean)
        } catch (parseError) {
            console.error('Failed to parse session video URLs', parseError)
            return []
        }
    }

    const setButtonState = (button, urls) => {
        if (!button) return
        const list = Array.isArray(urls) ? urls.filter(Boolean) : []
        button.dataset.videoUrls = JSON.stringify(list)
        button.classList.toggle('btn-success', list.length > 0)
        button.classList.toggle('btn-outline-secondary', list.length === 0)
        const label = list.length > 0
            ? (button.dataset.editLabel || 'Edit video links')
            : (button.dataset.addLabel || 'Add video links')
        button.title = label
        button.setAttribute('aria-label', label)
    }

    const maxRows = Number.parseInt(dialog.dataset.maxRows || '20', 10)
    const urlLabel = dialog.dataset.urlLabel || 'YouTube, Vimeo, or Wikimedia Commons URL'
    const removeLabel = dialog.dataset.removeLabel || 'Remove'

    const rowList = createSessionVideoRowList({
        container: listEl,
        addButton: addBtn,
        clearButton: clearBtn,
        maxRows,
        urlLabel,
        removeLabel,
        onClear: () => {
            save([])
        },
    })

    const openForButton = (button) => {
        activeButton = button
        saveUrl = button.dataset.url || ''
        if (titleEl) {
            titleEl.textContent = button.dataset.title || ''
        }
        rowList.setValues(parseUrlsFromButton(button))
        showError('')
        if (typeof dialog.showModal === 'function' && !dialog.open) {
            dialog.showModal()
            const firstInput = listEl.querySelector('input')
            if (firstInput) {
                firstInput.focus({ preventScroll: true })
            }
        }
    }

    const save = async (urls) => {
        if (!saveUrl) return
        showError('')
        try {
            const response = await fetch(saveUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': readCsrfToken(),
                },
                credentials: 'include',
                body: JSON.stringify({ urls }),
            })
            let data = {}
            try {
                data = await response.json()
            } catch (parseError) {
                console.error('Failed to parse video link response', parseError)
            }
            if (!response.ok || !data.ok) {
                showError(data.error || 'Could not save video links.')
                return false
            }
            setButtonState(activeButton, data.urls || [])
            if (typeof dialog.close === 'function') {
                dialog.close()
            }
            return true
        } catch (error) {
            console.error('Failed to save session video links', error)
            showError('Could not save video links.')
            return false
        }
    }

    form.addEventListener('submit', (event) => {
        const submitter = event.submitter
        if (submitter && submitter.value === 'cancel') {
            return
        }
        event.preventDefault()
        save(rowList.getValues())
    })

    dialog.addEventListener('click', (event) => {
        if (event.target === dialog && typeof dialog.close === 'function') {
            dialog.close()
        }
    })

    submissionVideoController = { openForButton }
    return submissionVideoController
}

const initSubmissionVideoButtons = (root = document) => {
    const controller = getSubmissionVideoDialog()
    if (!controller) return

    root.querySelectorAll('.submission-video-btn:not([data-video-initialized])').forEach((button) => {
        button.setAttribute('data-video-initialized', '')
        button.addEventListener('click', () => {
            controller.openForButton(button)
        })
    })
}

function initSubmissionVideoFormset(root = document) {
    const formset = root.matches?.('[data-session-video-formset]')
        ? root
        : root.querySelector?.('[data-session-video-formset]')
    if (!formset || formset.dataset.sessionVideoReady === 'true') return null
    formset.dataset.sessionVideoReady = 'true'

    const container = formset.querySelector('[data-session-video-rows]')
    const emptyRowTemplate = formset.querySelector('[data-session-video-empty-row]')
    const addButton = formset.querySelector('[data-session-video-add]')
    const clearButton = formset.querySelector('[data-session-video-clear]')
    if (!container || !(emptyRowTemplate instanceof HTMLTemplateElement) || !addButton) return null

    const maxRows = Number.parseInt(formset.dataset.maxRows || '20', 10)

    return createSessionVideoRowList({
        container,
        rowTemplate: emptyRowTemplate,
        addButton,
        clearButton,
        maxRows,
    })
}

const initAll = (root = document) => {
    initSubmissionVideoButtons(root)
    initSubmissionVideoFormset(root)
}

if (typeof onReady === 'function') {
    onReady(() => {
        initAll()
    })
} else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initAll())
} else {
    initAll()
}

document.addEventListener('eventyay:ajax-results-replaced', (event) => {
    initAll(event.detail?.container ?? document)
})

if (typeof window !== 'undefined') {
    window.createSessionVideoRowList = createSessionVideoRowList
    window.initSubmissionVideoFormset = initSubmissionVideoFormset
    window.initSubmissionVideoButtons = initSubmissionVideoButtons
    window.getSubmissionVideoDialog = getSubmissionVideoDialog
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        createSessionVideoRowList,
        initSubmissionVideoFormset,
        initSubmissionVideoButtons,
        getSubmissionVideoDialog,
    }
}

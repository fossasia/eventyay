let submissionVideoController = null

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
    let rowIndex = 0

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

    const collectUrls = () => {
        return Array.from(listEl.querySelectorAll('.submission-video-url-row input'))
            .map((input) => input.value.trim())
            .filter(Boolean)
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

    const addRow = (value = '') => {
        rowIndex += 1
        const row = document.createElement('div')
        row.className = 'submission-video-url-row'
        const inputId = `submission-video-url-input-${rowIndex}`
        const urlLabel = dialog.dataset.urlLabel || 'YouTube or Vimeo URL'
        const removeLabel = dialog.dataset.removeLabel || 'Remove'
        row.innerHTML = `
            <div class="form-group form-group-inline">
                <label for="${inputId}"></label>
                <div class="submission-video-url-controls">
                    <input
                        type="text"
                        class="form-control"
                        id="${inputId}"
                        inputmode="url"
                        placeholder="https://www.youtube.com/watch?v=…"
                        autocomplete="off"
                        autocapitalize="off"
                        spellcheck="false"
                        data-lpignore="true"
                    >
                    <button type="button" class="btn btn-sm btn-outline-danger submission-video-remove">
                        <i class="fa fa-trash" aria-hidden="true"></i>
                    </button>
                </div>
            </div>
        `
        const label = row.querySelector('label')
        label.textContent = urlLabel
        const removeBtn = row.querySelector('.submission-video-remove')
        removeBtn.title = removeLabel
        removeBtn.setAttribute('aria-label', removeLabel)
        const input = row.querySelector('input')
        input.value = value
        removeBtn.addEventListener('click', () => {
            row.remove()
            if (!listEl.querySelector('.submission-video-url-row')) {
                addRow('')
            }
        })
        listEl.appendChild(row)
        return input
    }

    const renderRows = (urls) => {
        listEl.innerHTML = ''
        const values = urls.length ? urls : ['']
        values.forEach((url) => addRow(url))
    }

    const openForButton = (button) => {
        activeButton = button
        saveUrl = button.dataset.url || ''
        if (titleEl) {
            titleEl.textContent = button.dataset.title || ''
        }
        renderRows(parseUrlsFromButton(button))
        showError('')
        if (typeof dialog.showModal === 'function' && !dialog.open) {
            dialog.showModal()
            const firstInput = listEl.querySelector('.submission-video-url-row input')
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
                    'X-CSRFToken': getCookie('eventyay_csrftoken'),
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
        save(collectUrls())
    })

    if (addBtn) {
        addBtn.addEventListener('click', (event) => {
            event.preventDefault()
            const input = addRow('')
            input.focus()
        })
    }

    if (clearBtn) {
        clearBtn.addEventListener('click', (event) => {
            event.preventDefault()
            save([])
        })
    }

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

onReady(() => {
    initSubmissionVideoButtons()
})

document.addEventListener('eventyay:ajax-results-replaced', (event) => {
    initSubmissionVideoButtons(event.detail?.container ?? document)
})

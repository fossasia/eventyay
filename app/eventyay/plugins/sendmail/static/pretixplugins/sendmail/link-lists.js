const container = document.querySelector('[data-link-list]')
const select = document.querySelector('[data-link-list-select]')
const dialog = document.querySelector('#link-list-dialog')

const columnKey = (header, index) => {
    const key = header
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/^_+|_+$/g, '')
    return key || `column_${index + 1}`
}

const headerColumns = (text) => {
    const firstLine = text.split(/\r\n|\n|\r/)[0] || ''
    const delimiter = [';', ',', '\t'].find((candidate) => firstLine.includes(candidate)) || ','
    const keys = []
    firstLine.split(delimiter).forEach((header, index) => {
        let key = columnKey(header.replace(/^"|"$/g, ''), index)
        while (keys.includes(key)) {
            key = `${key}_${index + 1}`
        }
        keys.push(key)
    })
    return keys
}

const editorInputSelector = 'textarea[id^="id_text_"], input[id^="id_subject"]'
let lastFocusedInput = document.querySelector('#id_text_0')
document.querySelectorAll(editorInputSelector).forEach((input) => {
    input.addEventListener('focus', () => {
        lastFocusedInput = input
    })
})

const insertPlaceholder = (name) => {
    if (!lastFocusedInput) {
        return
    }
    const text = `{${name}}`
    const start = lastFocusedInput.selectionStart ?? lastFocusedInput.value.length
    const end = lastFocusedInput.selectionEnd ?? start
    lastFocusedInput.value = lastFocusedInput.value.slice(0, start) + text + lastFocusedInput.value.slice(end)
    lastFocusedInput.selectionStart = start
    lastFocusedInput.selectionEnd = start + text.length
    lastFocusedInput.dispatchEvent(new Event('input', { bubbles: true }))
    lastFocusedInput.focus()
}

const group = document.querySelector('[data-link-list-placeholders]')
const fileList = group?.querySelector('[data-link-list-file-placeholders]')

const showSelectedList = () => {
    const selected = select ? select.value : ''
    const usingFile = Boolean(fileList?.children.length)
    let visible = 0
    group?.querySelectorAll('[data-link-list]').forEach((item) => {
        item.hidden = usingFile || item.dataset.linkList !== selected
        if (!item.hidden) {
            visible += 1
        }
    })
    if (group) {
        group.hidden = visible === 0 && !usingFile
    }
    const manage = container?.querySelector('[data-link-list-manage]')
    if (manage) {
        manage.hidden = !selected
    }
    dialog?.querySelectorAll('[data-link-list-panel]').forEach((panel) => {
        panel.hidden = panel.dataset.linkListPanel !== selected
    })
}

const fileColumnItem = (name) => {
    const item = document.createElement('li')
    item.className = 'list-group-item list-group-item-action placeholder'
    item.dataset.placeholder = name
    const content = document.createElement('div')
    content.className = 'placeholder-content'
    const label = document.createElement('span')
    label.className = 'placeholder-text'
    label.textContent = `{${name}}`
    content.append(label)
    const hint = document.createElement('small')
    hint.className = 'text-muted'
    hint.textContent = group.dataset.fileLabel
    item.append(content, hint)
    item.addEventListener('click', () => insertPlaceholder(name))
    return item
}

const showFileColumns = async (input) => {
    const target = container?.querySelector('[data-link-list-file-columns]')
    const file = input.files?.[0]
    const names = file ? headerColumns(await file.text()).map((column) => `list_${column}`) : []
    fileList?.replaceChildren(...names.map(fileColumnItem))
    if (target) {
        target.textContent = names.length ? `${target.dataset.label} ${names.map((name) => `{${name}}`).join(', ')}` : ''
        target.hidden = !names.length
    }
    showSelectedList()
}

const csrfToken = () => document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || ''

const updateCounts = (panel, counts) => {
    ;['total', 'used', 'left'].forEach((name) => {
        const element = panel.querySelector(`[data-link-list-count="${name}"]`)
        if (element && counts[name] !== undefined) {
            element.textContent = counts[name]
        }
    })
}

const setStatus = (panel, message, failed = false) => {
    const status = panel.querySelector('[data-link-list-status]')
    if (status) {
        status.textContent = message
        status.classList.toggle('text-danger', failed)
    }
}

const fill = (template, values) =>
    Object.entries(values).reduce((text, [key, value]) => text.replace(`{${key}}`, value), template)

const post = async (panel, url, body) => {
    try {
        const response = await fetch(url, {
            method: 'POST',
            body,
            headers: { 'X-CSRFToken': csrfToken() },
            credentials: 'same-origin',
        })
        const data = await response.json()
        if (!response.ok) {
            setStatus(panel, data.error || dialog.dataset.errorLabel, true)
            return null
        }
        updateCounts(panel, data)
        return data
    } catch (error) {
        setStatus(panel, dialog.dataset.errorLabel, true)
        return null
    }
}

dialog?.querySelectorAll('[data-link-list-panel]').forEach((panel) => {
    panel.querySelector('[data-link-list-add-rows]')?.addEventListener('click', async () => {
        const input = panel.querySelector('[data-link-list-rows-file]')
        const file = input?.files?.[0]
        if (!file) {
            setStatus(panel, dialog.dataset.chooseFileLabel, true)
            return
        }
        const body = new FormData()
        body.append('file', file)
        const data = await post(panel, panel.dataset.rowsUrl, body)
        if (data) {
            setStatus(panel, fill(dialog.dataset.addedLabel, data))
            input.value = ''
        }
    })
    panel.querySelector('[data-link-list-delete-unused]')?.addEventListener('click', async (event) => {
        if (!window.confirm(event.currentTarget.dataset.confirm)) {
            return
        }
        const data = await post(panel, panel.dataset.unusedDeleteUrl, new FormData())
        if (data) {
            setStatus(panel, fill(dialog.dataset.deletedLabel, data))
        }
    })
})

dialog?.querySelector('[data-link-list-close]')?.addEventListener('click', () => dialog.close())

select?.addEventListener('change', showSelectedList)
container?.querySelector('[data-link-list-file]')?.addEventListener('change', (event) => showFileColumns(event.target))
showSelectedList()

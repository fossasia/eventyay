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

const savedColumns = JSON.parse(document.querySelector('#link-list-columns')?.textContent || '{}')
let fileColumns = []

const currentPlaceholders = () => {
    if (fileColumns.length) {
        return fileColumns
    }
    return savedColumns[select?.value || ''] || []
}

const menuItem = (editor, dropdown, name) => {
    const item = document.createElement('li')
    item.className = 'tiptap-placeholder-item'
    item.dataset.linkListPlaceholder = name
    item.setAttribute('role', 'option')
    item.tabIndex = 0
    item.textContent = `{${name}}`
    const insert = () => {
        editor.chain().focus().insertPlaceholder(name).run()
        dropdown.hidden = true
    }
    item.addEventListener('click', insert)
    item.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            insert()
        }
    })
    return item
}

const refreshEditorMenus = () => {
    const names = currentPlaceholders()
    document.querySelectorAll('textarea[id^="id_text_"]').forEach((textarea) => {
        const editor = textarea.__eventyayTiptapEditor
        const dropdown = textarea.closest('[data-tiptap-wrapper]')?.querySelector('.tiptap-placeholder-dropdown')
        if (!editor || !dropdown) {
            return
        }
        dropdown.querySelectorAll('[data-link-list-placeholder]').forEach((item) => item.remove())
        names.forEach((name) => dropdown.append(menuItem(editor, dropdown, name)))
    })
}

const showSelectedList = () => {
    const selected = select ? select.value : ''
    const manage = container?.querySelector('[data-link-list-manage]')
    if (manage) {
        manage.hidden = !selected
    }
    dialog?.querySelectorAll('[data-link-list-panel]').forEach((panel) => {
        panel.hidden = panel.dataset.linkListPanel !== selected
    })
    refreshEditorMenus()
}

const showFileColumns = async (input) => {
    const file = input.files?.[0]
    fileColumns = file ? headerColumns(await file.text()).map((column) => `list_${column}`) : []
    refreshEditorMenus()
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
document.addEventListener(
    'click',
    (event) => {
        if (event.target.closest?.('.tiptap-placeholder-menu .tiptap-btn')) {
            refreshEditorMenus()
        }
    },
    true,
)
showSelectedList()

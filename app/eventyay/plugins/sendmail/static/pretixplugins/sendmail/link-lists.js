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

const unquote = (value) => value.trim().replace(/^"|"$/g, '')

const readListFile = (text) => {
    const lines = text.split(/\r\n|\n|\r/).filter((line) => line.trim())
    const firstLine = lines[0] || ''
    const delimiter = [';', ',', '\t'].find((candidate) => firstLine.includes(candidate)) || ','
    const keys = []
    firstLine.split(delimiter).forEach((header, index) => {
        let key = columnKey(unquote(header), index)
        while (keys.includes(key)) {
            key = `${key}_${index + 1}`
        }
        keys.push(key)
    })
    const firstRow = (lines[1] || '').split(delimiter).map(unquote)
    const sample = Object.fromEntries(keys.map((key, index) => [`list_${key}`, firstRow[index] || '']))
    return { names: keys.map((key) => `list_${key}`), sample }
}

const savedColumns = JSON.parse(document.querySelector('#link-list-columns')?.textContent || '{}')
let fileColumns = []
let fileSample = {}

const updatePreviewUrls = () => {
    document.querySelectorAll('[data-email-preview-wrapper]').forEach((wrapper) => {
        if (!wrapper.dataset.basePreviewUrl) {
            wrapper.dataset.basePreviewUrl = wrapper.dataset.emailPreviewUrl || ''
        }
        if (!wrapper.dataset.basePreviewUrl) {
            return
        }
        const url = new URL(wrapper.dataset.basePreviewUrl, window.location.origin)
        if (fileColumns.length) {
            url.searchParams.set('link_list_sample', JSON.stringify(fileSample))
        } else if (select?.value) {
            url.searchParams.set('link_list', select.value)
        }
        wrapper.dataset.emailPreviewUrl = `${url.pathname}${url.search}`
    })
}

const currentPlaceholders = () => {
    if (fileColumns.length) {
        return fileColumns
    }
    return savedColumns[select?.value || ''] || []
}

const menuItem = (editor, close, name) => {
    const item = document.createElement('li')
    item.className = 'tiptap-placeholder-item'
    item.setAttribute('role', 'option')
    item.tabIndex = 0
    item.textContent = `{${name}}`
    const insert = () => {
        editor.chain().focus().insertPlaceholder(name).run()
        close()
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

const buildLinkListMenu = (editor, names) => {
    const menu = document.createElement('span')
    menu.className = 'tiptap-placeholder-menu'
    menu.dataset.linkListMenu = 'true'

    const toggle = document.createElement('button')
    toggle.type = 'button'
    toggle.className = 'tiptap-btn'
    toggle.textContent = container?.dataset.menuLabel || 'Link list'
    toggle.setAttribute('aria-haspopup', 'listbox')
    toggle.setAttribute('aria-expanded', 'false')

    const dropdown = document.createElement('ul')
    dropdown.className = 'tiptap-placeholder-dropdown'
    dropdown.setAttribute('role', 'listbox')
    dropdown.hidden = true

    const close = () => {
        dropdown.hidden = true
        toggle.setAttribute('aria-expanded', 'false')
    }
    names.forEach((name) => dropdown.append(menuItem(editor, close, name)))
    menu.append(toggle, dropdown)

    toggle.addEventListener('click', (event) => {
        event.stopPropagation()
        const open = !dropdown.hidden
        document.querySelectorAll('.tiptap-placeholder-dropdown').forEach((other) => {
            other.hidden = true
        })
        dropdown.hidden = open
        toggle.setAttribute('aria-expanded', String(!open))
    })

    const separator = document.createElement('span')
    separator.className = 'tiptap-separator'
    separator.setAttribute('aria-hidden', 'true')
    separator.dataset.linkListMenu = 'true'
    return [separator, menu]
}

const refreshEditorMenus = () => {
    const names = currentPlaceholders()
    document.querySelectorAll('textarea[id^="id_text_"]').forEach((textarea) => {
        const editor = textarea.__eventyayTiptapEditor
        const toolbar = textarea.closest('[data-tiptap-wrapper]')?.querySelector('.tiptap-toolbar')
        if (!editor || !toolbar) {
            return
        }
        toolbar.querySelectorAll('[data-link-list-menu]').forEach((element) => element.remove())
        if (!names.length) {
            return
        }
        const [separator, menu] = buildLinkListMenu(editor, names)
        const placeholderMenu = toolbar.querySelector('.tiptap-placeholder-menu:not([data-link-list-menu])')
        if (placeholderMenu) {
            placeholderMenu.after(separator, menu)
        } else {
            toolbar.append(separator, menu)
        }
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
    updatePreviewUrls()
}

const showFileColumns = async (input) => {
    const file = input.files?.[0]
    const parsed = file ? readListFile(await file.text()) : { names: [], sample: {} }
    fileColumns = parsed.names
    fileSample = parsed.sample
    refreshEditorMenus()
    updatePreviewUrls()
}

const csrfToken = () => document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || ''

const updateCounts = (panel, counts) => {
    ;['used', 'left'].forEach((name) => {
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
            const label = data.added ? dialog.dataset.addedLabel : dialog.dataset.nothingAddedLabel
            setStatus(panel, fill(label, data))
            input.value = ''
        }
    })
})

dialog?.querySelector('[data-link-list-close]')?.addEventListener('click', () => dialog.close())

select?.addEventListener('change', showSelectedList)
container?.querySelector('[data-link-list-file]')?.addEventListener('change', (event) => showFileColumns(event.target))
window.addEventListener('load', refreshEditorMenus)
document.addEventListener('click', () => {
    document.querySelectorAll('[data-link-list-menu] .tiptap-placeholder-dropdown').forEach((dropdown) => {
        dropdown.hidden = true
        dropdown.previousElementSibling?.setAttribute('aria-expanded', 'false')
    })
})
showSelectedList()

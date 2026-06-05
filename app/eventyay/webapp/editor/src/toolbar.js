/**
 * Builds the toolbar DOM element for a Tiptap editor instance.
 * @param {import('@tiptap/core').Editor} editor
 * @param {object} options
 * @param {string} options.profile - 'richtext' | 'email'
 * @param {string[]} options.placeholders - list of placeholder variable names (email profile only)
 * @param {string} options.previewUrl - URL for email preview endpoint (email profile only)
 * @returns {HTMLElement}
 */
export function buildToolbar(editor, { profile, placeholders = [], previewUrl = '' }) {
  const bar = document.createElement('div')
  bar.className = 'tiptap-toolbar'
  bar.setAttribute('role', 'toolbar')
  bar.setAttribute('aria-label', 'Text formatting')

  const button = (label, title, action, isActiveKey = null) => {
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = 'tiptap-btn'
    btn.title = title
    btn.setAttribute('aria-label', title)
    btn.innerHTML = label
    btn.addEventListener('click', (e) => {
      e.preventDefault()
      action()
      editor.view.focus()
      syncActive()
    })
    if (isActiveKey) {
      btn.dataset.activeKey = isActiveKey
    }
    return btn
  }

  const separator = () => {
    const sep = document.createElement('span')
    sep.className = 'tiptap-separator'
    sep.setAttribute('aria-hidden', 'true')
    return sep
  }

  const boldBtn = button('<b>B</b>', 'Bold', () => editor.chain().focus().toggleBold().run(), 'bold')
  const italicBtn = button('<i>I</i>', 'Italic', () => editor.chain().focus().toggleItalic().run(), 'italic')
  const underlineBtn = button('<u>U</u>', 'Underline', () => editor.chain().focus().toggleUnderline().run(), 'underline')
  const ulBtn = button('&#8226;&#8212;', 'Bullet list', () => editor.chain().focus().toggleBulletList().run(), 'bulletList')
  const olBtn = button('1.&#8212;', 'Numbered list', () => editor.chain().focus().toggleOrderedList().run(), 'orderedList')
  const linkBtn = button('&#128279;', 'Insert link', () => promptLink(editor), 'link')
  const clearBtn = button('&#10005;', 'Clear formatting', () => editor.chain().focus().clearNodes().unsetAllMarks().run())
  const undoBtn = button('&#8630;', 'Undo', () => editor.chain().focus().undo().run())
  const redoBtn = button('&#8631;', 'Redo', () => editor.chain().focus().redo().run())

  bar.append(boldBtn, italicBtn, underlineBtn, separator(), ulBtn, olBtn, separator(), linkBtn, separator(), clearBtn, separator(), undoBtn, redoBtn)

  if (profile === 'email') {
    if (placeholders.length > 0) {
      bar.append(separator(), buildPlaceholderMenu(editor, placeholders))
    }
    if (previewUrl) {
      bar.append(separator(), buildPreviewButton(editor, previewUrl))
    }
  }

  const syncActive = () => {
    bar.querySelectorAll('[data-active-key]').forEach((btn) => {
      const key = btn.dataset.activeKey
      btn.classList.toggle('is-active', editor.isActive(key))
      btn.setAttribute('aria-pressed', String(editor.isActive(key)))
    })
    undoBtn.disabled = !editor.can().undo()
    redoBtn.disabled = !editor.can().redo()
  }

  editor.on('selectionUpdate', syncActive)
  editor.on('transaction', syncActive)

  return bar
}

function promptLink(editor) {
  const existing = editor.getAttributes('link').href || ''
  const url = window.prompt('Enter URL (https://...)', existing)
  if (url === null) return
  if (url === '') {
    editor.chain().focus().extendMarkRange('link').unsetLink().run()
    return
  }
  if (!/^https?:\/\//i.test(url)) {
    window.alert('Only https:// and http:// URLs are allowed.')
    return
  }
  editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run()
}

function buildPlaceholderMenu(editor, placeholders) {
  const wrapper = document.createElement('span')
  wrapper.className = 'tiptap-placeholder-menu'

  const toggle = document.createElement('button')
  toggle.type = 'button'
  toggle.className = 'tiptap-btn'
  toggle.textContent = '{ } Insert placeholder'
  toggle.setAttribute('aria-haspopup', 'listbox')
  toggle.setAttribute('aria-expanded', 'false')

  const dropdown = document.createElement('ul')
  dropdown.className = 'tiptap-placeholder-dropdown'
  dropdown.setAttribute('role', 'listbox')
  dropdown.hidden = true

  placeholders.forEach((variable) => {
    const li = document.createElement('li')
    li.className = 'tiptap-placeholder-item'
    li.setAttribute('role', 'option')
    li.textContent = `{${variable}}`
    li.addEventListener('click', () => {
      editor.chain().focus().insertPlaceholder(variable).run()
      dropdown.hidden = true
      toggle.setAttribute('aria-expanded', 'false')
    })
    dropdown.appendChild(li)
  })

  toggle.addEventListener('click', (e) => {
    e.stopPropagation()
    const open = !dropdown.hidden
    dropdown.hidden = open
    toggle.setAttribute('aria-expanded', String(!open))
  })

  document.addEventListener('click', () => {
    dropdown.hidden = true
    toggle.setAttribute('aria-expanded', 'false')
  })

  wrapper.append(toggle, dropdown)
  return wrapper
}

function buildPreviewButton(editor, previewUrl) {
  const btn = document.createElement('button')
  btn.type = 'button'
  btn.className = 'tiptap-btn tiptap-preview-btn'
  btn.textContent = 'Preview'
  btn.setAttribute('aria-label', 'Preview email')

  btn.addEventListener('click', async (e) => {
    e.preventDefault()
    const html = editor.getHTML()
    try {
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
      const response = await fetch(previewUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ html }),
      })
      if (!response.ok) throw new Error(`Preview request failed: ${response.status}`)
      const data = await response.json()
      showPreviewModal(data.html)
    } catch (err) {
      console.error('Email preview failed:', err)
    }
  })

  return btn
}

function showPreviewModal(html) {
  let modal = document.getElementById('tiptap-preview-modal')
  if (!modal) {
    modal = document.createElement('dialog')
    modal.id = 'tiptap-preview-modal'
    modal.className = 'tiptap-preview-modal'
    modal.innerHTML = `
      <div class="tiptap-preview-modal-inner">
        <button type="button" class="tiptap-preview-close" aria-label="Close preview">&times;</button>
        <h2>Email Preview</h2>
        <div class="tiptap-preview-body"></div>
      </div>
    `
    modal.querySelector('.tiptap-preview-close').addEventListener('click', () => modal.close())
    document.body.appendChild(modal)
  }
  modal.querySelector('.tiptap-preview-body').innerHTML = html
  modal.showModal()
}

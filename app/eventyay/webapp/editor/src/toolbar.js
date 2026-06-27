/**
 * Builds the toolbar DOM element for a Tiptap editor instance.
 * @param {import('@tiptap/core').Editor} editor
 * @param {object} options
 * @param {string} options.profile - 'richtext' | 'email'
 * @param {string[]} options.placeholders - list of placeholder variable names (email profile only)
 * @param {string} options.previewUrl - URL for email preview endpoint (email profile only)
 * @param {string} options.locale - BCP 47 locale for the active editor tab (email profile only)
 * @returns {HTMLElement}
 */
export function buildToolbar(editor, { profile, placeholders = [], previewUrl = '', locale = '' }) {
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
    const doc = new DOMParser().parseFromString(label, 'text/html')
    btn.append(...doc.body.childNodes)
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
  const linkWrapper = document.createElement('span')
  linkWrapper.className = 'tiptap-link-menu'
  const linkBtn = button('&#128279;', 'Insert link', () => showLinkPopover(editor, linkWrapper), 'link')
  linkWrapper.append(linkBtn)
  const clearBtn = button('&#10005;', 'Clear formatting', () => editor.chain().focus().clearNodes().unsetAllMarks().run())
  const undoBtn = button('&#8630;', 'Undo', () => editor.chain().focus().undo().run())
  const redoBtn = button('&#8631;', 'Redo', () => editor.chain().focus().redo().run())

  bar.append(boldBtn, italicBtn, underlineBtn, separator(), ulBtn, olBtn, separator(), linkWrapper, separator(), clearBtn, separator(), undoBtn, redoBtn)

  if (profile === 'email') {
    if (placeholders.length > 0) {
      bar.append(separator(), buildPlaceholderMenu(editor, placeholders))
    }
    if (previewUrl) {
      bar.append(separator(), buildPreviewButton(editor, previewUrl, locale))
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

function showLinkPopover(editor, anchor) {
  document.querySelectorAll('.tiptap-link-popover').forEach((el) => el.remove())

  const wrapper = document.createElement('span')
  wrapper.className = 'tiptap-link-popover'

  const form = document.createElement('form')
  form.className = 'tiptap-link-form'
  form.noValidate = true

  const input = document.createElement('input')
  input.type = 'url'
  input.className = 'tiptap-link-input'
  input.placeholder = 'https://...'
  input.value = editor.getAttributes('link').href || ''
  input.setAttribute('aria-label', 'Link URL')

  const error = document.createElement('div')
  error.className = 'tiptap-link-error'
  error.hidden = true
  error.textContent = 'Only https:// and http:// URLs are allowed.'

  const actions = document.createElement('div')
  actions.className = 'tiptap-link-actions'

  const applyBtn = document.createElement('button')
  applyBtn.type = 'submit'
  applyBtn.className = 'tiptap-btn'
  applyBtn.textContent = 'Apply'

  const removeBtn = document.createElement('button')
  removeBtn.type = 'button'
  removeBtn.className = 'tiptap-btn'
  removeBtn.textContent = 'Remove'

  const close = () => {
    wrapper.remove()
    document.removeEventListener('click', onDocumentClick)
    document.removeEventListener('keydown', onKeydown)
  }

  const applyLink = () => {
    const url = input.value.trim()
    error.hidden = true
    if (!url) {
      editor.chain().focus().extendMarkRange('link').unsetLink().run()
      close()
      return
    }
    if (!/^https?:\/\//i.test(url)) {
      error.hidden = false
      input.focus()
      return
    }
    editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run()
    close()
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault()
    applyLink()
  })

  removeBtn.addEventListener('click', (e) => {
    e.preventDefault()
    editor.chain().focus().extendMarkRange('link').unsetLink().run()
    close()
  })

  const onDocumentClick = (e) => {
    if (!wrapper.contains(e.target) && !anchor.contains(e.target)) {
      close()
    }
  }

  const onKeydown = (e) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      close()
    }
  }

  actions.append(applyBtn, removeBtn)
  form.append(input, error, actions)
  wrapper.append(form)
  anchor.append(wrapper)
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('keydown', onKeydown)
  input.focus()
  input.select()
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
    li.tabIndex = 0
    li.textContent = `{${variable}}`
    const insert = () => {
      editor.chain().focus().insertPlaceholder(variable).run()
      dropdown.hidden = true
      toggle.setAttribute('aria-expanded', 'false')
    }
    li.addEventListener('click', insert)
    li.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        insert()
      }
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

function buildPreviewButton(editor, previewUrl, locale = '') {
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
        body: JSON.stringify({ html, locale: locale || undefined }),
      })
      if (!response.ok) throw new Error(`Preview request failed: ${response.status}`)
      const data = await response.json()
      showPreviewModal(data.html)
    } catch (err) {
      console.error('Email preview failed:', err)
      alert('An error occurred while generating the preview. Please try again.')
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
  const body = modal.querySelector('.tiptap-preview-body')
  const doc = new DOMParser().parseFromString(html, 'text/html')
  body.replaceChildren(...doc.body.childNodes)
  modal.showModal()
}

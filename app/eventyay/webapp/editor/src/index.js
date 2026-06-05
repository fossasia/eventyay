import { Editor } from '@tiptap/core'
import './styles.css'
import { getRichTextExtensions } from './profiles/richtext.js'
import { getEmailExtensions } from './profiles/email.js'
import { buildToolbar } from './toolbar.js'

/**
 * @param {HTMLTextAreaElement} textarea
 * @returns {Editor}
 */
function mountEditor(textarea) {
  const profile = textarea.dataset.tiptapProfile
  const placeholders = parsePlaceholders(textarea.dataset.tiptapPlaceholders)
  const previewUrl = textarea.dataset.tiptapPreviewUrl || ''

  const extensions = profile === 'email' ? getEmailExtensions() : getRichTextExtensions()

  const wrapper = textarea.closest('[data-tiptap-wrapper]')
  if (!wrapper) return null

  const editorEl = document.createElement('div')
  editorEl.className = 'tiptap-editor-content'

  const editor = new Editor({
    element: editorEl,
    extensions,
    content: textarea.value || '',
    editorProps: {
      attributes: {
        class: 'tiptap-prosemirror',
        role: 'textbox',
        'aria-multiline': 'true',
        'aria-label': textarea.getAttribute('aria-label') || textarea.name || 'Rich text editor',
      },
    },
  })

  const toolbar = buildToolbar(editor, { profile, placeholders, previewUrl })

  textarea.style.display = 'none'
  wrapper.insertBefore(toolbar, textarea)
  wrapper.insertBefore(editorEl, textarea)

  const form = textarea.closest('form')
  if (form) {
    form.addEventListener('submit', () => {
      textarea.value = editor.getHTML()
    })
  }

  return editor
}

function parsePlaceholders(raw) {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function init() {
  document.querySelectorAll('textarea[data-tiptap-profile]').forEach((textarea) => {
    mountEditor(textarea)
  })
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init)
} else {
  init()
}

window.eventyayTiptap = { init, mountEditor }

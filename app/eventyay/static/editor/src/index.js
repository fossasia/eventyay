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
  if (textarea.dataset.tiptapMounted) return null
  textarea.dataset.tiptapMounted = 'true'

  const profile = textarea.dataset.tiptapProfile
  const placeholders = parsePlaceholders(textarea.dataset.tiptapPlaceholders)
  const previewUrl = textarea.dataset.tiptapPreviewUrl || ''

  const extensions = profile === 'email' ? getEmailExtensions() : getRichTextExtensions()

  const wrapper = textarea.closest('[data-tiptap-wrapper]')
  if (!wrapper) return null

  const fieldLang = textarea.getAttribute('lang')
  const fieldDir = textarea.getAttribute('dir')

  const editorEl = document.createElement('div')
  editorEl.className = 'tiptap-editor-content'

  const prosemirrorAttrs = {
    class: 'tiptap-prosemirror',
    role: 'textbox',
    'aria-multiline': 'true',
    'aria-label': textarea.getAttribute('aria-label') || textarea.name || 'Rich text editor',
    // Always set dir so LTR locales do not inherit page-level RTL.
    dir: fieldDir || 'ltr',
  }
  if (fieldLang) {
    prosemirrorAttrs.lang = fieldLang
  }

  const editor = new Editor({
    element: editorEl,
    extensions,
    content: textarea.value || '',
    editorProps: {
      attributes: prosemirrorAttrs,
    },
    onUpdate({ editor }) {
      textarea.value = editor.getHTML()
    }
  })

  const toolbar = buildToolbar(editor, { profile, placeholders, previewUrl, locale: fieldLang || '' })

  textarea.style.display = 'none'
  wrapper.insertBefore(toolbar, textarea)
  wrapper.insertBefore(editorEl, textarea)

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

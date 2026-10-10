/**
 * Rich-text submit helpers for required Tiptap fields.
 *
 * - Sync editor HTML into the hidden textarea before submit
 * - Remove native HTML5 `required` (hidden controls block Save with no message)
 * - After a server validation response, scroll to the form error banner
 *
 * Field validation itself is handled by Django (same flow as profile picture).
 */

function syncEditorValue(textarea) {
  const editor = textarea.__eventyayTiptapEditor
  if (editor) {
    textarea.value = editor.getHTML()
  }
}

/**
 * Native required on display:none textareas silently blocks submit.
 * Keep the visual asterisk via Django; enforce emptiness on the server.
 */
function clearNativeRequired(textarea) {
  if (textarea.required || textarea.hasAttribute('required')) {
    textarea.required = false
    textarea.removeAttribute('required')
  }
}

function prepareForm(form) {
  form.querySelectorAll('textarea[data-tiptap-profile]').forEach((textarea) => {
    clearNativeRequired(textarea)
    syncEditorValue(textarea)
  })
}

function navbarOffset() {
  const raw = getComputedStyle(document.documentElement).getPropertyValue('--navbar-height')
  const parsed = Number.parseInt(raw, 10)
  return Number.isFinite(parsed) ? parsed : 56
}

function scrollToFormErrors() {
  const form = document.querySelector('form[data-richtext-form-error], form .alert.alert-danger')?.closest('form')
  if (!form) return

  const alert = form.querySelector('.alert.alert-danger')
  const fieldError =
    form.querySelector('.form-group .invalid-feedback.d-block, .avatar-form .invalid-feedback.d-block, .has-error')
  const target = alert || fieldError
  if (!target) return

  const top = target.getBoundingClientRect().top + window.scrollY - navbarOffset() - 16
  // Use only window.scrollTo so the fixed navbar offset is preserved
  // (scrollIntoView would ignore that offset and tuck the alert under the bar).
  window.scrollTo({ top: Math.max(0, top), behavior: 'auto' })
}

function onSubmit(event) {
  const form = event.target
  if (!(form instanceof HTMLFormElement)) return
  if (!form.querySelector('textarea[data-tiptap-profile]')) return
  // Do not preventDefault — let Save show loading and POST like other fields.
  prepareForm(form)
}

function init() {
  document.querySelectorAll('textarea[data-tiptap-profile]').forEach((textarea) => {
    clearNativeRequired(textarea)
  })
  // After server-side validation (profile picture, biography, …), land on the errors.
  if (document.querySelector('form .alert.alert-danger, form .invalid-feedback.d-block')) {
    requestAnimationFrame(() => {
      requestAnimationFrame(scrollToFormErrors)
    })
  }
}

document.addEventListener('submit', onSubmit, true)

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init)
} else {
  init()
}

window.addEventListener('eventyay:tiptap-ready', () => {
  document.querySelectorAll('textarea[data-tiptap-profile]').forEach(clearNativeRequired)
})

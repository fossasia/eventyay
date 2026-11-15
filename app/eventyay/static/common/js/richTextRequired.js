/**
 * Client-side required check for Tiptap rich-text fields.
 * Empty HTML such as <p></p> or whitespace must not pass when the field is required.
 *
 * Native HTML5 `required` on a display:none textarea is removed: the browser
 * would block submit without showing a message. Validation is handled here and
 * mirrors Django form errors (alert-danger + field invalid-feedback).
 */

const INVISIBLE_CHARS_RE = /[\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff\u00ad]/g
const REQUIRED_SELECTOR = 'textarea[data-tiptap-profile][data-richtext-required="true"]'
const FORM_ERROR_TEXT = 'We had trouble saving your input – Please see below for details.'

function decodeBasicEntities(text) {
  return String(text)
    .replace(/&nbsp;/gi, ' ')
    .replace(/&#160;/g, ' ')
    .replace(/&#x0*a0;/gi, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
}

function isEmptyRichText(html) {
  if (!html) return true
  const text = decodeBasicEntities(String(html).replace(/<[^>]*>/g, ''))
    .replace(INVISIBLE_CHARS_RE, '')
    .replace(/\u00a0/g, ' ')
    .trim()
  return !text
}

function fieldAnchor(textarea) {
  return (
    textarea.closest('.form-group') ||
    textarea.closest('[data-tiptap-wrapper]') ||
    textarea
  )
}

function navbarOffset() {
  const raw = getComputedStyle(document.documentElement).getPropertyValue('--navbar-height')
  const parsed = Number.parseInt(raw, 10)
  return Number.isFinite(parsed) ? parsed : 56
}

function ensureFormAlert(form) {
  let alert = form.querySelector('[data-richtext-form-error-alert]')
  if (alert) return alert

  const existing = form.querySelector('.alert.alert-danger[role="alert"]')
  if (existing) {
    existing.setAttribute('data-richtext-form-error-alert', 'true')
    return existing
  }

  alert = document.createElement('div')
  alert.className = 'alert alert-danger'
  alert.setAttribute('role', 'alert')
  alert.setAttribute('data-richtext-form-error-alert', 'true')

  const inner = document.createElement('div')
  inner.textContent =
    form.dataset.richtextFormError ||
    form.getAttribute('data-richtext-form-error') ||
    FORM_ERROR_TEXT
  alert.appendChild(inner)

  const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]')
  if (csrf?.nextSibling) {
    csrf.parentNode.insertBefore(alert, csrf.nextSibling)
  } else {
    form.prepend(alert)
  }
  return alert
}

function clearFormAlert(form) {
  form.querySelector('[data-richtext-form-error-alert]')?.remove()
}

function ensureErrorElement(anchor, message, textarea) {
  let error = anchor.querySelector('[data-richtext-required-error]')
  const errorId = textarea.id ? `${textarea.id}-error` : 'richtext-required-error'
  if (!error) {
    error = document.createElement('div')
    error.className = 'invalid-feedback d-block'
    error.setAttribute('data-richtext-required-error', 'true')
    error.setAttribute('role', 'alert')
    error.id = errorId
    const wrapper = anchor.querySelector('[data-tiptap-wrapper]')
    if (wrapper) {
      wrapper.insertAdjacentElement('afterend', error)
    } else {
      anchor.appendChild(error)
    }
  }
  error.textContent = message

  const prosemirror = anchor.querySelector('.tiptap-prosemirror, [contenteditable="true"]')
  if (prosemirror) {
    prosemirror.setAttribute('aria-invalid', 'true')
    prosemirror.setAttribute('aria-describedby', errorId)
  }
  return error
}

function clearError(anchor) {
  anchor?.querySelector?.('[data-richtext-required-error]')?.remove()
  anchor?.classList?.remove('is-invalid', 'has-error')
  const wrapper = anchor?.querySelector?.('[data-tiptap-wrapper]')
  wrapper?.classList?.remove('is-invalid')

  const prosemirror = anchor?.querySelector?.('.tiptap-prosemirror, [contenteditable="true"]')
  if (prosemirror) {
    prosemirror.removeAttribute('aria-invalid')
    prosemirror.removeAttribute('aria-describedby')
  }
}

function revealInvalidField(textarea, form) {
  const editor = textarea.__eventyayTiptapEditor
  const anchor = fieldAnchor(textarea)
  const alert = form.querySelector('[data-richtext-form-error-alert]')
  const target = alert || anchor
  target.style.scrollMarginTop = `${navbarOffset() + 16}px`

  const jump = () => {
    const top = target.getBoundingClientRect().top + window.scrollY - navbarOffset() - 16
    window.scrollTo({ top: Math.max(0, top), behavior: 'auto' })
    if (editor?.commands?.focus) {
      editor.commands.focus('end')
    }
  }

  requestAnimationFrame(() => {
    requestAnimationFrame(jump)
  })
}

function isMarkedRequired(textarea) {
  return (
    textarea.dataset.richtextRequired === 'true' ||
    Boolean(textarea.closest('.form-group.required, .form-group--required'))
  )
}

/**
 * Move native required onto a data attribute so the hidden textarea cannot
 * silently block form submit via HTML5 constraint validation.
 */
function adoptNativeRequired(textarea) {
  if (
    textarea.required ||
    textarea.hasAttribute('required') ||
    Boolean(textarea.closest('.form-group.required, .form-group--required'))
  ) {
    textarea.dataset.richtextRequired = 'true'
    if (!textarea.dataset.requiredMessage && !textarea.getAttribute('data-required-message')) {
      textarea.dataset.requiredMessage = 'This field is required.'
    }
    textarea.required = false
    textarea.removeAttribute('required')
  }
}

function syncEditorValue(textarea) {
  const editor = textarea.__eventyayTiptapEditor
  if (editor) {
    textarea.value = editor.getHTML()
  }
}

function syncAndValidateTextarea(textarea) {
  syncEditorValue(textarea)
  const anchor = fieldAnchor(textarea)
  const wrapper = textarea.closest('[data-tiptap-wrapper]')
  if (!isMarkedRequired(textarea)) {
    clearError(anchor)
    textarea.setCustomValidity('')
    return true
  }
  const message =
    textarea.dataset.requiredMessage ||
    textarea.getAttribute('data-required-message') ||
    'This field is required.'
  if (isEmptyRichText(textarea.value)) {
    textarea.setCustomValidity(message)
    anchor.classList.add('is-invalid', 'has-error')
    wrapper?.classList?.add('is-invalid')
    ensureErrorElement(anchor, message, textarea)
    return false
  }
  textarea.setCustomValidity('')
  clearError(anchor)
  return true
}

function bindLiveValidation(textarea) {
  adoptNativeRequired(textarea)
  if (!isMarkedRequired(textarea)) return

  const revalidate = () => {
    syncAndValidateTextarea(textarea)
    const form = textarea.closest('form')
    if (!form) return
    const stillInvalid = Array.from(form.querySelectorAll(REQUIRED_SELECTOR)).some(
      (el) => isMarkedRequired(el) && isEmptyRichText(el.__eventyayTiptapEditor ? el.__eventyayTiptapEditor.getHTML() : el.value)
    )
    if (!stillInvalid) {
      clearFormAlert(form)
    }
  }

  if (!textarea.dataset.richtextRequiredBound) {
    textarea.dataset.richtextRequiredBound = 'true'
    textarea.addEventListener('input', revalidate)
  }

  const editor = textarea.__eventyayTiptapEditor
  if (editor?.on && !textarea.dataset.richtextEditorBound) {
    textarea.dataset.richtextEditorBound = 'true'
    editor.on('update', revalidate)
  }
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
  window.scrollTo({ top: Math.max(0, top), behavior: 'auto' })
}

function onSubmit(event) {
  const form = event.target
  if (!(form instanceof HTMLFormElement)) return

  form.querySelectorAll('textarea[data-tiptap-profile]').forEach(adoptNativeRequired)

  const textareas = form.querySelectorAll(REQUIRED_SELECTOR)
  if (!textareas.length) return

  let firstInvalid = null
  textareas.forEach((textarea) => {
    bindLiveValidation(textarea)
    if (!syncAndValidateTextarea(textarea) && !firstInvalid) {
      firstInvalid = textarea
    }
  })

  if (firstInvalid) {
    event.preventDefault()
    event.stopPropagation()
    ensureFormAlert(form)
    revealInvalidField(firstInvalid, form)
  } else {
    clearFormAlert(form)
  }
}

function init() {
  document.querySelectorAll('textarea[data-tiptap-profile]').forEach((textarea) => {
    bindLiveValidation(textarea)
  })
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

window.addEventListener('eventyay:tiptap-ready', init)

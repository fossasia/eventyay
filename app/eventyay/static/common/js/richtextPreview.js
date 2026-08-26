function getCsrfToken(container) {
  const input = (container || document).querySelector('input[name="csrfmiddlewaretoken"]')
  return input ? input.value : ''
}

function showPreviewError(target) {
  target.textContent = typeof window.gettext === 'function' ? window.gettext('Preview could not be loaded.') : 'Preview could not be loaded.'
}

function replaceHtml(target, html) {
  const parsed = new DOMParser().parseFromString(html || '', 'text/html')
  target.replaceChildren(...parsed.body.childNodes)
}

function initRichTextPreviewTabs() {
  document.querySelectorAll('[data-richtext-preview-tab]').forEach((tab) => {
    const wrapper = tab.closest('[data-richtext-preview-wrapper]')
    if (!wrapper) return

    const previewUrl = wrapper.getAttribute('data-richtext-preview-url')
    const previewEl = wrapper.querySelector('.richtext-preview')
    if (!previewUrl || !previewEl) return

    const form = wrapper.closest('form')

    tab.addEventListener('click', async () => {
      const textarea = wrapper.querySelector('textarea[data-tiptap-profile], textarea')
      if (!textarea) return

      const params = new URLSearchParams()
      params.append('content', textarea.value)

      try {
        const response = await fetch(previewUrl, {
          method: 'POST',
          headers: {
            'X-CSRFToken': getCsrfToken(form),
            'Content-Type': 'application/x-www-form-urlencoded',
          },
          credentials: 'same-origin',
          body: params,
        })
        if (!response.ok) throw new Error(`Preview request failed: ${response.status}`)
        const data = await response.json()
        replaceHtml(previewEl, data.html)
      } catch (err) {
        console.error('Rich text preview failed:', err)
        showPreviewError(previewEl)
      }
    })
  })
}

function initEmailPreviewTabs() {
  document.querySelectorAll('[data-email-preview-tab]').forEach((tab) => {
    const wrapper = tab.closest('[data-email-preview-wrapper]')
    if (!wrapper) return

    const previewUrl = wrapper.getAttribute('data-email-preview-url')
    const blocks = wrapper.querySelectorAll('.mail-preview')
    if (!previewUrl || !blocks.length) return

    const form = wrapper.closest('form')

    tab.addEventListener('click', async () => {
      const params = new URLSearchParams()
      const textareas = wrapper.querySelectorAll('textarea')
      textareas.forEach((textarea) => {
        const lang = textarea.getAttribute('lang')
        params.append(lang ? `body_${lang}` : 'body', textarea.value)
      })

      try {
        const response = await fetch(previewUrl, {
          method: 'POST',
          headers: {
            'X-CSRFToken': getCsrfToken(form),
            'Content-Type': 'application/x-www-form-urlencoded',
          },
          credentials: 'same-origin',
          body: params,
        })
        if (!response.ok) throw new Error(`Preview request failed: ${response.status}`)
        const data = await response.json()
        const previews = data.previews || {}
        blocks.forEach((block) => {
          replaceHtml(block, previews[block.getAttribute('lang')])
        })
      } catch (err) {
        console.error('Email preview failed:', err)
        blocks.forEach((block) => showPreviewError(block))
      }
    })
  })
}

function init() {
  initRichTextPreviewTabs()
  initEmailPreviewTabs()
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true })
} else {
  init()
}

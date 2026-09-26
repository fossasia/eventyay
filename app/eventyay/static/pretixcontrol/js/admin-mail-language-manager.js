const LANGUAGE_INPUT_SELECTOR = 'input[lang], textarea[lang]'
let DEFAULT_LOCALE = 'en'

const getAllLocales = () => {
  const locales = []
  const seen = new Set()
  document.querySelectorAll(LANGUAGE_INPUT_SELECTOR).forEach((input) => {
    if (!seen.has(input.lang)) {
      seen.add(input.lang)
      locales.push({ code: input.lang, label: input.title || input.lang })
    }
  })
  return locales
}

const getLocalesWithContent = () => {
  const locales = new Set()
  document.querySelectorAll(LANGUAGE_INPUT_SELECTOR).forEach((input) => {
    const val = input.value || ''
    if (val.trim()) locales.add(input.lang)
  })
  document.querySelectorAll('.tiptap-prosemirror[lang]').forEach((el) => {
    const text = (el.textContent || '').trim()
    if (text) locales.add(el.getAttribute('lang'))
  })
  return locales
}

const toggleLocaleField = (input, hidden) => {
  input.classList.toggle('d-none', hidden)
  const wrapper = input.closest('.tiptap-wrapper')
  if (wrapper) wrapper.classList.toggle('d-none', hidden)
}

const showLocale = (code, tabs) => {
  document.querySelectorAll(LANGUAGE_INPUT_SELECTOR).forEach((input) => {
    toggleLocaleField(input, input.lang !== code)
  })
  tabs.forEach((tab) => {
    const active = tab.dataset.locale === code
    tab.classList.toggle('active', active)
    tab.setAttribute('aria-selected', active ? 'true' : 'false')
  })
  document.dispatchEvent(new CustomEvent('mail-language-change', { detail: { locale: code } }))
}

const buildTab = (locale, container, tabs, activeLocales, rebuildFn) => {
  const tab = document.createElement('button')
  tab.type = 'button'
  tab.className = 'mail-language-tab'
  tab.dataset.locale = locale.code
  tab.setAttribute('role', 'tab')
  tab.textContent = locale.label

  if (locale.code !== DEFAULT_LOCALE) {
    const removeBtn = document.createElement('span')
    removeBtn.className = 'ml-1'
    removeBtn.textContent = '\u00d7'
    removeBtn.style.cursor = 'pointer'
    removeBtn.style.fontSize = '0.75rem'
    removeBtn.setAttribute('aria-label', 'Remove ' + locale.label)
    tab.appendChild(removeBtn)

    removeBtn.addEventListener('click', (e) => {
      e.stopPropagation()
      document.querySelectorAll(LANGUAGE_INPUT_SELECTOR).forEach((input) => {
        if (input.lang === locale.code) {
          if (input.__eventyayTiptapEditor) {
            input.__eventyayTiptapEditor.commands.setContent('', { emitUpdate: false })
          }
          input.value = ''
          toggleLocaleField(input, true)
        }
      })
      activeLocales.delete(locale.code)
      const idx = tabs.indexOf(tab)
      tabs.splice(idx, 1)
      tab.remove()
      rebuildFn()
      if (tab.classList.contains('active') && tabs.length) {
        showLocale(tabs[0].dataset.locale, tabs)
      }
    })
  }

  tab.addEventListener('click', (e) => {
    if (e.target.tagName === 'SPAN') return
    showLocale(locale.code, tabs)
  })

  container.appendChild(tab)
  tabs.push(tab)
}

const init = () => {
  const container = document.querySelector('#mail-language-tabs')
  const addBtn = document.querySelector('#add-language-btn')
  const dropdown = document.querySelector('#add-language-dropdown')
  if (!container || !addBtn || !dropdown) return

  const allLocales = getAllLocales()
  if (allLocales.length < 2) return

  const configuredDefault = container.dataset.defaultLocale
  DEFAULT_LOCALE = allLocales.some((l) => l.code === configuredDefault)
    ? configuredDefault
    : allLocales[0].code

  const tabs = []
  const activeLocales = new Set([DEFAULT_LOCALE])

  const prefilled = getLocalesWithContent()
  prefilled.forEach((code) => activeLocales.add(code))

  const rebuildDropdown = () => {
    dropdown.innerHTML = ''
    allLocales
      .filter((l) => !activeLocales.has(l.code))
      .forEach((locale) => {
        const li = document.createElement('li')
        const a = document.createElement('a')
        a.href = '#'
        a.textContent = locale.label
        a.addEventListener('click', (e) => {
          e.preventDefault()
          activeLocales.add(locale.code)
          buildTab(locale, container, tabs, activeLocales, rebuildDropdown)
          showLocale(locale.code, tabs)
          rebuildDropdown()
        })
        li.appendChild(a)
        dropdown.appendChild(li)
      })
    addBtn.hidden = dropdown.children.length === 0
  }

  const sortedActive = [DEFAULT_LOCALE, ...[...activeLocales].filter((c) => c !== DEFAULT_LOCALE).sort()]
  sortedActive.forEach((code) => {
    const locale = allLocales.find((l) => l.code === code)
    if (locale) buildTab(locale, container, tabs, activeLocales, rebuildDropdown)
  })

  container.setAttribute('role', 'tablist')
  container.hidden = false

  document.querySelectorAll(LANGUAGE_INPUT_SELECTOR).forEach((input) => {
    toggleLocaleField(input, input.lang !== DEFAULT_LOCALE)
  })

  rebuildDropdown()
  showLocale(DEFAULT_LOCALE, tabs)
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init)
} else {
  init()
}

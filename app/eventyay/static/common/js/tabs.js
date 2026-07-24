const TAB_SELECTOR = 'input[role=tab][name=tablist]'
const ERROR_SELECTOR = '.invalid-feedback, .is-invalid, [aria-invalid="true"], .has-error, .alert-danger'

const getPanelForTab = (tab) => {
  const panelId = tab.getAttribute('aria-controls')
  if (!panelId) return null
  return document.getElementById(panelId)
}

const updateTabPanels = () => {
  const selectedTab = document.querySelector(`${TAB_SELECTOR}:checked`)
  if (!selectedTab) return
  const selectedPanel = getPanelForTab(selectedTab)
  if (!selectedPanel) return
  selectedTab.parentElement.querySelectorAll('[role=tab][aria-selected=true]').forEach((element) => {
    element.setAttribute('aria-selected', 'false')
  })
  selectedPanel.parentElement.querySelectorAll(':scope > [role=tabpanel]').forEach((element) => {
    element.setAttribute('aria-hidden', 'true')
  })
  selectedTab.setAttribute('aria-selected', 'true')
  selectedPanel.setAttribute('aria-hidden', 'false')
  window.location.hash = selectedTab.id
}

const getTabFromHash = () => {
  const fragment = window.location.hash.substring(1)
  if (fragment) {
    return document.querySelector(`${TAB_SELECTOR}#${CSS.escape(fragment)}`)
  }
}

/**
 * Prefer the first tab whose panel contains server-side or client-side validation errors.
 * Matches Tickets/Orders mail editor behavior (pretixcontrol/js/ui/tabs.js).
 */
const getTabWithErrors = () => {
  for (const tab of document.querySelectorAll(TAB_SELECTOR)) {
    const tablist = tab.closest('[role="tablist"]')
    if (!tablist || tablist.dataset.tabErrorSync !== 'true') continue

    const panel = getPanelForTab(tab)
    if (panel && panel.querySelector(ERROR_SELECTOR)) {
      return tab
    }
  }
  return null
}

const focusFirstErrorInPanel = (panel) => {
  if (!panel) return
  const control =
    panel.querySelector('.is-invalid, [aria-invalid="true"]') ||
    panel.querySelector('.invalid-feedback')?.closest('.form-group')?.querySelector('input, select, textarea')
  if (!control || typeof control.focus !== 'function') return
  control.focus()
  if (typeof control.scrollIntoView === 'function') {
    control.scrollIntoView({ block: 'center' })
  }
}

const setupInvalidHandlers = () => {
  let handledSubmitInvalid = false
  const firstTab = document.querySelector(TAB_SELECTOR)
  const form = firstTab?.closest('form')
  if (form) {
    form.addEventListener('submit', () => {
      handledSubmitInvalid = false
    })
  }

  document.querySelectorAll(TAB_SELECTOR).forEach((tab) => {
    const tablist = tab.closest('[role="tablist"]')
    if (!tablist || tablist.dataset.tabErrorSync !== 'true') return

    const panel = getPanelForTab(tab)
    if (!panel) return
    panel.querySelectorAll('input, select, textarea').forEach((control) => {
      if (control.matches(TAB_SELECTOR)) return
      control.addEventListener('invalid', () => {
        if (!tab.checked) {
          tab.checked = true
          updateTabPanels()
        }
        if (!handledSubmitInvalid) {
          handledSubmitInvalid = true
          control.focus()
        }
      })
    })
  })
}

const initTabs = () => {
  // Prefer a tab with validation errors so required fields on other tabs are visible.
  // Then fall back to hash, the last selected tab, and finally the first tab.
  let selectedTab = getTabWithErrors()
  const selectedForErrors = Boolean(selectedTab)
  if (!selectedTab) {
    selectedTab = getTabFromHash()
  }
  if (!selectedTab) {
    selectedTab = document.querySelector(`${TAB_SELECTOR}:checked`)
  }
  if (!selectedTab) {
    selectedTab = document.querySelector(TAB_SELECTOR)
  }
  if (!selectedTab) return

  selectedTab.checked = true
  updateTabPanels()
  if (selectedForErrors) {
    focusFirstErrorInPanel(getPanelForTab(selectedTab))
  }

  document.querySelectorAll(TAB_SELECTOR).forEach((element) => {
    element.addEventListener('change', updateTabPanels)
  })
  setupInvalidHandlers()

  // If the URL fragment changes, e.g. by navigating backwards, update the tab
  window.addEventListener('hashchange', () => {
    selectedTab = getTabFromHash()
    if (selectedTab) {
      selectedTab.checked = true
      updateTabPanels()
    }
  })
}

if (document.querySelector(TAB_SELECTOR)) {
  initTabs()
}

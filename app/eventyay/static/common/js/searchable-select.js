/**
 * Enhances a native <select data-searchable-select> with a filterable list.
 * The original select stays in the form so the submitted value is unchanged.
 */

const READY_FLAG = 'searchableSelectReady'

const normalize = function(value) {
  return String(value || '')
    .toLocaleLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}

const escapeSelectorId = function(value) {
  if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') {
    return CSS.escape(value)
  }
  return String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"')
}

const isDisabledItem = function(item) {
  return item.getAttribute('aria-disabled') === 'true'
}

const optionIsDisabled = function(option) {
  const group = option.parentElement
  return option.disabled || Boolean(group && group.tagName === 'OPTGROUP' && group.disabled)
}

const initSearchableSelect = function(select) {
  if (select.dataset[READY_FLAG] === '1' || select.multiple) {
    return
  }

  const searchPlaceholder = select.dataset.searchPlaceholder || 'Search'
  const emptyText = select.dataset.emptyText || 'No matches'
  const allLabel = select.dataset.allLabel || ''
  const listId = (select.id || select.name || 'searchable-select') + '-listbox'
  const parent = select.parentNode
  const nextSibling = select.nextSibling
  let root = null
  let observer = null

  try {
  root = document.createElement('div')
  root.className = 'searchable-select is-enhanced'
  parent.insertBefore(root, select)
  root.appendChild(select)

  const toggle = document.createElement('button')
  toggle.type = 'button'
  toggle.className = 'searchable-select__toggle'
  toggle.setAttribute('aria-haspopup', 'listbox')
  toggle.setAttribute('aria-expanded', 'false')
  toggle.setAttribute('aria-controls', listId)
  const value = document.createElement('span')
  value.className = 'searchable-select__value'
  value.id = listId + '-value'
  if (select.id) {
    const label = document.querySelector(`label[for="${escapeSelectorId(select.id)}"]`)
    if (label) {
      if (!label.id) {
        label.id = select.id + '-label'
      }
      toggle.setAttribute('aria-labelledby', label.id + ' ' + value.id)
    }
  }
  const caret = document.createElement('span')
  caret.className = 'searchable-select__caret'
  caret.setAttribute('aria-hidden', 'true')
  toggle.append(value, caret)

  const panel = document.createElement('div')
  panel.className = 'searchable-select__panel'
  panel.hidden = true

  const search = document.createElement('input')
  search.type = 'search'
  search.className = 'searchable-select__search'
  search.placeholder = searchPlaceholder
  search.setAttribute('aria-label', searchPlaceholder)
  search.setAttribute('aria-controls', listId)
  search.setAttribute('aria-autocomplete', 'list')
  search.autocomplete = 'off'

  const list = document.createElement('ul')
  list.className = 'searchable-select__list'
  list.id = listId
  list.setAttribute('role', 'listbox')

  const empty = document.createElement('p')
  empty.className = 'searchable-select__empty'
  empty.hidden = true
  empty.textContent = emptyText

  panel.append(search, list, empty)
  root.append(toggle, panel)

  let activeIndex = -1

  const options = function() {
    return Array.from(list.querySelectorAll('[role="option"]'))
  }

  const visibleOptions = function() {
    return options().filter(function(option) {
      return !option.hidden && !isDisabledItem(option)
    })
  }

  const syncLabel = function() {
    const selected = select.options[select.selectedIndex]
    value.textContent = selected ? selected.text : ''
    options().forEach(function(option) {
      const isSelected = option.dataset.value === select.value
      option.classList.toggle('is-selected', isSelected)
      option.setAttribute('aria-selected', isSelected ? 'true' : 'false')
    })
  }

  const setActive = function(index) {
    const items = visibleOptions()
    items.forEach(function(option) {
      option.classList.remove('is-active')
    })
    if (!items.length) {
      activeIndex = -1
      search.removeAttribute('aria-activedescendant')
      return
    }
    activeIndex = (index + items.length) % items.length
    const active = items[activeIndex]
    active.classList.add('is-active')
    search.setAttribute('aria-activedescendant', active.id)
    const top = active.offsetTop
    const bottom = top + active.offsetHeight
    if (top < list.scrollTop) {
      list.scrollTop = top
    } else if (bottom > list.scrollTop + list.clientHeight) {
      list.scrollTop = bottom - list.clientHeight
    }
  }

  const rebuild = function() {
    toggle.disabled = select.disabled
    if (select.disabled) {
      close(false)
    }
    list.replaceChildren()
    Array.from(select.options).forEach(function(option, index) {
      const item = document.createElement('li')
      item.id = listId + '-option-' + index
      item.className = 'searchable-select__option'
      item.setAttribute('role', 'option')
      item.dataset.value = option.value
      item.textContent = allLabel && option.value === '' ? allLabel : option.text
      if (optionIsDisabled(option)) {
        item.setAttribute('aria-disabled', 'true')
      }
      item.addEventListener('mousedown', function(event) {
        event.preventDefault()
      })
      item.addEventListener('click', function() {
        if (optionIsDisabled(option)) {
          return
        }
        choose(option.value)
      })
      list.appendChild(item)
    })
    applyFilter()
    syncLabel()
  }

  const applyFilter = function() {
    const query = normalize(search.value.trim())
    let choiceMatches = 0
    options().forEach(function(option) {
      const isAll = allLabel && option.dataset.value === ''
      const matchesQuery = !query || normalize(option.textContent).includes(query)
      option.hidden = !(isAll || matchesQuery)
      if (!isAll && query && matchesQuery && !isDisabledItem(option)) {
        choiceMatches += 1
      }
    })
    empty.hidden = !query || choiceMatches > 0
    setActive(0)
  }

  const open = function() {
    toggle.disabled = select.disabled
    if (!panel.hidden || select.disabled) {
      return
    }
    panel.hidden = false
    root.classList.add('is-open')
    toggle.setAttribute('aria-expanded', 'true')
    search.value = ''
    applyFilter()
    const selected = visibleOptions().findIndex(function(option) {
      return option.dataset.value === select.value
    })
    setActive(selected >= 0 ? selected : 0)
    search.focus()
  }

  const close = function(restoreFocus) {
    if (panel.hidden) {
      return
    }
    panel.hidden = true
    root.classList.remove('is-open')
    toggle.setAttribute('aria-expanded', 'false')
    search.removeAttribute('aria-activedescendant')
    if (restoreFocus) {
      toggle.focus()
    }
  }

  const choose = function(nextValue) {
    if (select.value !== nextValue) {
      select.value = nextValue
      select.dispatchEvent(new Event('change', { bubbles: true }))
    }
    syncLabel()
    close(true)
  }

  toggle.addEventListener('click', function() {
    toggle.disabled = select.disabled
    if (select.disabled) {
      close(false)
      return
    }
    if (panel.hidden) {
      open()
    } else {
      close(false)
    }
  })

  search.addEventListener('input', applyFilter)
  search.addEventListener('keydown', function(event) {
    const items = visibleOptions()
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActive(activeIndex + 1)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive(activeIndex - 1)
    } else if (event.key === 'Home') {
      event.preventDefault()
      setActive(0)
    } else if (event.key === 'End') {
      event.preventDefault()
      setActive(items.length - 1)
    } else if (event.key === 'Enter') {
      event.preventDefault()
      const active = items[activeIndex]
      if (active) {
        choose(active.dataset.value)
      }
    } else if (event.key === 'Escape') {
      event.preventDefault()
      close(true)
    }
  })

  root.addEventListener('focusout', function(event) {
    if (!root.contains(event.relatedTarget)) {
      close(false)
    }
  })

  document.addEventListener('pointerdown', function(event) {
    if (!root.contains(event.target)) {
      close(false)
    }
  })

  if (typeof MutationObserver !== 'undefined') {
    observer = new MutationObserver(function(mutations) {
      let shouldRebuild = false
      let shouldSyncDisabled = false
      for (const mutation of mutations) {
        if (mutation.type === 'childList') {
          shouldRebuild = true
        } else if (mutation.type === 'attributes') {
          if (mutation.target === select && mutation.attributeName === 'disabled') {
            shouldSyncDisabled = true
          } else if (
            mutation.target.tagName === 'OPTION' ||
            mutation.target.tagName === 'OPTGROUP'
          ) {
            shouldRebuild = true
          }
        }
      }
      if (shouldSyncDisabled) {
        toggle.disabled = select.disabled
        if (select.disabled) {
          close(false)
        }
      }
      if (shouldRebuild) {
        rebuild()
      }
    })
    observer.observe(select, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['disabled', 'value', 'selected', 'label'],
    })
  }

  select.rebuildSearchableSelect = rebuild
  select.addEventListener('eventyay:rebuild', rebuild)
  select.addEventListener('change', syncLabel)
  rebuild()
  toggle.disabled = select.disabled
  select.classList.add('searchable-select__native')
  select.tabIndex = -1
  select.setAttribute('aria-hidden', 'true')
  select.dataset[READY_FLAG] = '1'
  } catch (error) {
    if (observer) {
      observer.disconnect()
    }
    delete select.rebuildSearchableSelect
    console.error('searchable-select: failed to enhance select', select, error)
    if (root && root.parentNode) {
      parent.insertBefore(select, root)
      root.remove()
    } else if (select.parentNode !== parent) {
      parent.insertBefore(select, nextSibling)
    }
    select.classList.remove('searchable-select__native')
    select.removeAttribute('aria-hidden')
    if (select.tabIndex === -1) {
      select.tabIndex = 0
    }
    delete select.dataset[READY_FLAG]
  }
}

const initSearchableSelects = function(root) {
  const scope = root && root.querySelectorAll ? root : (typeof document !== 'undefined' ? document : null)
  if (!scope) {
    return
  }
  scope.querySelectorAll('select[data-searchable-select]').forEach(initSearchableSelect)
}

if (typeof window !== 'undefined') {
  window.eventyayInitSearchableSelects = initSearchableSelects
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      initSearchableSelects(document)
    })
  } else {
    initSearchableSelects(document)
  }

  document.addEventListener('eventyay:ajax-results-replaced', function(event) {
    initSearchableSelects(event.detail && event.detail.container ? event.detail.container : document)
  })
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    initSearchableSelect,
    initSearchableSelects,
    normalize,
    escapeSelectorId,
  }
}

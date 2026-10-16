/**
 * Unit and interaction test suite for searchable-select.js.
 * Run with: node --test app/eventyay/static/common/js/searchable-select.test.js
 */
const test = require('node:test')
const assert = require('node:assert/strict')

// Lightweight DOM mock tailored for searchable-select.js
function createDOMEnvironment() {
  const documentListeners = {}

  class MockClassList {
    constructor(element) {
      this.element = element
      this._classes = new Set()
      this._sync()
    }
    _sync() {
      this._classes.clear()
      if (this.element._className) {
        this.element._className.split(/\s+/).filter(Boolean).forEach(c => this._classes.add(c))
      }
    }
    _flush() {
      this.element._className = Array.from(this._classes).join(' ')
    }
    add(...classes) {
      classes.forEach(c => this._classes.add(c))
      this._flush()
    }
    remove(...classes) {
      classes.forEach(c => this._classes.delete(c))
      this._flush()
    }
    toggle(cls, force) {
      if (typeof force === 'boolean') {
        if (force) this._classes.add(cls)
        else this._classes.delete(cls)
      } else {
        if (this._classes.has(cls)) this._classes.delete(cls)
        else this._classes.add(cls)
      }
      this._flush()
      return this._classes.has(cls)
    }
    contains(cls) {
      return this._classes.has(cls)
    }
  }

  class MockElement {
    constructor(tagName) {
      this.tagName = tagName.toUpperCase()
      this.parentNode = null
      this.childNodes = []
      this.children = []
      this.attributes = {}
      this._className = ''
      this.classList = new MockClassList(this)
      this.dataset = {}
      this.listeners = {}
      this._observers = []
      this.hidden = false
      this._value = ''
      this._text = ''
      this._id = ''
      this.disabled = false
      this.tabIndex = 0
      this.multiple = false
      this.type = ''
      this.placeholder = ''
      this.autocomplete = ''
      this.scrollTop = 0
      this.clientHeight = 200
      this.offsetTop = 0
      this.offsetHeight = 30
    }

    get id() { return this._id }
    set id(val) {
      this._id = val
      this.attributes['id'] = val
    }

    get className() { return this._className }
    set className(val) {
      this._className = val
      this.classList._sync()
    }

    get textContent() {
      if (this.childNodes.length > 0) {
        return this.childNodes.map(c => typeof c === 'string' ? c : c.textContent).join('')
      }
      return this._text
    }
    set textContent(val) {
      this._text = String(val)
      this.childNodes = [this._text]
      this.children = []
      this._notifyMutation({ type: 'childList' })
    }

    get text() { return this.textContent }
    set text(val) { this.textContent = val }

    get value() {
      if (this.tagName === 'SELECT') {
        const selected = this.options.find(o => o.selected) || this.options[0]
        return selected ? selected.value : this._value
      }
      return this._value
    }
    set value(val) {
      this._value = String(val)
      if (this.tagName === 'SELECT') {
        let found = false
        this.options.forEach(o => {
          o.selected = (o.value === this._value)
          if (o.selected) found = true
        })
        if (!found && this.options.length > 0) {
          this.options[0].selected = true
        }
      }
    }

    get options() {
      if (this.tagName === 'SELECT') {
        const opts = []
        this.children.forEach(child => {
          if (child.tagName === 'OPTION') opts.push(child)
          else if (child.tagName === 'OPTGROUP') {
            child.children.forEach(sub => {
              if (sub.tagName === 'OPTION') opts.push(sub)
            })
          }
        })
        return opts
      }
      return []
    }

    get selectedIndex() {
      if (this.tagName === 'SELECT') {
        const opts = this.options
        const idx = opts.findIndex(o => o.selected)
        return idx >= 0 ? idx : (opts.length > 0 ? 0 : -1)
      }
      return -1
    }
    set selectedIndex(idx) {
      const opts = this.options
      opts.forEach((o, i) => {
        o.selected = (i === idx)
      })
    }

    get nextSibling() {
      if (!this.parentNode) return null
      const siblings = this.parentNode.childNodes
      const idx = siblings.indexOf(this)
      return idx >= 0 && idx + 1 < siblings.length ? siblings[idx + 1] : null
    }

    setAttribute(name, val) {
      this.attributes[name] = String(val)
      if (name.startsWith('data-')) {
        const key = name.slice(5).replace(/-([a-z])/g, (_, l) => l.toUpperCase())
        this.dataset[key] = String(val)
      }
      if (name === 'id') this._id = String(val)
      if (name === 'disabled') this.disabled = true
      this._notifyMutation({ type: 'attributes', attributeName: name })
    }

    getAttribute(name) {
      if (name === 'id') return this.id || null
      return this.attributes[name] !== undefined ? this.attributes[name] : null
    }

    hasAttribute(name) {
      return this.attributes[name] !== undefined
    }

    removeAttribute(name) {
      delete this.attributes[name]
      if (name.startsWith('data-')) {
        const key = name.slice(5).replace(/-([a-z])/g, (_, l) => l.toUpperCase())
        delete this.dataset[key]
      }
      if (name === 'id') this._id = ''
      if (name === 'disabled') this.disabled = false
      this._notifyMutation({ type: 'attributes', attributeName: name })
    }

    appendChild(child) {
      if (typeof child === 'string') {
        this.childNodes.push(child)
        return child
      }
      if (child.parentNode) {
        child.parentNode.removeChild(child)
      }
      child.parentNode = this
      this.childNodes.push(child)
      this.children.push(child)
      this._notifyMutation({ type: 'childList', addedNodes: [child] })
      return child
    }

    insertBefore(newNode, refNode) {
      if (newNode.parentNode) {
        newNode.parentNode.removeChild(newNode)
      }
      newNode.parentNode = this
      const idx = this.childNodes.indexOf(refNode)
      if (idx === -1) {
        this.childNodes.push(newNode)
        this.children.push(newNode)
      } else {
        this.childNodes.splice(idx, 0, newNode)
        const childIdx = this.children.indexOf(refNode)
        if (childIdx === -1) this.children.push(newNode)
        else this.children.splice(childIdx, 0, newNode)
      }
      this._notifyMutation({ type: 'childList', addedNodes: [newNode] })
      return newNode
    }

    removeChild(child) {
      const idx = this.childNodes.indexOf(child)
      if (idx !== -1) {
        this.childNodes.splice(idx, 1)
        child.parentNode = null
      }
      const cIdx = this.children.indexOf(child)
      if (cIdx !== -1) {
        this.children.splice(cIdx, 1)
      }
      this._notifyMutation({ type: 'childList', removedNodes: [child] })
      return child
    }

    remove() {
      if (this.parentNode) {
        this.parentNode.removeChild(this)
      }
    }

    append(...nodes) {
      nodes.forEach(node => {
        if (typeof node === 'string') {
          this.appendChild(node)
        } else {
          this.appendChild(node)
        }
      })
    }

    replaceChildren(...nodes) {
      const removed = [...this.children]
      this.childNodes = []
      this.children = []
      nodes.forEach(n => {
        if (typeof n === 'string') this.childNodes.push(n)
        else {
          n.parentNode = this
          this.childNodes.push(n)
          this.children.push(n)
        }
      })
      this._notifyMutation({ type: 'childList', addedNodes: nodes, removedNodes: removed })
    }

    addEventListener(event, fn) {
      if (!this.listeners[event]) this.listeners[event] = []
      this.listeners[event].push(fn)
    }

    removeEventListener(event, fn) {
      if (!this.listeners[event]) return
      this.listeners[event] = this.listeners[event].filter(l => l !== fn)
    }

    dispatchEvent(evt) {
      Object.defineProperty(evt, 'target', { value: this, configurable: true, writable: true })
      let current = this
      while (current) {
        const list = current.listeners[evt.type] || []
        for (const fn of list) {
          fn.call(current, evt)
        }
        if (!evt.bubbles) break
        current = current.parentNode
      }
      return true
    }

    focus() {
      this._focused = true
    }

    contains(other) {
      if (!other) return false
      let cur = other
      while (cur) {
        if (cur === this) return true
        cur = cur.parentNode
      }
      return false
    }

    querySelector(selector) {
      return this.querySelectorAll(selector)[0] || null
    }

    querySelectorAll(selector) {
      const results = []
      const match = (el) => {
        if (selector === '[role="option"]') {
          if (el.getAttribute('role') === 'option') results.push(el)
        } else if (selector === 'select[data-searchable-select]') {
          if (el.tagName === 'SELECT' && ('searchableSelect' in el.dataset || el.hasAttribute('data-searchable-select'))) {
            results.push(el)
          }
        } else if (selector.startsWith('label[for="')) {
          const targetId = selector.slice(11, -2)
          if (el.tagName === 'LABEL' && el.getAttribute('for') === targetId) {
            results.push(el)
          }
        } else if (selector.startsWith('.')) {
          const cls = selector.slice(1)
          if (el.classList.contains(cls)) results.push(el)
        } else if (selector === 'select') {
          if (el.tagName === 'SELECT') results.push(el)
        }
        el.children.forEach(match)
      }
      this.children.forEach(match)
      return results
    }

    _notifyMutation(record) {
      record.target = this
      let cur = this
      while (cur) {
        cur._observers.forEach(obs => {
          let matches = false
          if (record.type === 'childList' && (obs.options.childList || (obs.options.subtree && cur !== this))) {
            matches = true
          } else if (record.type === 'attributes' && (obs.options.attributes || (obs.options.subtree && cur !== this))) {
            if (!obs.options.attributeFilter || obs.options.attributeFilter.includes(record.attributeName)) {
              matches = true
            }
          }
          if (matches) {
            obs.callback([record], obs)
          }
        })
        cur = cur.parentNode
      }
    }
  }

  class MockMutationObserver {
    constructor(callback) {
      this.callback = callback
      this.target = null
      this.options = null
    }
    observe(target, options) {
      this.target = target
      this.options = options || {}
      target._observers.push(this)
    }
    disconnect() {
      if (this.target) {
        this.target._observers = this.target._observers.filter(o => o !== this)
      }
    }
  }

  const rootDocument = new MockElement('#DOCUMENT')
  const body = new MockElement('BODY')
  rootDocument.appendChild(body)

  const doc = {
    readyState: 'complete',
    body,
    createElement(tag) {
      return new MockElement(tag)
    },
    querySelector(selector) {
      return rootDocument.querySelector(selector)
    },
    querySelectorAll(selector) {
      return rootDocument.querySelectorAll(selector)
    },
    addEventListener(event, fn) {
      if (!documentListeners[event]) documentListeners[event] = []
      documentListeners[event].push(fn)
    },
    removeEventListener(event, fn) {
      if (!documentListeners[event]) return
      documentListeners[event] = documentListeners[event].filter(l => l !== fn)
    },
    dispatchEvent(evt) {
      const list = documentListeners[evt.type] || []
      for (const fn of list) {
        fn(evt)
      }
    }
  }

  return {
    document: doc,
    body,
    MockElement,
    MockMutationObserver
  }
}

// Helper to set up global environment and load module
function setupTestEnvironment() {
  const env = createDOMEnvironment()
  global.document = env.document
  global.window = {
    document: env.document,
    eventyayInitSearchableSelects: null,
  }
  global.MutationObserver = env.MockMutationObserver
  global.CSS = {
    escape: (s) => String(s).replace(/([ #;?%&,.+*~\':"!^$[\]()=>|\/@])/g, '\\$1')
  }

  delete require.cache[require.resolve('./searchable-select.js')]
  const mod = require('./searchable-select.js')
  return { ...env, mod }
}

test('initialization replaces select with accessible searchable component', () => {
  const { document, body, mod } = setupTestEnvironment()

  const label = document.createElement('label')
  label.setAttribute('for', 'id_organizer')
  label.textContent = 'Organizer'
  body.appendChild(label)

  const select = document.createElement('select')
  select.id = 'id_organizer'
  select.name = 'organizer'
  select.setAttribute('data-searchable-select', '')
  select.setAttribute('data-search-placeholder', 'Search organizers')
  select.setAttribute('data-empty-text', 'No matching organizers')
  select.setAttribute('data-all-label', 'All organizers')

  const opt0 = document.createElement('option')
  opt0.value = ''
  opt0.textContent = 'All organizers'
  opt0.selected = true
  const opt1 = document.createElement('option')
  opt1.value = 'fossasia'
  opt1.textContent = 'FOSSASIA'
  const opt2 = document.createElement('option')
  opt2.value = 'eventyay'
  opt2.textContent = 'Eventyay'

  select.appendChild(opt0)
  select.appendChild(opt1)
  select.appendChild(opt2)
  body.appendChild(select)

  mod.initSearchableSelect(select)

  const root = select.parentNode
  assert.ok(root.classList.contains('searchable-select'))
  assert.ok(root.classList.contains('is-enhanced'))

  assert.ok(select.classList.contains('searchable-select__native'))
  assert.equal(select.tabIndex, -1)
  assert.equal(select.getAttribute('aria-hidden'), 'true')
  assert.equal(select.dataset.searchableSelectReady, '1')

  const toggle = root.querySelector('.searchable-select__toggle')
  assert.ok(toggle)
  assert.equal(toggle.getAttribute('aria-haspopup'), 'listbox')
  assert.equal(toggle.getAttribute('aria-expanded'), 'false')
  assert.equal(toggle.getAttribute('aria-controls'), 'id_organizer-listbox')

  const valueSpan = root.querySelector('.searchable-select__value')
  assert.equal(valueSpan.textContent, 'All organizers')

  const panel = root.querySelector('.searchable-select__panel')
  assert.equal(panel.hidden, true)

  const searchInput = root.querySelector('.searchable-select__search')
  assert.equal(searchInput.placeholder, 'Search organizers')
  assert.equal(searchInput.getAttribute('aria-label'), 'Search organizers')

  const list = root.querySelector('.searchable-select__list')
  assert.equal(list.getAttribute('role'), 'listbox')
  const items = list.querySelectorAll('[role="option"]')
  assert.equal(items.length, 3)
  assert.equal(items[0].dataset.value, '')
  assert.equal(items[0].textContent, 'All organizers')
  assert.equal(items[1].dataset.value, 'fossasia')
  assert.equal(items[1].textContent, 'FOSSASIA')
  assert.equal(items[2].dataset.value, 'eventyay')
  assert.equal(items[2].textContent, 'Eventyay')
})

test('filtering matches case/accent-insensitively and shows empty state on no match', () => {
  const { document, body, mod } = setupTestEnvironment()

  const select = document.createElement('select')
  select.id = 'filter_test'
  select.setAttribute('data-searchable-select', '')
  select.setAttribute('data-search-placeholder', 'Search')
  select.setAttribute('data-empty-text', 'No matching results')
  select.setAttribute('data-all-label', 'All items')

  const opt0 = document.createElement('option')
  opt0.value = ''
  opt0.textContent = 'All items'
  const opt1 = document.createElement('option')
  opt1.value = 'cafe'
  opt1.textContent = 'Café München'
  const opt2 = document.createElement('option')
  opt2.value = 'tech'
  opt2.textContent = 'Tech Conference'

  select.appendChild(opt0)
  select.appendChild(opt1)
  select.appendChild(opt2)
  body.appendChild(select)

  mod.initSearchableSelect(select)
  const root = select.parentNode
  const toggle = root.querySelector('.searchable-select__toggle')
  const panel = root.querySelector('.searchable-select__panel')
  const searchInput = root.querySelector('.searchable-select__search')
  const empty = root.querySelector('.searchable-select__empty')
  const list = root.querySelector('.searchable-select__list')
  const items = list.querySelectorAll('[role="option"]')

  // Open dropdown
  toggle.dispatchEvent(new Event('click'))
  assert.equal(panel.hidden, false)
  assert.equal(toggle.getAttribute('aria-expanded'), 'true')

  // Search with accents/lowercase "cafe"
  searchInput.value = 'cafe'
  searchInput.dispatchEvent(new Event('input'))

  assert.equal(items[0].hidden, false) // All items remains visible when all-label is configured
  assert.equal(items[1].hidden, false) // Café München matches
  assert.equal(items[2].hidden, true)  // Tech Conference hidden
  assert.equal(empty.hidden, true)

  // Search with no-match query "xyz"
  searchInput.value = 'xyz'
  searchInput.dispatchEvent(new Event('input'))

  assert.equal(items[1].hidden, true)
  assert.equal(items[2].hidden, true)
  assert.equal(empty.hidden, false)
  assert.equal(empty.textContent, 'No matching results')
})

test('choosing an option updates native select, fires change event, and closes menu', () => {
  const { document, body, mod } = setupTestEnvironment()

  const select = document.createElement('select')
  select.id = 'choose_test'
  select.setAttribute('data-searchable-select', '')

  const opt0 = document.createElement('option')
  opt0.value = ''
  opt0.textContent = 'Select one'
  const opt1 = document.createElement('option')
  opt1.value = 'val1'
  opt1.textContent = 'First Choice'

  select.appendChild(opt0)
  select.appendChild(opt1)
  body.appendChild(select)

  let changeFired = 0
  select.addEventListener('change', () => {
    changeFired++
  })

  mod.initSearchableSelect(select)
  const root = select.parentNode
  const toggle = root.querySelector('.searchable-select__toggle')
  const panel = root.querySelector('.searchable-select__panel')
  const valueSpan = root.querySelector('.searchable-select__value')
  const list = root.querySelector('.searchable-select__list')
  const items = list.querySelectorAll('[role="option"]')

  // Open
  toggle.dispatchEvent(new Event('click'))
  assert.equal(panel.hidden, false)

  // Click on second option
  items[1].dispatchEvent(new Event('click'))

  assert.equal(select.value, 'val1')
  assert.equal(changeFired, 1)
  assert.equal(valueSpan.textContent, 'First Choice')
  assert.equal(panel.hidden, true)
  assert.equal(toggle.getAttribute('aria-expanded'), 'false')
  assert.equal(items[1].getAttribute('aria-selected'), 'true')
})

test('clearing selection resets native select value to empty', () => {
  const { document, body, mod } = setupTestEnvironment()

  const select = document.createElement('select')
  select.id = 'clear_test'
  select.setAttribute('data-searchable-select', '')
  select.setAttribute('data-all-label', 'All organizers')

  const opt0 = document.createElement('option')
  opt0.value = ''
  opt0.textContent = 'All organizers'
  const opt1 = document.createElement('option')
  opt1.value = 'stats-orga'
  opt1.textContent = 'Stats Orga'
  opt1.selected = true

  select.appendChild(opt0)
  select.appendChild(opt1)
  body.appendChild(select)

  mod.initSearchableSelect(select)
  const root = select.parentNode
  const valueSpan = root.querySelector('.searchable-select__value')
  const list = root.querySelector('.searchable-select__list')
  const items = list.querySelectorAll('[role="option"]')

  assert.equal(select.value, 'stats-orga')
  assert.equal(valueSpan.textContent, 'Stats Orga')

  // Click 'All organizers' (empty value)
  items[0].dispatchEvent(new Event('click'))

  assert.equal(select.value, '')
  assert.equal(valueSpan.textContent, 'All organizers')
})

test('keyboard navigation and Enter selection work as expected', () => {
  const { document, body, mod } = setupTestEnvironment()

  const select = document.createElement('select')
  select.id = 'kb_test'
  select.setAttribute('data-searchable-select', '')

  const opt0 = document.createElement('option')
  opt0.value = 'opt0'
  opt0.textContent = 'Option 0'
  const opt1 = document.createElement('option')
  opt1.value = 'opt1'
  opt1.textContent = 'Option 1'

  select.appendChild(opt0)
  select.appendChild(opt1)
  body.appendChild(select)

  mod.initSearchableSelect(select)
  const root = select.parentNode
  const toggle = root.querySelector('.searchable-select__toggle')
  const panel = root.querySelector('.searchable-select__panel')
  const searchInput = root.querySelector('.searchable-select__search')

  // Open
  toggle.dispatchEvent(new Event('click'))
  assert.equal(panel.hidden, false)

  // Navigate down with ArrowDown
  const arrowDownEvt = new Event('keydown')
  arrowDownEvt.key = 'ArrowDown'
  searchInput.dispatchEvent(arrowDownEvt)

  // Select active item with Enter
  const enterEvt = new Event('keydown')
  enterEvt.key = 'Enter'
  searchInput.dispatchEvent(enterEvt)

  assert.equal(select.value, 'opt1')
  assert.equal(panel.hidden, true)
})

test('option-list lifecycle: dynamic repopulation triggers MutationObserver and rebuilds list', () => {
  const { document, body, mod } = setupTestEnvironment()

  const select = document.createElement('select')
  select.id = 'lifecycle_test'
  select.setAttribute('data-searchable-select', '')

  const opt0 = document.createElement('option')
  opt0.value = 'initial'
  opt0.textContent = 'Initial Option'
  select.appendChild(opt0)
  body.appendChild(select)

  mod.initSearchableSelect(select)
  const root = select.parentNode
  const list = root.querySelector('.searchable-select__list')
  let items = list.querySelectorAll('[role="option"]')
  assert.equal(items.length, 1)
  assert.equal(items[0].textContent, 'Initial Option')

  // Dynamically append new option to native select
  const opt1 = document.createElement('option')
  opt1.value = 'added'
  opt1.textContent = 'Added Option'
  select.appendChild(opt1)

  // MutationObserver triggers rebuild automatically
  items = list.querySelectorAll('[role="option"]')
  assert.equal(items.length, 2)
  assert.equal(items[1].textContent, 'Added Option')

  // Wholesale replacement of options (e.g. repopulated via AJAX or dynamic form logic)
  const optNew1 = document.createElement('option')
  optNew1.value = 'brand_new'
  optNew1.textContent = 'Brand New'
  select.replaceChildren(optNew1)

  items = list.querySelectorAll('[role="option"]')
  assert.equal(items.length, 1)
  assert.equal(items[0].textContent, 'Brand New')

  // Verify manual rebuild event and function
  const optManual = document.createElement('option')
  optManual.value = 'manual'
  optManual.textContent = 'Manual Option'
  select.childNodes.push(optManual)
  select.children.push(optManual)

  select.dispatchEvent(new Event('eventyay:rebuild'))
  items = list.querySelectorAll('[role="option"]')
  assert.equal(items.length, 2)
  assert.equal(items[1].textContent, 'Manual Option')
})

test('disabled select synchronization and disabled options handling', () => {
  const { document, body, mod } = setupTestEnvironment()

  const select = document.createElement('select')
  select.id = 'disabled_test'
  select.setAttribute('data-searchable-select', '')

  const opt0 = document.createElement('option')
  opt0.value = 'enabled'
  opt0.textContent = 'Enabled'
  const opt1 = document.createElement('option')
  opt1.value = 'disabled_opt'
  opt1.textContent = 'Disabled Opt'
  opt1.disabled = true

  select.appendChild(opt0)
  select.appendChild(opt1)
  body.appendChild(select)

  mod.initSearchableSelect(select)
  const root = select.parentNode
  const toggle = root.querySelector('.searchable-select__toggle')
  const panel = root.querySelector('.searchable-select__panel')
  const list = root.querySelector('.searchable-select__list')
  const items = list.querySelectorAll('[role="option"]')

  assert.equal(items[1].getAttribute('aria-disabled'), 'true')

  // Clicking disabled item does not choose it
  items[1].dispatchEvent(new Event('click'))
  assert.notEqual(select.value, 'disabled_opt')

  // Setting select disabled closes panel and disables toggle
  select.setAttribute('disabled', 'disabled')
  assert.equal(toggle.disabled, true)

  toggle.dispatchEvent(new Event('click'))
  assert.equal(panel.hidden, true) // Does not open when disabled
})

test('ignores select multiple', () => {
  const { document, body, mod } = setupTestEnvironment()

  const select = document.createElement('select')
  select.multiple = true
  select.setAttribute('data-searchable-select', '')
  body.appendChild(select)

  mod.initSearchableSelect(select)
  assert.equal(select.parentNode, body)
  assert.equal(select.dataset.searchableSelectReady, undefined)
})

test('resilient error fallback restores native select cleanly', () => {
  const { document, body, mod } = setupTestEnvironment()

  const select = document.createElement('select')
  select.id = 'error_test'
  select.setAttribute('data-searchable-select', '')
  body.appendChild(select)

  // Force an error inside initialization (e.g. broken DOM API)
  const origCreate = document.createElement
  const origConsoleError = console.error
  console.error = () => {}
  document.createElement = () => {
    throw new Error('Forced DOM failure')
  }

  try {
    mod.initSearchableSelect(select)

    // Restores original state
    assert.equal(select.parentNode, body)
    assert.equal(select.classList.contains('searchable-select__native'), false)
    assert.equal(select.dataset.searchableSelectReady, undefined)
  } finally {
    document.createElement = origCreate
    console.error = origConsoleError
  }
})

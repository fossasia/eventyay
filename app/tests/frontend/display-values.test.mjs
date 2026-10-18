import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { runInNewContext } from 'node:vm'

const marker = '<b>Audit & "sample"</b>'
const source = (path) => readFileSync(new URL(`../../eventyay/static/${path}`, import.meta.url), 'utf8')
const flush = () => new Promise(setImmediate)

class Element {
  constructor(tagName) {
    this.tagName = tagName
    this.children = []
    this.classList = { remove() {} }
  }

  append(...children) {
    this.children.push(...children)
  }

  replaceChildren(...children) {
    this.children = children
  }

  set textContent(value) {
    this.children = [String(value)]
  }

  get textContent() {
    return this.children.map(child => typeof child === 'string' ? child : child.textContent).join('')
  }

  set innerHTML(html) {
    assert.ok(!html.includes(marker), 'Display values must never be parsed as HTML')
    this.html = html
    this.children = []
  }
}

const document = {
  createElement: tagName => new Element(tagName),
  createTextNode: value => String(value),
  addEventListener() {},
}

for (const type of ['organiser', 'user', 'user.admin', 'submission', 'speaker', 'event']) {
  test(`navigation displays ${type} values literally and preserves the link`, async () => {
    const handlers = {}
    const input = new Element('input')
    input.value = 'Audit'
    input.addEventListener = (name, handler) => { handlers[name] = handler }
    const list = new Element('ul')
    const search = {
      getAttribute: () => '/fixture',
      querySelectorAll: () => [],
      querySelector: () => list,
    }
    const wrapper = {
      querySelector: selector => selector === 'input' ? input : search,
      addEventListener() {},
    }
    const result = {
      type, name: marker, email: marker, event: marker,
      organiser: marker, date_range: marker,
      url: '/orga/demo/?q="&value=<b>',
    }
    runInNewContext(source('orga/js/typeahead.js'), {
      document: { ...document, querySelector: () => wrapper },
      onReady: fn => fn(),
      setTimeout: () => 1,
      clearTimeout() {},
      fetch: async () => ({ json: async () => ({ results: [result] }) }),
    })
    handlers.input()
    await flush()
    assert.equal(list.children.length, 1)
    const link = list.children[0].children[0]
    assert.equal(link.tagName, 'a')
    assert.equal(link.href, result.url)
    assert.equal(link.children[0].className, 'search-title')
    assert.ok(link.children[0].textContent.includes(marker))
    for (const detail of link.children.slice(1)) {
      assert.equal(detail.className, 'search-detail')
      assert.equal(detail.children[0].tagName, 'i')
      assert.ok(detail.textContent.includes(marker))
    }
    assert.equal(link.children.length, type === 'event' ? 3 : ['user.admin', 'submission', 'speaker'].includes(type) ? 2 : 1)
  })
}

async function renderRecipients(data, error) {
  const panel = new Element('div')
  panel.dataset = { recipientsUrl: '/fixture' }
  const logged = []
  runInNewContext(source('pretixcontrol/js/admin-messages-sent-detail.js'), {
    document: { ...document, getElementById: () => panel },
    fetch: async () => {
      if (error) throw error
      return { json: async () => data }
    },
    console: { error: (...args) => logged.push(args) },
  })
  await flush()
  return { panel, logged }
}

test('recipient fields remain text while status badges and pagination remain intact', async () => {
  const { panel } = await renderRecipients({
    recipients: [
      { email: marker, name: marker, error: marker, sent: false },
      { email: 'demo@example.test', name: '', error: null, sent: true },
    ],
    has_more: true,
  })
  const table = panel.children[0]
  assert.equal(table.tagName, 'table')
  assert.equal(table.className, 'table table-condensed')
  assert.ok(table.html.includes('<th>Name</th>'))
  const rows = table.children[0].children
  assert.equal(rows.length, 2)
  const cells = rows[0].children
  for (const index of [0, 1, 3]) assert.equal(cells[index].textContent, marker)
  assert.equal(cells[2].children[0].className, 'label label-danger')
  assert.equal(cells[2].textContent, 'Failed')
  assert.equal(rows[1].children[1].textContent, '')
  assert.equal(rows[1].children[3].textContent, '')
  assert.equal(rows[1].children[2].children[0].className, 'label label-success')
  assert.equal(rows[1].children[2].textContent, 'Sent')
  assert.equal(panel.children[1].textContent, 'More recipients not shown.')
})

test('empty recipient lists still display the empty state', async () => {
  const { panel } = await renderRecipients({ recipients: [], has_more: false })
  assert.ok(panel.html.includes('No recipients found.'))
})

test('failed requests retain the error state and log the original error', async () => {
  const error = new TypeError('Network unavailable')
  const { panel, logged } = await renderRecipients(null, error)
  assert.ok(panel.html.includes('Could not load recipient list.'))
  assert.equal(logged[0][1], error)
})

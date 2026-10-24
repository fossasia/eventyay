import assert from 'node:assert/strict'
import { Buffer } from 'node:buffer'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import test from 'node:test'
import { pathToFileURL } from 'node:url'
import { compileScript, parse } from '@vue/compiler-sfc'
import ts from 'typescript'
import { createRenderer, defineComponent, h, markRaw, nextTick, ref } from 'vue'

// Compile the real SFC, including its Pug template, without a browser dependency.
const require = createRequire(import.meta.url)
const source = readFileSync(new URL('./ConfirmDialog.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)
const script = compileScript(descriptor, {
  id: 'confirm-dialog-test', inlineTemplate: true, templateOptions: { preprocessLang: 'pug' },
})
const code = ts.transpileModule(script.content, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
}).outputText.replace(/from (['"])vue\1/g, `from '${pathToFileURL(require.resolve('vue')).href}'`)
const { default: ConfirmDialog } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)

function mountDialog() {
  const oldDocument = globalThis.document
  const document = { activeElement: null }
  globalThis.document = document
  const element = type => markRaw({
    type, props: {}, children: [], parent: null,
    focus() { document.activeElement = this },
    querySelectorAll() { return descendants(this).filter(el => el.type === 'button' && !el.props.disabled) },
  })
  const renderer = createRenderer({
    createElement: element,
    createText: text => ({ text }), createComment: text => ({ text }),
    setText: (node, text) => { node.text = text },
    setElementText: (node, text) => { node.text = text },
    patchProp: (node, key, before, after) => { node.props[key] = after },
    parentNode: node => node.parent,
    nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1],
    remove(node) { node.parent?.children.splice(node.parent.children.indexOf(node), 1); node.parent = null },
    insert(node, parent, anchor) {
      if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
      node.parent = parent
      const index = anchor ? parent.children.indexOf(anchor) : parent.children.length
      parent.children.splice(index, 0, node)
    },
  })
  const root = element('root'), opener = element('opener')
  opener.focus()
  const busy = ref(false), dialog = ref(null), events = []
  const app = renderer.createApp(defineComponent({
    setup: () => () => h(ConfirmDialog, {
      title: 'Delete shift?', busy: busy.value, ref: dialog,
      onCancel: () => events.push('cancel'), onConfirm: () => events.push('confirm'),
    }),
  }))
  app.config.globalProperties.$t = text => text
  app.mount(root)
  return {
    root, opener, busy, events, document, dialog,
    panel: () => descendants(root).find(el => el.props?.class === 'ts-confirm-panel'),
    async show() { dialog.value.show(); await nextTick() },
    cleanup() { app.unmount(); globalThis.document = oldDocument },
  }
}

function descendants(node) {
  return (node.children || []).flatMap(child => [child, ...descendants(child)])
}

function key(panel, value, shiftKey = false) {
  const event = { key: value, shiftKey, prevented: false, stopped: false,
    preventDefault() { this.prevented = true }, stopPropagation() { this.stopped = true } }
  panel.props.onKeydown?.(event)
  return event
}

test('opening focuses the labelled dialog; Escape cancels and restores its opener', async () => {
  const m = mountDialog()
  try {
    await m.show()
    const panel = m.panel()
    assert.ok(m.document.activeElement === panel, 'focus stays in the expected element')
    assert.equal(panel.props.role, 'dialog')
    assert.equal(panel.props['aria-label'], 'Delete shift?')
    const event = key(panel, 'Escape')
    await nextTick()
    assert.deepEqual(m.events, ['cancel'])
    assert.equal(m.panel(), undefined)
    assert.ok(m.document.activeElement === m.opener, 'focus stays in the expected element')
    assert.ok(event.prevented && event.stopped)
  } finally { m.cleanup() }
})

test('Escape is ignored while busy and works when the operation becomes idle', async () => {
  const m = mountDialog()
  try {
    m.busy.value = true
    await m.show()
    key(m.panel(), 'Escape')
    await nextTick()
    assert.ok(m.panel())
    assert.deepEqual(m.events, [])
    m.busy.value = false
    await nextTick()
    key(m.panel(), 'Escape')
    await nextTick()
    assert.deepEqual(m.events, ['cancel'])
  } finally { m.cleanup() }
})

test('unrelated keys do not cancel or consume the event', async () => {
  const m = mountDialog()
  try {
    await m.show()
    const event = key(m.panel(), 'ArrowRight')
    assert.deepEqual(m.events, [])
    assert.equal(event.prevented, false)
    assert.equal(event.stopped, false)
  } finally { m.cleanup() }
})

test('Tab wraps enabled buttons in either direction', async () => {
  const m = mountDialog()
  try {
    await m.show()
    const panel = m.panel(), buttons = panel.querySelectorAll('button:not(:disabled)')
    buttons.at(-1).focus()
    assert.ok(key(panel, 'Tab').prevented)
    assert.ok(m.document.activeElement === buttons[0], 'focus stays in the expected element')
    assert.ok(key(panel, 'Tab', true).prevented)
    assert.ok(m.document.activeElement === buttons.at(-1, 'focus stays in the expected element'))
    panel.focus()
    key(panel, 'Tab', true)
    assert.ok(m.document.activeElement === buttons.at(-1, 'focus stays in the expected element'))
  } finally { m.cleanup() }
})

test('programmatic close restores focus without emitting cancellation', async () => {
  const m = mountDialog()
  try {
    await m.show()
    m.panel().querySelectorAll('button')[0].focus()
    m.dialog.value.close()
    await nextTick()
    assert.ok(m.document.activeElement === m.opener, 'focus stays in the expected element')
    assert.deepEqual(m.events, [])
  } finally { m.cleanup() }
})

test('confirm remains parent-controlled and does not automatically close', async () => {
  const m = mountDialog()
  try {
    await m.show()
    m.panel().querySelectorAll('button').at(-1).props.onClick()
    await nextTick()
    assert.deepEqual(m.events, ['confirm'])
    assert.ok(m.panel())
  } finally { m.cleanup() }
})

test('show then close before the next tick does not steal focus', async () => {
  const m = mountDialog()
  try {
    m.dialog.value.show()
    m.dialog.value.close()
    await nextTick()
    assert.ok(m.document.activeElement === m.opener)
    assert.equal(m.panel(), undefined)
    assert.deepEqual(m.events, [])
  } finally { m.cleanup() }
})

test('unmounting an open dialog restores focus to its opener', async () => {
  const m = mountDialog()
  try {
    await m.show()
    m.panel().querySelectorAll('button')[0].focus()
    m.cleanup()
    assert.ok(m.document.activeElement === m.opener)
  } finally { m.cleanup() }
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const vueFile = readFileSync(join(__dirname, './ConfirmDialog.vue'), 'utf-8')

test('ConfirmDialog template has accessibility dialog semantics', () => {
  assert.match(vueFile, /role="dialog"/, 'Dialog panel should have role="dialog"')
  assert.match(vueFile, /aria-modal="true"/, 'Dialog panel should have aria-modal="true"')
  assert.match(vueFile, /aria-labelledby="confirm-dialog-title"/, 'Dialog panel should have aria-labelledby')
  assert.match(vueFile, /h3#confirm-dialog-title/, 'Heading should have matching id')
})

test('ConfirmDialog script registers Escape keydown listener and focus management', () => {
  assert.match(vueFile, /event\.key === 'Escape'/, 'Handles Escape key')
  assert.match(vueFile, /event\.stopImmediatePropagation/, 'Stops immediate event propagation')
  assert.match(vueFile, /addEventListener\('keydown', onKeydown, true\)/, 'Attaches keydown listener on window with capture')
  assert.match(vueFile, /removeEventListener\('keydown', onKeydown, true\)/, 'Cleans up keydown listener on window')
  assert.match(vueFile, /previousActiveElement/, 'Saves previous active element for restoration')
  assert.match(vueFile, /event\.key === 'Tab'/, 'Traps Tab key navigation inside panel')
  assert.match(vueFile, /if \(props\.busy\) return/, 'Guards cancel while busy')
})

function createDialogRunner(props = {}) {
  let visible = false
  const listeners = []
  const emits = []
  let previousActiveElement = null

  const fakeDocument = {
    activeElement: { name: 'trigger-btn', focus() { fakeDocument.activeElement = this } },
    contains(el) { return el != null }
  }

  const windowObj = {
    addEventListener(event, fn, useCapture) { listeners.push({ event, fn, useCapture }) },
    removeEventListener(event, fn, useCapture) {
      const idx = listeners.findIndex(l => l.event === event && l.fn === fn && l.useCapture === useCapture)
      if (idx !== -1) listeners.splice(idx, 1)
    }
  }

  const focusables = [
    { name: 'cancel-btn', focus() { fakeDocument.activeElement = this } },
    { name: 'confirm-btn', focus() { fakeDocument.activeElement = this } }
  ]

  const fakePanel = {
    contains(el) { return focusables.includes(el) },
    querySelectorAll() { return focusables }
  }

  function emit(name) { emits.push(name) }

  function cancel() {
    if (props.busy) return
    close()
    emit('cancel')
  }

  function onKeydown(event) {
    if (!visible) return
    if (event.key === 'Escape') {
      if (!props.busy) {
        event.preventDefault?.()
        event.stopPropagation?.()
        event.stopImmediatePropagation?.()
        cancel()
      }
      return
    }

    if (event.key === 'Tab') {
      const first = focusables[0]
      const last = focusables[focusables.length - 1]
      if (event.shiftKey) {
        if (fakeDocument.activeElement === first || !fakePanel.contains(fakeDocument.activeElement)) {
          event.preventDefault?.()
          last.focus()
        }
      } else {
        if (fakeDocument.activeElement === last || !fakePanel.contains(fakeDocument.activeElement)) {
          event.preventDefault?.()
          first.focus()
        }
      }
    }
  }

  function show() {
    previousActiveElement = fakeDocument.activeElement
    visible = true
    windowObj.addEventListener('keydown', onKeydown, true)
    focusables[0].focus()
  }

  function close() {
    visible = false
    windowObj.removeEventListener('keydown', onKeydown, true)
    if (previousActiveElement && fakeDocument.contains(previousActiveElement)) {
      previousActiveElement.focus()
    }
    previousActiveElement = null
  }

  return {
    show,
    close,
    cancel,
    onKeydown,
    get visible() { return visible },
    get listenerCount() { return listeners.length },
    get emits() { return emits },
    get activeElement() { return fakeDocument.activeElement },
    fakeDocument
  }
}

test('Escape dismisses visible dialog and restores prior focus', () => {
  const runner = createDialogRunner()
  const initialTrigger = runner.activeElement

  runner.show()
  assert.equal(runner.visible, true)
  assert.equal(runner.activeElement.name, 'cancel-btn')
  assert.equal(runner.listenerCount, 1)

  let stopped = false
  runner.onKeydown({ key: 'Escape', stopImmediatePropagation() { stopped = true } })

  assert.equal(stopped, true, 'Immediate propagation stopped')
  assert.equal(runner.visible, false, 'Dialog closed')
  assert.equal(runner.listenerCount, 0, 'Listener cleaned up')
  assert.equal(runner.activeElement, initialTrigger, 'Restored prior focus')
  assert.deepEqual(runner.emits, ['cancel'])
})

test('Tab navigation wraps at dialog boundaries (focus trap)', () => {
  const runner = createDialogRunner()
  runner.show()
  assert.equal(runner.activeElement.name, 'cancel-btn')

  // Tab from first -> moves to confirm
  runner.fakeDocument.activeElement = { name: 'confirm-btn' } // on last
  let prevented = false
  runner.onKeydown({ key: 'Tab', preventDefault() { prevented = true } })
  assert.equal(prevented, true)
  assert.equal(runner.activeElement.name, 'cancel-btn', 'Wrapped from last to first')

  // Shift+Tab from first -> wraps to last
  prevented = false
  runner.onKeydown({ key: 'Tab', shiftKey: true, preventDefault() { prevented = true } })
  assert.equal(prevented, true)
  assert.equal(runner.activeElement.name, 'confirm-btn', 'Wrapped from first to last')
})

test('Escape does not dismiss dialog when busy is true', () => {
  const runner = createDialogRunner({ busy: true })
  runner.show()
  assert.equal(runner.visible, true)

  let stopped = false
  runner.onKeydown({ key: 'Escape', stopImmediatePropagation() { stopped = true } })

  assert.equal(stopped, false)
  assert.equal(runner.visible, true)
  assert.deepEqual(runner.emits, [])
})

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

test('ConfirmDialog script registers Escape keydown listener', () => {
  assert.match(vueFile, /event\.key === 'Escape'/, 'Handles Escape key')
  assert.match(vueFile, /event\.stopPropagation\(\)/, 'Stops event propagation')
  assert.match(vueFile, /addEventListener\('keydown', onKeydown\)/, 'Attaches keydown listener on window')
  assert.match(vueFile, /removeEventListener\('keydown', onKeydown\)/, 'Cleans up keydown listener on window')
  assert.match(vueFile, /if \(props\.busy\) return/, 'Guards cancel while busy')
})

// Behavioral test verifying the escape & busy lifecycle logic
function createDialogRunner(props = {}) {
  let visible = false
  const listeners = []
  const emits = []
  const windowObj = {
    addEventListener(event, fn) { listeners.push({ event, fn }) },
    removeEventListener(event, fn) {
      const idx = listeners.findIndex(l => l.event === event && l.fn === fn)
      if (idx !== -1) listeners.splice(idx, 1)
    }
  }

  function emit(name) {
    emits.push(name)
  }

  function cancel() {
    if (props.busy) return
    close()
    emit('cancel')
  }

  function onKeydown(event) {
    if (event.key === 'Escape' && visible && !props.busy) {
      event.stopPropagation?.()
      cancel()
    }
  }

  function show() {
    visible = true
    windowObj.addEventListener('keydown', onKeydown)
  }

  function close() {
    visible = false
    windowObj.removeEventListener('keydown', onKeydown)
  }

  return {
    show,
    close,
    cancel,
    onKeydown,
    get visible() { return visible },
    get listenerCount() { return listeners.length },
    get emits() { return emits }
  }
}

test('Escape dismisses visible dialog and cleans up listener', () => {
  const runner = createDialogRunner()
  assert.equal(runner.visible, false)
  assert.equal(runner.listenerCount, 0)

  runner.show()
  assert.equal(runner.visible, true)
  assert.equal(runner.listenerCount, 1)

  let stopped = false
  runner.onKeydown({ key: 'Escape', stopPropagation() { stopped = true } })

  assert.equal(stopped, true, 'Propagation was stopped')
  assert.equal(runner.visible, false, 'Dialog closed')
  assert.equal(runner.listenerCount, 0, 'Listener cleaned up')
  assert.deepEqual(runner.emits, ['cancel'])
})

test('Escape does not dismiss dialog when busy is true', () => {
  const runner = createDialogRunner({ busy: true })
  runner.show()
  assert.equal(runner.visible, true)

  let stopped = false
  runner.onKeydown({ key: 'Escape', stopPropagation() { stopped = true } })

  assert.equal(stopped, false, 'Propagation should not be stopped when busy')
  assert.equal(runner.visible, true, 'Dialog should stay open when busy')
  assert.deepEqual(runner.emits, [], 'No cancel should be emitted when busy')
})

test('Non-escape keys do not dismiss dialog', () => {
  const runner = createDialogRunner()
  runner.show()

  let stopped = false
  runner.onKeydown({ key: 'Enter', stopPropagation() { stopped = true } })

  assert.equal(stopped, false)
  assert.equal(runner.visible, true)
  assert.deepEqual(runner.emits, [])
})

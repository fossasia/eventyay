import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { runInNewContext } from 'node:vm'

const editorSource = readFileSync(new URL('../../eventyay/static/pretixcontrol/js/ui/editor.js', import.meta.url), 'utf8')
const flush = () => new Promise(setImmediate)

function setupEditor() {
  const calls = []
  const context = {
    clearRect: (...args) => calls.push(['clear', ...args]),
  }
  const canvas = { width: 10, height: 10, getContext: () => context }
  const pdfjs = { isEvalSupported: true }
  const sandbox = {
    PDFJS: pdfjs,
    fabric: { util: { createClass: () => function () {} } },
    $: () => ({ bind() {} }),
    window: {},
    document: { getElementById: () => canvas },
    console: { log() {} },
    gettext: value => value,
  }
  runInNewContext(editorSource, sandbox)
  const editor = sandbox.editor
  editor.pdf_url = '/background.pdf'
  editor.$pdfcv = { attr: () => '/static/pdfjs/pdf.worker.js' }
  editor.$cva = { width: () => 600 }
  editor._sync_page_size_fields_from_viewport = viewport => calls.push(['size', viewport])
  editor._init_fabric = dump => calls.push(['fabric', dump])
  editor._error = message => calls.push(['error', message])
  const page = {
    userUnit: 1,
    getViewport: scale => ({ width: 300 * scale, height: 150 * scale }),
    render: options => {
      calls.push(['render', options])
      return Promise.resolve()
    },
  }
  pdfjs.getDocument = url => {
    assert.equal(pdfjs.isEvalSupported, false, 'Disable evaluation before starting every load')
    assert.equal(pdfjs.workerSrc, '/static/pdfjs/pdf.worker.js')
    calls.push(['load', url])
    return { promise: Promise.resolve({ getPage: async number => {
      assert.equal(number, 1)
      return page
    } }) }
  }
  return { editor, pdfjs, calls, canvas, context, page }
}

test('PDF loading disables evaluation and preserves first-page rendering and layout initialization', async () => {
  const { editor, calls, canvas, context, page } = setupEditor()
  editor._load_pdf({ objects: [] })
  await flush()
  assert.equal(calls[0][1], '/background.pdf')
  assert.equal(canvas.width, 600)
  assert.equal(canvas.height, 300)
  assert.equal(editor.pdf_page, page)
  assert.equal(editor.pdf_scale, 2)
  const render = calls.find(call => call[0] === 'render')[1]
  assert.equal(render.canvasContext, context)
  assert.equal(render.viewport.width, 600)
  assert.ok(calls.some(call => call[0] === 'size'))
  assert.equal(calls.find(call => call[0] === 'fabric')[1].objects.length, 0)
})

test('replacement PDF loads also disable evaluation and preserve explicit page dimensions', async () => {
  const { editor, pdfjs, calls } = setupEditor()
  editor._load_pdf()
  await flush()
  calls.length = 0
  pdfjs.isEvalSupported = true
  editor.pdf_url = '/replacement.pdf'
  editor._load_pdf(null, true)
  await flush()
  assert.equal(calls[0][1], '/replacement.pdf')
  assert.ok(calls.some(call => call[0] === 'render'))
  assert.ok(!calls.some(call => call[0] === 'size'))
})

test('PDF loading failures still display the existing translated error', async () => {
  const { editor, pdfjs, calls } = setupEditor()
  pdfjs.getDocument = () => {
    assert.equal(pdfjs.isEvalSupported, false)
    return { promise: Promise.reject(new Error('Invalid PDF')) }
  }
  editor._load_pdf()
  await flush()
  assert.ok(calls[0][1].includes('The PDF background file could not be loaded'))
  assert.ok(calls[0][1].includes('Invalid PDF'))
  assert.ok(!calls.some(call => call[0] === 'render'))
})

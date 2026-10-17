import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createServer } from 'vite'

let server
let api
let HTTPError

before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
  ;({ default: api, HTTPError } = await server.ssrLoadModule('/src/api.ts'))
})

after(async () => {
  await server?.close()
})

for (const status of [403, 500]) {
  for (const [name, body, contentType] of [
    ['JSON', JSON.stringify({ error: 'Forbidden' }), 'application/json'],
    ['HTML', '<h1>Forbidden</h1>', 'text/html'],
    ['invalid JSON', '{', 'application/json'],
  ]) {
    test(`preserves HTTP ${status} for ${name} responses`, async (t) => {
      t.mock.method(globalThis, 'fetch', async () => new Response(body, {
        status,
        headers: { 'Content-Type': contentType },
      }))
      await assert.rejects(api.http('GET', '/schedule/', null), (error) => {
        assert.ok(error instanceof HTTPError)
        assert.ok(error instanceof Error)
        assert.equal(error.status, status)
        assert.match(error.message, new RegExp(`^HTTP error ${status}: `))
        return true
      })
    })
  }
}

test('returns successful JSON responses unchanged', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => Response.json({ id: 1 }))
  assert.deepEqual(await api.http('GET', '/schedule/', null), { id: 1 })
})

test('keeps invalid successful JSON as a parsing error', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response('{', {
    headers: { 'Content-Type': 'application/json' },
  }))
  await assert.rejects(api.http('GET', '/schedule/', null), SyntaxError)
})

test('preserves the network failure message', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => { throw new TypeError('Network error') })
  await assert.rejects(api.http('GET', '/schedule/', null), {
    message: 'HTTP error 0: network failure',
  })
})


test('returns no content for a successful deletion', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response(null, { status: 204 }))
  assert.equal(await api.http('DELETE', '/schedule/1/', null), undefined)
})

test('preserves existing error messages for callers outside shifts', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response('<h1>Forbidden</h1>', {
    status: 403,
    headers: { 'Content-Type': 'text/html' },
  }))
  await assert.rejects(api.http('GET', '/schedule/', null), {
    message: 'HTTP error 403: server returned non-JSON response',
  })
})

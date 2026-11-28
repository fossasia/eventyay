import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./teamshifts-adapter', () => ({
  resolveMode: () => 'shifts',
  getApiConfig: () => ({ baseUrl: '/api/', endpoints: { talks: 'talks/' } }),
  getCsrfToken: () => 'token',
  getClaimedShiftIds: () => new Set<number>(),
  getClaimBaseUrl: () => '',
}))

import api, { HttpError, isNotFound, isPermissionDenied } from './api'

function jsonResponse(status: number, body: string): Response {
  return new Response(body, { status, headers: { 'Content-Type': 'application/json' } })
}

const emptySchedule = JSON.stringify({
  version: null,
  event_start: '2026-12-01',
  event_end: '2026-12-02',
  timezone: 'UTC',
})

beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => {})
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('error helpers', () => {
  it('tells a permission denial apart from a missing object', () => {
    expect(isPermissionDenied(new HttpError(403, 'denied'))).toBe(true)
    expect(isNotFound(new HttpError(403, 'denied'))).toBe(false)
    expect(isNotFound(new HttpError(404, 'gone'))).toBe(true)
    expect(isPermissionDenied(new Error('other'))).toBe(false)
  })
})

describe('http', () => {
  it('keeps the 403 status from a JSON error response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(403, '{"detail": "no"}')))

    const error = await api.http('DELETE', '/api/talks/1/', null).catch((e) => e)

    expect(isPermissionDenied(error)).toBe(true)
  })

  it('keeps the status when an error body is not valid JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(403, '<html>Forbidden</html>')))

    const error = await api.http('DELETE', '/api/talks/1/', null).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(HttpError)
    expect((error as HttpError).status).toBe(403)
  })

  it('still throws the parse error for a successful response with a broken body', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(200, '{broken')))

    const error = await api.http('GET', '/api/talks/', null).catch((e) => e)

    expect(error).toBeInstanceOf(SyntaxError)
  })
})

describe('fetchTalks', () => {
  function requestedUrl(fetchMock: ReturnType<typeof vi.fn>): string {
    return fetchMock.mock.calls[0][0] as string
  }

  beforeEach(() => {
    vi.stubGlobal('window', { location: { search: '?since=2026-12-01T10:00&mode=shifts', pathname: '/' } })
  })

  it('keeps the page filters for a normal load', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, emptySchedule))
    vi.stubGlobal('fetch', fetchMock)

    await api.fetchTalks()

    expect(requestedUrl(fetchMock)).toContain('since=')
    expect(requestedUrl(fetchMock)).toContain('mode=shifts')
  })

  it('drops the page since filter when the full schedule is asked for', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, emptySchedule))
    vi.stubGlobal('fetch', fetchMock)

    await api.fetchTalks({ full: true })

    expect(requestedUrl(fetchMock)).not.toContain('since=')
    expect(requestedUrl(fetchMock)).toContain('mode=shifts')
  })
})

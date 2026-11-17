import assert from 'node:assert/strict'
import { test } from 'node:test'
import { dayForHash, horizontalTabScrollDelta, isVerticallyScrollable, updateDayHash } from './dateNavigation.ts'

const days = ['2026-11-12', '2026-11-13', '2026-11-14'].map((date) => ({
  format: () => date,
}))

test('an empty hash selects the first day and known hashes select their date', () => {
  assert.equal(dayForHash(days, ''), days[0])
  assert.equal(dayForHash(days, '2026-11-14'), days[2])
  assert.equal(dayForHash(days, 'unknown'), undefined)
})

test('scroll date changes replace history while tab changes update the hash', () => {
  const calls = []
  const originalWindow = globalThis.window
  const location = { hash: '#2026-11-12', pathname: '/schedule/grid/', search: '?event=test' }
  globalThis.window = {
    location,
    history: {
      state: { retained: true },
      replaceState: (...args) => calls.push(['replace', ...args]),
    },
  }

  try {
    updateDayHash('2026-11-13', true)
    assert.deepEqual(calls, [['replace', { retained: true }, '', '/schedule/grid/?event=test#2026-11-13']])

    updateDayHash('2026-11-14', false)
    assert.equal(location.hash, '2026-11-14')
  } finally {
    globalThis.window = originalWindow
  }
})

test('window scrolling is selected when the schedule parent cannot scroll', () => {
  assert.equal(isVerticallyScrollable(500, 500, 'auto'), false)
  assert.equal(isVerticallyScrollable(700, 500, 'visible'), false)
  assert.equal(isVerticallyScrollable(700, 500, 'auto'), true)
  assert.equal(isVerticallyScrollable(700, 500, 'scroll'), true)
})

test('date tabs scroll horizontally in either direction without changing vertical position', () => {
  assert.equal(horizontalTabScrollDelta(100, 300, 80, 180), -20)
  assert.equal(horizontalTabScrollDelta(100, 300, 280, 320), 20)
  assert.equal(horizontalTabScrollDelta(100, 300, 120, 280), 0)
})

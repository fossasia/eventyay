import assert from 'node:assert/strict'
import test from 'node:test'
import { getDayAtScrollPosition, updateDayEndSpace } from './dayNavigation.js'

const days = ['2026-11-12', '2026-11-13', '2026-11-14']
const starts = days.map((day, index) => ({ day, top: 84 + index * 1004 }))
const at = scrollTop => getDayAtScrollPosition(starts.map(start => ({
	...start,
	top: start.top - scrollTop,
})), 90)

test('small scroll steps update the day in both directions', () => {
	const positions = [0, 500, 1000, 1500, 2100, 2500, 2100, 1500, 1000, 500, 0]
	assert.deepEqual(positions.map(at), [days[0], days[0], days[1], days[1], days[2], days[2], days[2], days[1], days[1], days[0], days[0]])
})

test('large scroll jumps do not require crossing an observed header', () => {
	assert.deepEqual([0, 2500, 500, 2000, 0].map(at), [days[0], days[2], days[0], days[1], days[0]])
})

test('scrolling back across a divider immediately restores the previous day', () => {
	assert.equal(at(1000), days[1])
	assert.equal(at(900), days[0])
	assert.equal(at(2100), days[2])
	assert.equal(at(1900), days[1])
})

test('date gaps use the actual preceding event day', () => {
	assert.equal(getDayAtScrollPosition([
		{ day: '2026-11-12', top: -200 },
		{ day: '2026-11-16', top: 200 },
	], 90), '2026-11-12')
})

test('the same day is selected inside an offset scroll container', () => {
	assert.equal(getDayAtScrollPosition(starts.map(start => ({ ...start, top: start.top + 300 - 1000 })), 390), days[1])
})

test('an empty schedule has no active day', () => {
	assert.equal(getDayAtScrollPosition([], 90), null)
})

test('a short last day can reach the toolbar without adding more space on repeat updates', () => {
	let padding = 0
	const element = {
		style: {
			getPropertyValue: () => `${padding}px`,
			setProperty: (name, value) => { padding = parseFloat(value) },
		},
		getBoundingClientRect: () => ({ bottom: 2200 + padding }),
	}
	const lastDay = { getBoundingClientRect: () => ({ top: 2000 }) }
	updateDayEndSpace(element, lastDay, 650, 90)
	assert.equal(padding, 360)
	updateDayEndSpace(element, lastDay, 650, 90)
	assert.equal(padding, 360)
	updateDayEndSpace(element, lastDay, 650, 90, false)
	assert.equal(padding, 0)
})

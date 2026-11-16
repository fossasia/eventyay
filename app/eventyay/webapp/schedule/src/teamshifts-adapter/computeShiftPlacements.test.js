/**
 * Checks how overlapping shifts in one room are split into cards on the schedule grid.
 * Run: node --test src/teamshifts-adapter/computeShiftPlacements.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { computeShiftColumnLayout, computeShiftPlacements } from './index.js'

const pad = n => String(n).padStart(2, '0')

// Just enough of a moment object for the placement code. Day 0 is 29 Nov 2026 (UTC).
function at (hours, minutes = 0, day = 0) {
	const date = new Date(Date.UTC(2026, 10, 29 + day, hours, minutes))
	return {
		valueOf: () => date.getTime(),
		diff: other => date.getTime() - other.valueOf(),
		isBefore: other => date.getTime() < other.valueOf(),
		format: () => `${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}-${pad(date.getUTCHours())}-${pad(date.getUTCMinutes())}`,
	}
}

const room = { id: 1 }

function shift (id, start, end, inRoom = room) {
	return { id, room: inRoom, start, end }
}

function placementsFor (sessions, rooms = [room]) {
	const layout = computeShiftColumnLayout(rooms, sessions)
	return Object.fromEntries(sessions.map(s => [s.id, computeShiftPlacements(s, sessions, layout)]))
}

const summary = placements => placements.map(p => `${p.gridRow} | ${p.gridColumn} | ${p.continuation ? 'continued' : 'main'}`)

test('splits the handover from the issue into full-width and half-width pieces', () => {
	const sessions = [
		shift('afternoon', at(18), at(23)),
		shift('evening', at(22, 30), at(2, 30, 1)),
	]
	const result = placementsFor(sessions)
	assert.deepEqual(summary(result.afternoon), [
		'slice-11-29-18-00 / slice-11-29-22-30 | 2 / 4 | main',
		'slice-11-29-22-30 / slice-11-29-23-00 | 2 / 3 | continued',
	])
	assert.deepEqual(summary(result.evening), [
		'slice-11-29-22-30 / slice-11-29-23-00 | 3 / 4 | continued',
		'slice-11-29-23-00 / slice-11-30-02-30 | 2 / 4 | main',
	])
})

test('a shift that overlaps nothing uses the whole room width in one piece', () => {
	const sessions = [
		shift('afternoon', at(18), at(23)),
		shift('evening', at(22, 30), at(2, 30, 1)),
		shift('morning', at(6, 0, 1), at(8, 0, 1)),
	]
	assert.deepEqual(summary(placementsFor(sessions).morning), ['slice-11-30-06-00 / slice-11-30-08-00 | 2 / 4 | main'])
})

test('shifts that only touch are not treated as overlapping', () => {
	const sessions = [shift('early', at(9), at(12)), shift('later', at(12), at(14))]
	const layout = computeShiftColumnLayout([room], sessions)
	assert.equal(layout.get(1).colSpan, 1)
	assert.equal(computeShiftPlacements(sessions[0], sessions, layout), null)
})

test('returns null for shifts without times or a room', () => {
	const sessions = [shift('a', at(9), at(12)), shift('b', at(10), at(11))]
	const layout = computeShiftColumnLayout([room], sessions)
	assert.equal(computeShiftPlacements({ id: 'x', room, start: null, end: at(1) }, sessions, layout), null)
	assert.equal(computeShiftPlacements({ id: 'y', room: null, start: at(1), end: at(2) }, sessions, layout), null)
})

test('other rooms do not affect the split', () => {
	const other = { id: 2 }
	const sessions = [
		shift('a', at(9), at(12)),
		shift('b', at(10), at(11)),
		shift('alone', at(9), at(12), other),
	]
	const layout = computeShiftColumnLayout([room, other], sessions)
	assert.equal(computeShiftPlacements(sessions[2], sessions, layout), null)
})

test('three overlapping shifts never share a column at the same time and every stretch is covered', () => {
	const sessions = [
		shift('a', at(9), at(12)),
		shift('b', at(10), at(11)),
		shift('c', at(10, 30), at(13)),
	]
	const layout = computeShiftColumnLayout([room], sessions)
	assert.equal(layout.get(1).colSpan, 3)
	const result = placementsFor(sessions)

	const pieces = sessions.flatMap(s => result[s.id].map(p => {
		const [from, to] = p.gridColumn.split(' / ').map(Number)
		return { id: s.id, from, to, start: p.segmentStart.valueOf(), end: p.segmentEnd.valueOf() }
	}))

	for (const a of pieces) {
		for (const b of pieces) {
			if (a === b || a.id === b.id) continue
			const timeOverlap = a.start < b.end && b.start < a.end
			const columnOverlap = a.from < b.to && b.from < a.to
			assert.ok(!(timeOverlap && columnOverlap), `${a.id} and ${b.id} overlap`)
		}
	}

	for (const s of sessions) {
		const own = result[s.id].map(p => [p.segmentStart.valueOf(), p.segmentEnd.valueOf()]).sort((x, y) => x[0] - y[0])
		assert.equal(own[0][0], s.start.valueOf())
		assert.equal(own[own.length - 1][1], s.end.valueOf())
		for (let i = 1; i < own.length; i++) assert.equal(own[i][0], own[i - 1][1])
		assert.equal(result[s.id].filter(p => !p.continuation).length, 1)
	}
})

/**
 * Checks that overlapping shifts split into per-segment placements so
 * non-overlapping time ranges use the full room width.
 * Run: node --test src/teamshifts-adapter/computeShiftSegments.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import moment from 'moment-timezone'
import { computeShiftColumnLayout, computeShiftSegments, mapGridColumnToChunk } from './index.js'

const ROOM = { id: 1, name: 'Main Auditorium' }
const OTHER_ROOM = { id: 2, name: 'Side Room' }

function shift (id, start, end, room = ROOM) {
	return {
		id,
		title: `Shift ${id}`,
		start: start ? moment.tz(start, 'YYYY-MM-DD HH:mm', 'UTC') : null,
		end: end ? moment.tz(end, 'YYYY-MM-DD HH:mm', 'UTC') : null,
		room,
		roles: [{ id: 1, capacity: 1, assigned: [] }],
	}
}

function layoutFor (sessions, rooms = [ROOM]) {
	return computeShiftColumnLayout(rooms, sessions)
}

test('issue repro: afternoon shift widens after the overlap ends', () => {
	const afternoon = shift('afternoon', '2026-11-14 18:00', '2026-11-14 23:00')
	const evening = shift('evening', '2026-11-14 22:30', '2026-11-15 02:30')
	const sessions = [afternoon, evening]
	const layout = layoutFor(sessions)

	const segments = computeShiftSegments(afternoon, sessions, layout)
	assert.equal(segments.length, 2)

	assert.equal(segments[0].fullWidth, true)
	assert.equal(segments[0].continuation, false)
	assert.equal(segments[0].gridRow, 'slice-11-14-18-00 / slice-11-14-22-30')
	assert.equal(segments[0].gridColumn, '2 / 4')

	assert.equal(segments[1].fullWidth, false)
	assert.equal(segments[1].track, 0)
	assert.equal(segments[1].continuation, true)
	assert.equal(segments[1].gridRow, 'slice-11-14-22-30 / slice-11-14-23-00')
	assert.equal(segments[1].gridColumn, '2 / 3')
})

test('issue repro: evening shift starts narrow and widens at 23:00', () => {
	const afternoon = shift('afternoon', '2026-11-14 18:00', '2026-11-14 23:00')
	const evening = shift('evening', '2026-11-14 22:30', '2026-11-15 02:30')
	const sessions = [afternoon, evening]
	const layout = layoutFor(sessions)

	const segments = computeShiftSegments(evening, sessions, layout)
	assert.equal(segments.length, 2)

	assert.equal(segments[0].fullWidth, false)
	assert.equal(segments[0].track, 1)
	assert.equal(segments[0].continuation, false)
	assert.equal(segments[0].gridRow, 'slice-11-14-22-30 / slice-11-14-23-00')
	assert.equal(segments[0].gridColumn, '3 / 4')

	assert.equal(segments[1].fullWidth, true)
	assert.equal(segments[1].continuation, true)
	assert.equal(segments[1].gridRow, 'slice-11-14-23-00 / slice-11-15-02-30')
	assert.equal(segments[1].gridColumn, '2 / 4')
})

test('a shift with no overlap is a single full-width segment', () => {
	const only = shift('only', '2026-11-14 18:00', '2026-11-14 23:00')
	const sessions = [only]
	const layout = layoutFor(sessions)

	const segments = computeShiftSegments(only, sessions, layout)
	assert.equal(segments.length, 1)
	assert.equal(segments[0].fullWidth, true)
	assert.equal(segments[0].continuation, false)
	assert.equal(segments[0].gridRow, 'slice-11-14-18-00 / slice-11-14-23-00')
	assert.equal(segments[0].gridColumn, '2 / 3')
})

test('back-to-back sessions do not count as overlapping', () => {
	const first = shift('first', '2026-11-14 18:00', '2026-11-14 22:30')
	const second = shift('second', '2026-11-14 22:30', '2026-11-15 02:30')
	const sessions = [first, second]
	const layout = layoutFor(sessions)

	for (const session of sessions) {
		const segments = computeShiftSegments(session, sessions, layout)
		assert.equal(segments.length, 1)
		assert.equal(segments[0].fullWidth, true)
		assert.equal(segments[0].continuation, false)
	}
})

test('a shift crossed by two short shifts widens between them', () => {
	const long = shift('long', '2026-11-14 18:00', '2026-11-14 23:00')
	const first = shift('first', '2026-11-14 19:00', '2026-11-14 20:00')
	const second = shift('second', '2026-11-14 20:30', '2026-11-14 21:00')
	const sessions = [long, first, second]
	const layout = layoutFor(sessions)

	const segments = computeShiftSegments(long, sessions, layout)
	assert.deepEqual(
		segments.map(s => [s.gridRow, s.gridColumn, s.fullWidth, s.continuation]),
		[
			['slice-11-14-18-00 / slice-11-14-19-00', '2 / 4', true, false],
			['slice-11-14-19-00 / slice-11-14-20-00', '2 / 3', false, true],
			['slice-11-14-20-00 / slice-11-14-20-30', '2 / 4', true, true],
			['slice-11-14-20-30 / slice-11-14-21-00', '2 / 3', false, true],
			['slice-11-14-21-00 / slice-11-14-23-00', '2 / 4', true, true],
		]
	)
})

test('a very short overlap still produces a narrow segment', () => {
	const long = shift('long', '2026-11-14 18:00', '2026-11-14 23:00')
	const short = shift('short', '2026-11-14 22:30', '2026-11-14 22:35')
	const sessions = [long, short]
	const layout = layoutFor(sessions)

	const segments = computeShiftSegments(long, sessions, layout)
	assert.equal(segments.length, 3)
	assert.equal(segments[1].gridRow, 'slice-11-14-22-30 / slice-11-14-22-35')
	assert.equal(segments[1].fullWidth, false)
	assert.equal(segments[2].fullWidth, true)
})

test('sessions in other rooms do not affect the segments', () => {
	const main = shift('main', '2026-11-14 18:00', '2026-11-14 23:00')
	const other = shift('other', '2026-11-14 19:00', '2026-11-14 20:00', OTHER_ROOM)
	const sessions = [main, other]
	const layout = layoutFor(sessions, [ROOM, OTHER_ROOM])

	const segments = computeShiftSegments(main, sessions, layout)
	assert.equal(segments.length, 1)
	assert.equal(segments[0].fullWidth, true)
	assert.equal(segments[0].gridColumn, '2 / 3')
})

test('a shift crossed by many short shifts alternates narrow and wide', () => {
	const long = shift('long', '2026-11-14 18:00', '2026-11-14 23:00')
	const first = shift('first', '2026-11-14 19:00', '2026-11-14 19:30')
	const second = shift('second', '2026-11-14 20:00', '2026-11-14 20:30')
	const third = shift('third', '2026-11-14 21:00', '2026-11-14 21:30')
	const sessions = [long, first, second, third]
	const layout = layoutFor(sessions)

	const segments = computeShiftSegments(long, sessions, layout)
	assert.deepEqual(
		segments.map(s => [s.gridRow, s.gridColumn, s.fullWidth, s.continuation]),
		[
			['slice-11-14-18-00 / slice-11-14-19-00', '2 / 4', true, false],
			['slice-11-14-19-00 / slice-11-14-19-30', '2 / 3', false, true],
			['slice-11-14-19-30 / slice-11-14-20-00', '2 / 4', true, true],
			['slice-11-14-20-00 / slice-11-14-20-30', '2 / 3', false, true],
			['slice-11-14-20-30 / slice-11-14-21-00', '2 / 4', true, true],
			['slice-11-14-21-00 / slice-11-14-21-30', '2 / 3', false, true],
			['slice-11-14-21-30 / slice-11-14-23-00', '2 / 4', true, true],
		]
	)
})

test('back-to-back crossing shifts keep the overlap covered across the join', () => {
	const long = shift('long', '2026-11-14 18:00', '2026-11-14 23:00')
	const first = shift('first', '2026-11-14 19:00', '2026-11-14 20:00')
	const second = shift('second', '2026-11-14 20:00', '2026-11-14 21:00')
	const sessions = [long, first, second]
	const layout = layoutFor(sessions)

	const segments = computeShiftSegments(long, sessions, layout)
	assert.deepEqual(
		segments.map(s => [s.gridRow, s.gridColumn, s.fullWidth, s.continuation]),
		[
			['slice-11-14-18-00 / slice-11-14-19-00', '2 / 4', true, false],
			['slice-11-14-19-00 / slice-11-14-21-00', '2 / 3', false, true],
			['slice-11-14-21-00 / slice-11-14-23-00', '2 / 4', true, true],
		]
	)
})

test('print chunk mapping keeps segment columns apart', () => {
	// Room A spans columns 2-4 in the full grid, room B is column 4-5.
	const layoutA = { colStart: 2, colSpan: 2 }
	const layoutB = { colStart: 4, colSpan: 1 }
	const chunkAB = [layoutA, layoutB]

	// Full-width and narrow segments in the first room keep their columns.
	assert.equal(mapGridColumnToChunk('2 / 4', layoutA, chunkAB, 0), '2 / 4')
	assert.equal(mapGridColumnToChunk('2 / 3', layoutA, chunkAB, 0), '2 / 3')
	assert.equal(mapGridColumnToChunk('3 / 4', layoutA, chunkAB, 0), '3 / 4')

	// The second room in the chunk starts after room A's span.
	assert.equal(mapGridColumnToChunk('4 / 5', layoutB, chunkAB, 1), '4 / 5')

	// A chunk holding only room B renumbers it to start at column 2.
	assert.equal(mapGridColumnToChunk('4 / 5', layoutB, [layoutB], 0), '2 / 3')

	// Bad input maps to nothing instead of a wrong column.
	assert.equal(mapGridColumnToChunk('bogus', layoutA, chunkAB, 0), null)
	assert.equal(mapGridColumnToChunk('2 / 4', null, chunkAB, 0), null)
	assert.equal(mapGridColumnToChunk('2 / 4', layoutA, chunkAB, -1), null)
})

test('returns null without start, end, room, or layout entry', () => {
	const full = shift('full', '2026-11-14 18:00', '2026-11-14 23:00')
	const sessions = [full]
	const layout = layoutFor(sessions)

	assert.equal(computeShiftSegments(shift('no-start', null, '2026-11-14 23:00'), sessions, layout), null)
	assert.equal(computeShiftSegments(shift('no-end', '2026-11-14 18:00', null), sessions, layout), null)
	assert.equal(computeShiftSegments(shift('no-room', '2026-11-14 18:00', '2026-11-14 23:00', null), sessions, layout), null)
	assert.equal(computeShiftSegments(full, sessions, new Map()), null)
	assert.equal(computeShiftSegments(full, sessions, null), null)
})

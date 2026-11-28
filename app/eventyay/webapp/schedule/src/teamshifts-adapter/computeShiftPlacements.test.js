/**
 * Checks how overlapping shifts in one room are split into cards on the schedule grid.
 * Run: node --test src/teamshifts-adapter/computeShiftPlacements.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { computeShiftColumnLayout, computeShiftPlacements, computeShiftOverlapPlacement, placementGridItems } from './index.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

const pad = n => String(n).padStart(2, '0')

// Just enough of a moment object for the placement code. Day 0 is 29 Nov 2026 (UTC).
function at (hours, minutes = 0, day = 0) {
	const date = new Date(Date.UTC(2026, 10, 29 + day, hours, minutes))
	return {
		valueOf: () => date.getTime(),
		diff: other => date.getTime() - other.valueOf(),
		isBefore: other => date.getTime() < other.valueOf(),
		format: (pattern) => {
			assert.equal(pattern, 'MM-DD-HH-mm')
			return `${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}-${pad(date.getUTCHours())}-${pad(date.getUTCMinutes())}`
		},
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

test('initial segment of long shift remains main when substantial', () => {
	const sessions = [
		shift('longShift', at(18), at(23, 0, 1)),
		shift('shortOverlap', at(22, 30), at(2, 30, 1)),
	]
	const result = placementsFor(sessions)
	assert.deepEqual(summary(result.longShift), [
		'slice-11-29-18-00 / slice-11-29-22-30 | 2 / 4 | main',
		'slice-11-29-22-30 / slice-11-30-02-30 | 2 / 3 | continued',
		'slice-11-30-02-30 / slice-11-30-23-00 | 2 / 4 | continued',
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

// Parses "from / to" and fails the test on anything that is not a valid, non-empty column range.
function columnRange (placement) {
	assert.match(placement.gridColumn, /^\d+ \/ \d+$/, `malformed gridColumn: ${placement.gridColumn}`)
	const [from, to] = placement.gridColumn.split(' / ').map(Number)
	assert.ok(Number.isFinite(from) && Number.isFinite(to), `non-finite column in ${placement.gridColumn}`)
	assert.ok(from >= 1 && from < to, `empty or reversed column range ${placement.gridColumn}`)
	return [from, to]
}

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

test('shifts in another room, even a busy one, leave the split of this room unchanged', () => {
	const other = { id: 2 }
	const inRoom = [shift('a', at(9), at(12)), shift('b', at(10), at(11))]
	const before = placementsFor(inRoom, [room])

	// A second room with its own overlap that runs during the same hours.
	const busyElsewhere = [
		shift('x', at(9), at(12), other),
		shift('y', at(9, 30), at(11, 30), other),
		shift('z', at(10), at(11), other),
	]
	const after = placementsFor([...inRoom, ...busyElsewhere], [room, other])

	assert.deepEqual(summary(after.a), summary(before.a))
	assert.deepEqual(summary(after.b), summary(before.b))
	// The other room is laid out on its own columns, to the right of this room.
	for (const s of busyElsewhere) {
		for (const p of after[s.id]) assert.ok(columnRange(p)[0] >= 4, `${s.id} left its room: ${p.gridColumn}`)
	}
})

test('when the first shift ends, the ones still running fill the room with no blank column', () => {
	// a ends early. b and c keep running, so column 0 would be empty if they kept their old tracks.
	const sessions = [
		shift('a', at(9), at(10)),
		shift('b', at(9), at(13)),
		shift('c', at(9), at(13)),
	]
	const layout = computeShiftColumnLayout([room], sessions)
	const { colStart, colSpan } = layout.get(1)
	assert.equal(colSpan, 3)
	const result = placementsFor(sessions)
	const pieces = sessions.flatMap(s => result[s.id].map(p => {
		const [from, to] = columnRange(p)
		return { id: s.id, from, to, start: p.segmentStart.valueOf(), end: p.segmentEnd.valueOf() }
	}))

	const edges = [...new Set(pieces.flatMap(p => [p.start, p.end]))].sort((x, y) => x - y)
	for (let i = 0; i < edges.length - 1; i++) {
		const mid = (edges[i] + edges[i + 1]) / 2
		const covered = new Array(colSpan).fill(0)
		for (const p of pieces) {
			if (p.start <= mid && mid < p.end) for (let col = p.from; col < p.to; col++) covered[col - colStart]++
		}
		assert.deepEqual(covered, new Array(colSpan).fill(1), `columns not filled exactly once at ${new Date(mid).toISOString()}`)
	}
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
		const [from, to] = columnRange(p)
		return { id: s.id, from, to, start: p.segmentStart.valueOf(), end: p.segmentEnd.valueOf() }
	}))
	assert.ok(pieces.length >= sessions.length, 'every shift should produce at least one piece')

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

test('grid items carry the continuation flags, a unique key and the grid placement of each piece', () => {
	const sessions = [
		shift('afternoon', at(18), at(23)),
		shift('evening', at(22, 30), at(2, 30, 1)),
	]
	const placements = placementsFor(sessions).afternoon
	const items = placementGridItems('afternoon', sessions[0], placements)

	assert.equal(items.length, placements.length)
	assert.deepEqual(items.map(item => item.key), ['afternoon-0', 'afternoon-1'])
	assert.deepEqual(items.map(item => item.props.continuation), [false, true])
	assert.deepEqual(items.map(item => item.props.continuationBefore), [false, true])
	assert.deepEqual(items.map(item => item.props.continuationAfter), [true, false])
	assert.deepEqual(items.map(item => item.style), [
		{ 'grid-row': 'slice-11-29-18-00 / slice-11-29-22-30', 'grid-column': '2 / 4' },
		{ 'grid-row': 'slice-11-29-22-30 / slice-11-29-23-00', 'grid-column': '2 / 3' },
	])
	assert.ok(items.every(item => item.session === sessions[0]))
	assert.equal(new Set(items.map(item => item.key)).size, items.length)
})

test('computeShiftOverlapPlacement preserves legacy whole-shift single placement for existing callers', () => {
	const sessions = [
		shift('afternoon', at(18), at(23)),
		shift('evening', at(22, 30), at(2, 30, 1)),
	]
	const layout = computeShiftColumnLayout([room], sessions)
	const legacyPlacement = computeShiftOverlapPlacement(sessions[0], sessions, layout)
	assert.deepEqual(legacyPlacement, {
		gridRow: 'slice-11-29-18-00 / slice-11-29-23-00',
		gridColumn: '2 / 3',
	})
})

test('continuation margin overrides are defined for all densities and print styles without !important', () => {
	const gridSchedulePath = path.resolve(__dirname, '../components/GridSchedule.vue')
	const content = fs.readFileSync(gridSchedulePath, 'utf-8')
	// Verify .is-shift-mode overrides continuation margins for default, density-compact, and density-comfortable
	assert.match(content, /\.c-grid-schedule\.is-shift-mode[\s\S]*?&, &\.density-compact, &\.density-comfortable[\s\S]*?margin-bottom: 0[\s\S]*?margin-top: 0/)
	// Verify print grid styles also suppress continuation margins
	assert.match(content, /\.print-grids[\s\S]*?\.c-linear-schedule-session[\s\S]*?margin-bottom: 0[\s\S]*?margin-top: 0/)
	// Verify no !important tag is used for these overrides (satisfies Rule 1)
	const continuationBlock = content.match(/\.c-grid-schedule\.is-shift-mode[\s\S]*?margin-top: 0/)?.[0]
	assert.ok(continuationBlock && !continuationBlock.includes('!important'))
})

test('hover state preserves seamless border removal at continuation seams', () => {
	const sessionVuePath = path.resolve(__dirname, 'Session.vue')
	const content = fs.readFileSync(sessionVuePath, 'utf-8')
	// Verify hover rule suppresses border-bottom and border-top on continuation pieces
	assert.match(content, /&:hover[\s\S]*?has-continuation-after[\s\S]*?border-bottom: none/)
	assert.match(content, /&:hover[\s\S]*?has-continuation-before[\s\S]*?border-top: none/)
})

test('idless breaks do not split overlapping shifts into subcolumns', () => {
	const realShift = shift('shift-1', at(10), at(14))
	const idlessBreak = { room, start: at(12), end: at(13) }
	const sessions = [realShift, idlessBreak]

	const layout = computeShiftColumnLayout([room], sessions)
	assert.equal(layout.get(room.id).colSpan, 1)

	const placements = computeShiftPlacements(realShift, sessions, layout)
	assert.equal(placements, null)
})

test('fallback print chunk styling uses expanded room layout coordinates and spans totalCols for breaks', () => {
	const gridSchedulePath = path.resolve(__dirname, '../components/GridSchedule.vue')
	const content = fs.readFileSync(gridSchedulePath, 'utf-8')
	assert.match(content, /getChunkSessionStyle\s*\(session,\s*chunkRooms\)\s*\{[\s\S]*?if\s*\(this\.isShiftMode\)[\s\S]*?\$\{l\.colStart\}\s*\/\s*\$\{l\.colStart\s*\+\s*l\.colSpan\}[\s\S]*?2\s*\/\s*\$\{totalCols\s*\+\s*2\}/)
})

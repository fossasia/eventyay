/**
 * Checks how far a shift card's title and time are moved down to stay in view.
 * Run: node --test src/teamshifts-adapter/stickyLabels.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { computeStickyOffset, shouldHideContinuation, registerStickyLabels } from './stickyLabels.js'

// A 600px card whose title is 24px tall and sits 9px below the card's top edge.
const card = { cardHeight: 600, height: 24 }
const offsetAt = (cardTop, stickyBottom = 70) => computeStickyOffset({
	...card, stickyBottom, cardTop, naturalTop: cardTop + 9,
})

test('does not move while the card top is below the rooms bar', () => {
	assert.equal(offsetAt(300), 0)
	assert.equal(offsetAt(61), 0) // title top is exactly at the rooms bar
})

test('moves down by the amount the card top has scrolled past the rooms bar', () => {
	// card top 100px above the bar: the title's natural top is 91px above it, so it needs 161px.
	assert.equal(offsetAt(-30), 70 - (-30 + 9))
	assert.equal(offsetAt(-200), 70 - (-200 + 9))
})

test('keeps the title at the rooms bar, never above it', () => {
	for (const cardTop of [60, 0, -100, -400]) {
		const offset = offsetAt(cardTop)
		assert.equal(cardTop + 9 + offset, 70, `title not at the bar for cardTop=${cardTop}`)
	}
})

test('stops at the bottom of the card so the title never leaves it', () => {
	// Only 20px of the card is left below the bar: the title can move down until its bottom meets the card's bottom.
	const cardTop = 70 - 600 + 20
	const offset = offsetAt(cardTop)
	assert.equal(cardTop + 9 + offset + card.height, cardTop + card.cardHeight)
	// Scrolled further, there is no more room, and the offset stays where it ended.
	assert.equal(offsetAt(cardTop - 500), 600 - 9 - 24)
})

test('never returns a negative or non-finite offset', () => {
	assert.equal(offsetAt(5000), 0)
	assert.equal(computeStickyOffset({ stickyBottom: NaN, cardTop: 0, cardHeight: 10, naturalTop: 0, height: 5 }), 0)
	// A label taller than its card has no room to move.
	assert.equal(computeStickyOffset({ stickyBottom: 100, cardTop: 0, cardHeight: 20, naturalTop: 0, height: 40 }), 0)
})

test('shouldHideContinuation returns false for primary non-continuation cards', () => {
	const card = { classList: { contains: () => false } }
	assert.equal(shouldHideContinuation(card, 70), false)
})

test('shouldHideContinuation hides continuation piece while previous piece is on screen', () => {
	const prevPiece = {
		getBoundingClientRect: () => ({ bottom: 250 }),
	}
	const continuationCard = {
		classList: { contains: (cls) => cls === 'has-continuation-before' },
		dataset: { shiftId: '42' },
		closest: () => ({
			querySelectorAll: () => [prevPiece, continuationCard],
		}),
	}
	assert.equal(shouldHideContinuation(continuationCard, 70), true)
})

test('shouldHideContinuation reveals continuation piece once previous piece scrolls off', () => {
	const prevPiece = {
		getBoundingClientRect: () => ({ bottom: 50 }), // Scrolled past stickyBottom (70)
	}
	const continuationCard = {
		classList: { contains: (cls) => cls === 'has-continuation-before' },
		dataset: { shiftId: '42' },
		closest: () => ({
			querySelectorAll: () => [prevPiece, continuationCard],
		}),
	}
	assert.equal(shouldHideContinuation(continuationCard, 70), false)
})

test('registerStickyLabels ignores cards outside grid schedule or inside print container', () => {
	const linearCard = { closest: () => null }
	const stopLinear = registerStickyLabels(linearCard)
	assert.equal(typeof stopLinear, 'function')
	stopLinear()

	const printCard = {
		closest: (sel) => sel === '.c-grid-schedule' ? { querySelector: () => ({}) } : (sel === '.print-grids' || sel === '.is-print') ? {} : null,
	}
	const stopPrint = registerStickyLabels(printCard)
	assert.equal(typeof stopPrint, 'function')
	stopPrint()
})

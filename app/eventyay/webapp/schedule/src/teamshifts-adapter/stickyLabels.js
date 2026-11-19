/**
 * Keeps a shift card's title and start time in view while a long card is scrolled.
 *
 * CSS `position: sticky` cannot do this here. The shift cards sit inside `.grid-viewport`, which has
 * `overflow-x: auto` and so is a scroll container, and sticky follows that container instead of the page.
 * So the offset is worked out from the real position of the card on screen and applied as a transform.
 */

/**
 * How far to move an element down so its top sits at `stickyBottom`, without leaving its card.
 *
 * All values are viewport coordinates in pixels. `naturalTop` is where the element would be with no offset.
 * The result is never negative and never moves the element's bottom past the card's bottom.
 */
export function computeStickyOffset ({ stickyBottom, cardTop, cardHeight, naturalTop, height }) {
	const wanted = stickyBottom - naturalTop
	if (!(wanted > 0)) return 0
	const room = (cardTop + cardHeight) - (naturalTop + height)
	return Math.max(0, Math.min(wanted, room))
}

const LABEL_SELECTORS = ['.time-box .start', '.info .title-row']

// Each registered card, with the grid it belongs to (found once, when it registers).
const entries = new Map()
const applied = new WeakMap()
let frame = 0
let listening = false

function setOffset (el, offset) {
	const rounded = Math.round(offset)
	if ((applied.get(el) || 0) === rounded) return
	applied.set(el, rounded)
	el.style.transform = rounded ? `translateY(${rounded}px)` : ''
}

function update () {
	frame = 0
	const viewportHeight = window.innerHeight || document.documentElement.clientHeight
	const viewportWidth = window.innerWidth || document.documentElement.clientWidth

	// Read phase: measure everything before changing anything, so no write below can force a new layout
	// in the middle of the reads.
	const stickyBottoms = new Map()
	const changes = []
	for (const [card, grid] of entries) {
		let stickyBottom = stickyBottoms.get(grid)
		if (stickyBottom === undefined) {
			const header = grid ? grid.querySelector('.sticky-header') : null
			stickyBottom = header ? header.getBoundingClientRect().bottom : 0
			stickyBottoms.set(grid, stickyBottom)
		}
		const cardRect = card.getBoundingClientRect()
		const onScreen = cardRect.bottom > stickyBottom && cardRect.top < viewportHeight &&
			cardRect.right > 0 && cardRect.left < viewportWidth
		for (const selector of LABEL_SELECTORS) {
			const el = card.querySelector(selector)
			if (!el) continue
			if (!onScreen) {
				changes.push([el, 0])
				continue
			}
			const rect = el.getBoundingClientRect()
			changes.push([el, computeStickyOffset({
				stickyBottom,
				cardTop: cardRect.top,
				cardHeight: cardRect.height,
				naturalTop: rect.top - (applied.get(el) || 0),
				height: rect.height,
			})])
		}
	}

	// Write phase.
	for (const [el, offset] of changes) setOffset(el, offset)
}

function schedule () {
	if (!frame) frame = requestAnimationFrame(update)
}

/**
 * Recomputes every label offset now. Call it when the layout changes without a scroll or window resize,
 * for example when the grid rows or the rooms bar change size.
 */
export function refreshStickyLabels () {
	if (entries.size) schedule()
}

/**
 * Starts keeping the labels of one shift card in view. Returns a function that stops it.
 * One shared, throttled scroll listener serves every card.
 */
export function registerStickyLabels (card) {
	entries.set(card, card.closest('.c-grid-schedule'))
	if (!listening) {
		// Capture, because scroll events do not bubble and the page may scroll inside any ancestor.
		window.addEventListener('scroll', schedule, { passive: true, capture: true })
		window.addEventListener('resize', schedule, { passive: true })
		listening = true
	}
	schedule()
	return () => {
		entries.delete(card)
		for (const selector of LABEL_SELECTORS) {
			const el = card.querySelector(selector)
			if (el) setOffset(el, 0)
		}
		if (!entries.size && listening) {
			window.removeEventListener('scroll', schedule, { capture: true })
			window.removeEventListener('resize', schedule)
			listening = false
			if (frame) {
				cancelAnimationFrame(frame)
				frame = 0
			}
		}
	}
}

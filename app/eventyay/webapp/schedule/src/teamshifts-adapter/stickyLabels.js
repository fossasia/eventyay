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

const entries = new Set()
const applied = new WeakMap()
let frame = 0
let listening = false

function stickyBottomFor (card) {
	const header = card.closest('.c-grid-schedule')?.querySelector('.sticky-header')
	return header ? header.getBoundingClientRect().bottom : 0
}

function setOffset (el, offset) {
	const rounded = Math.round(offset)
	if ((applied.get(el) || 0) === rounded) return
	applied.set(el, rounded)
	el.style.transform = rounded ? `translateY(${rounded}px)` : ''
}

function update () {
	frame = 0
	const viewportHeight = window.innerHeight || document.documentElement.clientHeight
	for (const card of entries) {
		const cardRect = card.getBoundingClientRect()
		const stickyBottom = stickyBottomFor(card)
		const onScreen = cardRect.bottom > stickyBottom && cardRect.top < viewportHeight
		for (const selector of LABEL_SELECTORS) {
			const el = card.querySelector(selector)
			if (!el) continue
			if (!onScreen) {
				setOffset(el, 0)
				continue
			}
			const rect = el.getBoundingClientRect()
			setOffset(el, computeStickyOffset({
				stickyBottom,
				cardTop: cardRect.top,
				cardHeight: cardRect.height,
				naturalTop: rect.top - (applied.get(el) || 0),
				height: rect.height,
			}))
		}
	}
}

function schedule () {
	if (!frame) frame = requestAnimationFrame(update)
}

/**
 * Starts keeping the labels of one shift card in view. Returns a function that stops it.
 * One shared, throttled scroll listener serves every card.
 */
export function registerStickyLabels (card) {
	entries.add(card)
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

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
 * The result is never negative and never moves the element's bottom past the shift's bottom.
 */
export function computeStickyOffset ({ stickyBottom, cardTop, cardHeight, naturalTop, height }) {
	const wanted = stickyBottom - naturalTop
	if (!(wanted > 0)) return 0
	const room = (cardTop + cardHeight) - (naturalTop + height)
	return Math.max(0, Math.min(wanted, room))
}

function getLabelElements (card) {
	const elements = []
	const start = card.querySelector('.time-box .start')
	if (start) elements.push(start)
	const title = card.querySelector('.info .title-range-wrapper') || card.querySelector('.info .title-row')
	if (title) elements.push(title)
	return elements
}

const entries = new Set()
const applied = new WeakMap()
let listening = false
let updateScheduled = false

function scheduleUpdate () {
	if (updateScheduled) return
	updateScheduled = true
	const run = () => {
		updateScheduled = false
		if (entries.size) update()
	}
	if (typeof queueMicrotask === 'function') {
		queueMicrotask(run)
	} else {
		setTimeout(run, 0)
	}
}

function stickyBottomFor (card) {
	const header = card.closest?.('.c-grid-schedule')?.querySelector('.sticky-header')
	return header ? header.getBoundingClientRect().bottom : 0
}

function setOffset (el, offset) {
	const rounded = Math.round(offset)
	if ((applied.get(el) || 0) === rounded) return
	applied.set(el, rounded)
	el.style.transform = rounded ? `translate3d(0, ${rounded}px, 0)` : ''
}

export function shouldHideContinuation (card, stickyBottom) {
	if (!card?.classList?.contains('has-continuation-before')) return false
	const shiftId = card.dataset?.shiftId
	const grid = card.closest ? card.closest('.grid') : null
	const pieces = grid && shiftId ? Array.from(grid.querySelectorAll(`.is-shift-session[data-shift-id="${shiftId}"]`)) : []
	const myIndex = pieces.indexOf(card)
	const prevPiece = myIndex > 0 ? pieces[myIndex - 1] : null
	if (prevPiece && prevPiece.getBoundingClientRect().bottom > stickyBottom) {
		return true
	}
	return false
}

function update () {
	const viewportHeight = window.innerHeight || document.documentElement.clientHeight
	const updates = []
	for (const card of entries) {
		const cardRect = card.getBoundingClientRect()
		const stickyBottom = stickyBottomFor(card)

		if (shouldHideContinuation(card, stickyBottom)) {
			card.classList.add('shift-continuation-hidden')
			for (const el of getLabelElements(card)) {
				updates.push([el, 0])
			}
			continue
		} else if (card.classList.contains('shift-continuation-hidden')) {
			card.classList.remove('shift-continuation-hidden')
		}

		const onScreen = cardRect.bottom > stickyBottom && cardRect.top < viewportHeight
		if (!onScreen) {
			for (const el of getLabelElements(card)) {
				if (applied.get(el)) {
					updates.push([el, 0])
				}
			}
			continue
		}
		for (const el of getLabelElements(card)) {
			const rect = el.getBoundingClientRect()
			updates.push([el, computeStickyOffset({
				stickyBottom,
				cardTop: cardRect.top,
				cardHeight: cardRect.height,
				naturalTop: rect.top - (applied.get(el) || 0),
				height: rect.height,
			})])
		}
	}
	for (const [el, offset] of updates) {
		setOffset(el, offset)
	}
}

/**
 * Starts keeping the labels of one shift card in view. Returns a function that stops it.
 * One shared, synchronous scroll listener serves every card without animation frame lag.
 */
export function registerStickyLabels (card) {
	const grid = card?.closest?.('.c-grid-schedule')
	if (!grid || !grid.querySelector('.sticky-header') || card.closest?.('.is-print')) {
		return () => {}
	}
	entries.add(card)
	if (!listening) {
		window.addEventListener('scroll', update, { passive: true, capture: true })
		window.addEventListener('resize', update, { passive: true })
		listening = true
	}
	scheduleUpdate()
	return () => {
		entries.delete(card)
		for (const el of getLabelElements(card)) {
			setOffset(el, 0)
		}
		card.classList.remove('shift-continuation-hidden')
		if (!entries.size && listening) {
			window.removeEventListener('scroll', update, { capture: true })
			window.removeEventListener('resize', update)
			listening = false
		}
	}
}

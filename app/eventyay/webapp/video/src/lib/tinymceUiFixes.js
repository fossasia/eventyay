function dispatchEscape(target) {
	try {
		const eventInit = {
			key: 'Escape',
			code: 'Escape',
			keyCode: 27,
			which: 27,
			bubbles: true,
			cancelable: true,
		}
		target.dispatchEvent(new KeyboardEvent('keydown', eventInit))
		target.dispatchEvent(new KeyboardEvent('keyup', eventInit))
	} catch {
		// Best-effort only.
	}
}

function hasOpenTinymceUi() {
	return Boolean(document.querySelector('.tox-tinymce-aux'))
}

function closeTinymceUi() {
	if (!hasOpenTinymceUi()) return
	const activeElement = document.activeElement
	if (activeElement && activeElement !== document.body) {
		dispatchEscape(activeElement)
	}
	dispatchEscape(document)
	window.dispatchEvent(new Event('resize'))
}

let scheduledScrollClose = false
function scheduleCloseOnScroll() {
	if (scheduledScrollClose) return
	scheduledScrollClose = true
	window.requestAnimationFrame(() => {
		scheduledScrollClose = false
		closeTinymceUi()
	})
}

// Close on any scroll, including scrollable containers (scroll doesn't bubble, but it can be captured).
document.addEventListener('scroll', scheduleCloseOnScroll, { passive: true, capture: true })

// Ensure only one TinyMCE dropdown/popover at a time.
document.addEventListener(
	'pointerdown',
	(event) => {
		const target = event.target
		if (!(target instanceof Element)) return
		if (target.closest('.tox-tinymce-aux')) return
		if (target.closest('.tox')) closeTinymceUi()
	},
	{ capture: true }
)

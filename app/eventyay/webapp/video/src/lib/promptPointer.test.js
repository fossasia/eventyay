/**
 * Backdrop press tracking for the shared Prompt dialog.
 * Run: node --test src/lib/promptPointer.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { createBackdropPressTracker } from './promptPointer.js'

// Browsers reuse the same pointerId for every mouse press, which is why the
// tracker cannot rely on the id alone to tell separate presses apart.
const MOUSE = 1
const TOUCH = 65537

test('a press that starts inside the dialog never closes it', () => {
	const tracker = createBackdropPressTracker()
	tracker.press(false, MOUSE)
	assert.equal(tracker.release(true, MOUSE), false)
})

test('a backdrop press whose pointerup was missed does not close on a later inner press', () => {
	const tracker = createBackdropPressTracker()
	tracker.press(true, MOUSE) // pressed on the backdrop, released outside the window
	// the pointerup never reaches the overlay, so nothing is released here
	tracker.press(false, MOUSE) // pressed inside the dialog (seen in the capture phase)
	assert.equal(tracker.release(true, MOUSE), false)
})

test('pressing and releasing on the backdrop closes the dialog', () => {
	const tracker = createBackdropPressTracker()
	tracker.press(true, MOUSE)
	assert.equal(tracker.release(true, MOUSE), true)
})

test('releasing over the dialog does not close it', () => {
	const tracker = createBackdropPressTracker()
	tracker.press(true, MOUSE)
	assert.equal(tracker.release(false, MOUSE), false)
})

test('another pointer cannot finish a tracked backdrop press', () => {
	const tracker = createBackdropPressTracker()
	tracker.press(true, MOUSE)
	tracker.press(false, TOUCH) // a second finger inside the dialog
	assert.equal(tracker.release(true, TOUCH), false)
})

test('a cancelled press is not reused by the next release', () => {
	const tracker = createBackdropPressTracker()
	tracker.press(true, MOUSE)
	tracker.cancel(MOUSE)
	assert.equal(tracker.release(true, MOUSE), false)
})

test('there is nothing to release without a tracked press', () => {
	const tracker = createBackdropPressTracker()
	assert.equal(tracker.backdropPointerId, null)
	assert.equal(tracker.release(true, MOUSE), false)
	assert.equal(tracker.backdropPointerId, null)
})

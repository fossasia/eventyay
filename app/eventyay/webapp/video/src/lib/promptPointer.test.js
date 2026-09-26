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
const TOUCH_2 = 65538

test('a press that starts inside the dialog never closes it', () => {
	const tracker = createBackdropPressTracker()
	tracker.press(false, MOUSE)
	assert.equal(tracker.release(true, MOUSE), false)
})

test('a backdrop press whose pointerup was missed does not close on a later inner press with the same pointerId', () => {
	const tracker = createBackdropPressTracker()
	tracker.press(true, MOUSE) // pressed on the backdrop, released outside the window
	// the pointerup never reaches the overlay, so nothing is released here
	tracker.press(false, MOUSE) // pressed inside the dialog (seen in the capture phase, overwrites the same pointer)
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

test('concurrent pointers are tracked independently', () => {
	const tracker = createBackdropPressTracker()
	// Pointer A presses the backdrop; Pointer B presses inside the dialog concurrently
	tracker.press(true, TOUCH)
	tracker.press(false, TOUCH_2)
	assert.equal(tracker.activeCount, 2)
	assert.equal(tracker.isBackdropPointer(TOUCH), true)
	assert.equal(tracker.isBackdropPointer(TOUCH_2), false)

	// B releasing on the backdrop must NOT close (it started inside)
	assert.equal(tracker.release(true, TOUCH_2), false)
	assert.equal(tracker.activeCount, 1)

	// A releasing on the backdrop still closes the prompt
	assert.equal(tracker.release(true, TOUCH), true)
	assert.equal(tracker.activeCount, 0)
})

test('releasing an untracked pointer does not affect tracked pointers', () => {
	const tracker = createBackdropPressTracker()
	tracker.press(true, TOUCH)
	assert.equal(tracker.release(true, TOUCH_2), false)
	assert.equal(tracker.activeCount, 1)
	assert.equal(tracker.release(true, TOUCH), true)
	assert.equal(tracker.activeCount, 0)
})

test('a cancelled press is not reused by the next release', () => {
	const tracker = createBackdropPressTracker()
	tracker.press(true, MOUSE)
	tracker.cancel(MOUSE)
	assert.equal(tracker.release(true, MOUSE), false)
})

test('there is nothing to release without a tracked press', () => {
	const tracker = createBackdropPressTracker()
	assert.equal(tracker.activeCount, 0)
	assert.equal(tracker.release(true, MOUSE), false)
	assert.equal(tracker.activeCount, 0)
})


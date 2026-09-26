/**
 * Backdrop press tracking for the shared Prompt dialog.
 *
 * The dialog may only close when the same pointer both presses and releases on
 * the dark backdrop. Presses that start inside the dialog are observed in the
 * capture phase, because .prompt-wrapper stops their bubbling before the
 * overlay's own handler could see them, and they must invalidate an earlier
 * backdrop press whose pointerup was lost, e.g. when the user releases the
 * mouse outside the browser window.
 *
 * Multiple concurrent pointers (e.g. multi-touch) are tracked independently
 * by pointerId so that a touch inside the dialog does not cancel a concurrent
 * backdrop press on another finger, and releasing one pointer does not detach
 * or clear another pointer's tracked press.
 */
export function createBackdropPressTracker() {
	const activePointers = new Map()

	return {
		/** Total number of currently tracked active pointers. */
		get activeCount() {
			return activePointers.size
		},
		/** Check whether a given pointer started on the backdrop. */
		isBackdropPointer(pointerId) {
			return activePointers.get(pointerId) === true
		},
		/** Record where a pointer started its press (true = backdrop, false = inner). */
		press(isBackdrop, pointerId) {
			activePointers.set(pointerId, isBackdrop)
		},
		/**
		 * Finish a press. Returns true only if the same pointer started on the
		 * backdrop and also released on the backdrop.
		 */
		release(isBackdrop, pointerId) {
			const startedOnBackdrop = activePointers.get(pointerId) === true
			activePointers.delete(pointerId)
			return startedOnBackdrop && isBackdrop
		},
		/** Drop a tracked pointer when the browser cancels it. */
		cancel(pointerId) {
			activePointers.delete(pointerId)
		},
		/** Drop all tracked presses (e.g. on unmount). */
		clear() {
			activePointers.clear()
		}
	}
}


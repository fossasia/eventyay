/**
 * Backdrop press tracking for the shared Prompt dialog.
 *
 * The dialog may only close when the same pointer both presses and releases on
 * the dark backdrop. Presses that start inside the dialog are observed in the
 * capture phase, because .prompt-wrapper stops their bubbling before the
 * overlay's own handler could see them, and they must invalidate an earlier
 * backdrop press whose pointerup was lost, e.g. when the user releases the
 * mouse outside the browser window.
 */
export function createBackdropPressTracker() {
	let backdropPointerId = null

	return {
		get backdropPointerId() {
			return backdropPointerId
		},
		/** Remember the pointer that started a press, or forget it for inner presses. */
		press(isBackdrop, pointerId) {
			backdropPointerId = isBackdrop ? pointerId : null
		},
		/** True when the same pointer both pressed and released on the backdrop. */
		release(isBackdrop, pointerId) {
			const isBackdropClick = backdropPointerId !== null && backdropPointerId === pointerId && isBackdrop
			backdropPointerId = null
			return isBackdropClick
		},
		/** Drop the tracked press when the browser cancels the pointer. */
		cancel(pointerId) {
			if (backdropPointerId === pointerId) {
				backdropPointerId = null
			}
		}
	}
}

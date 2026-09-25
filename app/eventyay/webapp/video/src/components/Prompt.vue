<template lang="pug">
.c-prompt(@pointerdown="onPointerdown")
	.prompt-wrapper(ref="wrapper", @pointerdown.stop="")
		bunt-icon-button#btn-close(v-if="allowCancel", @click="$emit('close')") close
		slot.content
</template>
<script>
import { Scrollbars } from 'buntpapier/src/directives/scrollbar'
import { createBackdropPressTracker } from 'lib/promptPointer'

export default {
	props: {
		action: String, // block, ban, silence, unban, unsilence
		allowCancel: {
			type: Boolean,
			default: true
		},
		scrollable: {
			type: Boolean,
			default: true
		}
	},
	emits: ['close'],
	created() {
		this._backdropPress = createBackdropPressTracker()
	},
	mounted() {
		this.$nextTick(() => {
			if (!this.scrollable) return
			this.scrollbars = new Scrollbars(this.$refs.wrapper, {
				scrollY: true
			})
		})
	},
	methods: {
		onPointerdown(event) {
			if (!this.allowCancel) return
			event.stopPropagation()
			this._backdropPress.press(event.target === this.$el, event.pointerId)
			// The capture listener is registered so that presses starting inside
			// the dialog, whose bubbling .prompt-wrapper stops, still reach us.
			this.$el.addEventListener('pointerdown', this.onPointerdownCapture, true)
			this.$el.addEventListener('pointerup', this.onPointerup)
			this.$el.addEventListener('pointercancel', this.onPointercancel)
		},
		onPointerdownCapture(event) {
			if (event.target !== this.$el) {
				this._backdropPress.press(false, event.pointerId)
			}
		},
		onPointerup(event) {
			this.$el.removeEventListener('pointerdown', this.onPointerdownCapture, true)
			this.$el.removeEventListener('pointerup', this.onPointerup)
			this.$el.removeEventListener('pointercancel', this.onPointercancel)
			// Close only when the same pointer both started and ended on the backdrop.
			if (!this._backdropPress.release(event.target === this.$el, event.pointerId)) return
			this.$emit('close')
		},
		onPointercancel(event) {
			this._backdropPress.cancel(event.pointerId)
			this.$el.removeEventListener('pointerdown', this.onPointerdownCapture, true)
			this.$el.removeEventListener('pointerup', this.onPointerup)
			this.$el.removeEventListener('pointercancel', this.onPointercancel)
		}
	}
}
</script>
<style lang="stylus">
.c-prompt
	position: fixed
	top: 0
	left: 0
	right: 0
	bottom: 0
	width: 100vw
	height: 100vh
	height: 100dvh
	height: var(--vh100, 100vh)
	z-index: 2000
	background-color: rgba(0, 0, 0, 0.54)
	display: flex
	justify-content: center
	align-items: safe center
	overflow-y: auto
	padding: 16px 0
	box-sizing: border-box
	.prompt-wrapper
		card()
		display: flex
		flex-direction: column
		width: 480px
		max-height: calc(100vh - 32px)
		max-height: calc(100dvh - 32px)
		max-height: calc(var(--vh100, 100vh) - 32px)
		min-height: 0
		flex-shrink: 1
		position: relative
		+below('m')
			width: 100vw
			max-height: calc(100vh - 32px)
			max-height: calc(100dvh - 32px)
			max-height: calc(var(--vh100, 100vh) - 32px)
		> .content
			display: flex
			flex-direction: column
			flex: 1 1 auto
			min-height: 0
			overflow: hidden
		#btn-close
			icon-button-style(style: clear)
			position: absolute
			top: 8px
			right: 8px
			z-index: 10
.prompt-enter-active, .prompt-leave-active
	transition: opacity .3s
.prompt-enter-from, .prompt-leave-to
	opacity: 0
</style>

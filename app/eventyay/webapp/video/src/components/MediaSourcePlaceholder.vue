<template lang="pug">
.c-media-source-placeholder(v-resize-observer="onResize")
</template>
<script>
// LIMITATIONS:
// - ResizeObserver does not fire on pure position changes, so we also observe
//   layout ancestors and follow sidebar width transitions that only move the
//   placeholder (chat rail and nav collapse).
const LAYOUT_FOLLOW_MS = 220

export default {
	components: {},
	data() {
		return {
			layoutRaf: 0,
			layoutObservers: [],
			layoutRoots: []
		}
	},
	computed: {},
	watch: {
		'$store.state.roomSidebarCollapsedByRoom': {
			deep: true,
			handler() {
				this.followLayoutTransition()
			}
		}
	},
	created() {},
	async mounted() {
		await this.$nextTick()
		this.onResize()
		window.addEventListener('scroll', this.onResize, { passive: true })
		window.addEventListener('resize', this.onResize, { passive: true })
		this.observeLayoutAncestors()
		this.layoutRoots = [
			this.$el.closest('.c-room'),
			this.$el.closest('.app-content')
		].filter(Boolean)
		for (const el of this.layoutRoots) {
			el.addEventListener('transitionrun', this.onLayoutTransition)
			el.addEventListener('transitionend', this.onResize)
		}
	},
	beforeUnmount() {
		window.removeEventListener('scroll', this.onResize)
		window.removeEventListener('resize', this.onResize)
		for (const el of this.layoutRoots) {
			el.removeEventListener('transitionrun', this.onLayoutTransition)
			el.removeEventListener('transitionend', this.onResize)
		}
		this.layoutRoots = []
		this.stopFollowingLayout()
		for (const observer of this.layoutObservers) {
			observer.disconnect()
		}
		this.layoutObservers = []
		this.$store.commit('reportMediaSourcePlaceholderRect', null)
	},
	methods: {
		onResize() {
			if (!this.$el) return
			this.$store.commit(
				'reportMediaSourcePlaceholderRect',
				this.$el.getBoundingClientRect(),
			)
		},
		onLayoutTransition(event) {
			if (event.propertyName !== 'width' && event.propertyName !== 'padding-left') return
			this.followLayoutTransition()
		},
		observeLayoutAncestors() {
			if (typeof ResizeObserver === 'undefined' || !this.$el) return
			const ancestors = [
				this.$el.closest('.stage-canvas-container'),
				this.$el.closest('.c-room'),
				this.$el.closest('.app-content')
			].filter(Boolean)
			const seen = new Set()
			for (const el of ancestors) {
				if (seen.has(el)) continue
				seen.add(el)
				const observer = new ResizeObserver(() => this.onResize())
				observer.observe(el)
				this.layoutObservers.push(observer)
			}
		},
		followLayoutTransition() {
			this.stopFollowingLayout()
			const startedAt = performance.now()
			const tick = (now) => {
				this.onResize()
				if (now - startedAt < LAYOUT_FOLLOW_MS) {
					this.layoutRaf = requestAnimationFrame(tick)
				} else {
					this.layoutRaf = 0
					this.onResize()
				}
			}
			this.layoutRaf = requestAnimationFrame(tick)
		},
		stopFollowingLayout() {
			if (this.layoutRaf) {
				cancelAnimationFrame(this.layoutRaf)
				this.layoutRaf = 0
			}
		}
	}
}
</script>
<style lang="stylus">
</style>

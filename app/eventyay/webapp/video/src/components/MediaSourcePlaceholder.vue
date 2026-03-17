<template lang="pug">
.c-media-source-placeholder(v-resize-observer="onResize")
</template>
<script>
// LIMITATIONS:
// - ResizeObserver does not fire on pure position changes, so we rely on layout/resize
//   changes to refresh the placeholder rect.
export default {
	components: {},
	data() {
		return {
		}
	},
	computed: {},
	created() {},
	async mounted() {
		await this.$nextTick()
		this.$store.commit('reportMediaSourcePlaceholderRect', this.$el.getBoundingClientRect())
	},
	beforeUnmount() {
		this.$store.commit('reportMediaSourcePlaceholderRect', null)
	},
	methods: {
		onResize() {
			this.$store.commit(
				'reportMediaSourcePlaceholderRect',
				this.$el.getBoundingClientRect(),
			)
		}
	}
}
</script>
<style lang="stylus">
</style>

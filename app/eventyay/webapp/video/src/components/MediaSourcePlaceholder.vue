<template lang="pug">
.c-media-source-placeholder(v-resize-observer="onResize")
</template>
<script>
// LIMITATIONS:
// - has to always be top left because ResizeObserver can't observe position changes
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
			this.$store.commit('reportMediaSourcePlaceholderRect', this.$el.getBoundingClientRect())
		}
	}
}
</script>
<style lang="stylus">
</style>

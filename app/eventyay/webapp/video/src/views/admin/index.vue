<template lang="pug">
.c-admin
	h1 {{ $t('admin') }}
	p {{ $t('here be global config') }}
</template>
<script>
export default {
	components: {},
	data() {
		return {
		}
	},
	computed: {},
	created() {},
	mounted() {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
.c-admin
	padding: 0 16px
</style>

<template lang="pug">
.c-disabled-video-component(role="status")
	.icon(aria-hidden="true")
		i.mdi.mdi-lock-outline
	h2 {{ componentLabel }}
	p {{ $t('This component is currently disabled by the platform administrator.') }}
	p.hint {{ $t('Existing room configuration has been kept, but this feature cannot be used while it is disabled.') }}
</template>
<script>
import { getDisabledModuleLabel } from 'lib/video-component-flags'

export default {
	props: {
		moduleType: {
			type: String,
			required: true,
		},
	},
	computed: {
		componentLabel() {
			return getDisabledModuleLabel(this.moduleType, this.$t.bind(this))
		},
	},
}
</script>
<style lang="stylus">
.c-disabled-video-component
	flex: auto
	display: flex
	flex-direction: column
	align-items: center
	justify-content: center
	min-height: min(56.25vw, 50vh)
	padding: 48px 32px
	margin: 16px
	text-align: center
	background-color: $clr-grey-50
	border: 1px dashed $clr-grey-300
	border-radius: 12px
	box-sizing: border-box
	.icon
		display: flex
		align-items: center
		justify-content: center
		width: 72px
		height: 72px
		margin-bottom: 20px
		border-radius: 50%
		background-color: $clr-white
		color: $clr-grey-500
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06)
		i.mdi
			font-size: 36px
			line-height: 1
	h2
		margin: 0 0 12px
		font-size: 20px
		font-weight: 600
		color: $clr-grey-900
	p
		margin: 0
		max-width: 480px
		font-size: 15px
		line-height: 22px
		color: $clr-secondary-text-light
	.hint
		margin-top: 12px
		font-size: 13px
		line-height: 20px
		color: $clr-grey-500
</style>

<template lang="pug">
.c-detail-top-bar(v-if="showBack || $slots.default")
	nav.back-nav(v-if="showBack", :aria-label="backLabel")
		button.back-link(type="button", @click="goBack")
			svg.back-icon(viewBox="0 0 24 24", aria-hidden="true")
				path(fill="currentColor", d="M20,11V13H8L13.5,18.5L12.08,19.92L4.16,12L12.08,4.08L13.5,5.5L8,11H20Z")
			span.back-label {{ backLabel }}
	.detail-top-actions(v-if="$slots.default")
		slot
</template>

<script>
export default {
	name: 'DetailBackNav',
	inject: {
		parentEventUrl: { from: 'eventUrl', default: '' },
		translationMessages: { default: () => ({}) },
	},
	props: {
		eventUrl: {
			type: String,
			default: ''
		},
	},
	computed: {
		resolvedEventUrl () {
			return this.eventUrl || this.parentEventUrl || ''
		},
		backLabel () {
			const messages = this.translationMessages || {}
			return messages.back || 'Back'
		},
		showBack () {
			return Boolean(this.resolvedEventUrl || (typeof window !== 'undefined' && window.history.length > 1))
		},
	},
	methods: {
		goBack () {
			if (typeof window !== 'undefined' && window.history.length > 1) {
				window.history.back()
				return
			}
			if (this.resolvedEventUrl) {
				window.location.href = this.resolvedEventUrl
			}
		},
	},
}
</script>

<style lang="stylus">
.c-detail-top-bar
	display: flex
	align-items: center
	justify-content: space-between
	gap: 12px
	padding: 12px 16px 0
	flex-wrap: nowrap
	.back-nav
		flex-shrink: 1
		min-width: 0
	.back-link
		display: inline-flex
		align-items: center
		gap: 6px
		padding: 7px 14px 7px 10px
		border-radius: 999px
		border: 1px solid $clr-grey-300
		background-color: $clr-white
		color: $clr-primary-text-light
		text-decoration: none
		font-size: 14px
		font-weight: 600
		line-height: 1.2
		box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04)
		transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease, transform 0.15s ease
		cursor: pointer
		max-width: 100%
		.back-icon
			width: 18px
			height: 18px
			flex-shrink: 0
		.back-label
			white-space: nowrap
			overflow: hidden
			text-overflow: ellipsis
		&:hover
			background-color: unquote("color-mix(in srgb, var(--pretalx-clr-primary, var(--clr-primary)) 8%, white)")
			border-color: var(--pretalx-clr-primary, var(--clr-primary))
			color: var(--pretalx-clr-primary, var(--clr-primary))
			box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08)
		&:active
			transform: translateY(1px)
		&:focus-visible
			outline: 2px solid var(--pretalx-clr-primary, var(--clr-primary))
			outline-offset: 2px
	.detail-top-actions
		display: flex
		align-items: center
		gap: 8px
		flex-shrink: 0
		margin-left: auto
	@media (max-width: 480px)
		padding: 10px 10px 0
		gap: 8px
		.back-link
			font-size: 13px
			padding: 6px 12px 6px 8px
		.detail-top-actions
			gap: 4px
</style>

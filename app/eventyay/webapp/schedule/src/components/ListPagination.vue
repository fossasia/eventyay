<template lang="pug">
.list-pagination(:class="{compact, directional: isDirectional}")
	nav.page-controls(v-if="isDirectional", :aria-label="ariaLabel")
		button.page-btn.nav-prev(
			v-if="currentPage > 1",
			type="button",
			:disabled="loading",
			:aria-label="previousAriaLabel",
			@click="$emit('change', currentPage - 1)"
		) {{ previousLabel }}
		span.page-status(v-if="status") {{ status }}
		button.page-btn.nav-next(
			v-if="currentPage < totalPages",
			type="button",
			:disabled="loading",
			:aria-label="nextAriaLabel",
			@click="$emit('change', currentPage + 1)"
		) {{ nextLabel }}
	template(v-else)
		p.page-status(v-if="status") {{ status }}
		nav.page-controls(:aria-label="ariaLabel")
			button.page-btn.nav-prev(
				type="button",
				:disabled="currentPage <= 1 || loading",
				:aria-label="previousAriaLabel",
				@click="$emit('change', currentPage - 1)"
			) {{ previousLabel }}
			button.page-btn(
				v-for="(item, idx) in items",
				:key="`${item}-${idx}`",
				type="button",
				:class="{current: item === currentPage, ellipsis: item === 'ellipsis'}",
				:disabled="item === 'ellipsis' || loading",
				:aria-current="item === currentPage ? 'page' : null",
				:aria-label="itemAriaLabel ? itemAriaLabel(item) : null",
				@click="item !== 'ellipsis' && $emit('change', item)"
			) {{ item === 'ellipsis' ? '…' : item }}
			button.page-btn.nav-next(
				type="button",
				:disabled="currentPage >= totalPages || loading",
				:aria-label="nextAriaLabel",
				@click="$emit('change', currentPage + 1)"
			) {{ nextLabel }}
</template>
<script>
export default {
	props: {
		currentPage: {type: Number, required: true},
		totalPages: {type: Number, required: true},
		items: {type: Array, default: () => []},
		variant: {type: String, default: 'pages'},
		status: {type: String, default: ''},
		ariaLabel: {type: String, default: ''},
		previousLabel: {type: String, required: true},
		nextLabel: {type: String, required: true},
		previousAriaLabel: {type: String, default: ''},
		nextAriaLabel: {type: String, default: ''},
		itemAriaLabel: {type: Function, default: null},
		loading: {type: Boolean, default: false},
		compact: {type: Boolean, default: false},
	},
	emits: ['change'],
	computed: {
		isDirectional () {
			return this.variant === 'directional'
		},
	},
}
</script>
<style lang="stylus">
.list-pagination
	display: flex
	flex-direction: column
	align-items: center
	gap: 8px
	padding: 16px 12px 24px
	&.compact
		padding: 8px 16px 24px
	.page-status
		margin: 0
		font-size: 13px
		color: $clr-secondary-text-light
	.page-controls
		display: flex
		flex-wrap: nowrap
		justify-content: center
		align-items: center
		gap: 6px
		width: 100%
		overflow-x: auto
	.page-btn
		appearance: none
		flex: 0 0 auto
		min-width: 36px
		height: 36px
		padding: 0 10px
		border: 1px solid var(--pretalx-clr-primary, #3aa57c)
		background: #fff
		color: var(--pretalx-clr-primary, #3aa57c)
		border-radius: 8px
		font-size: 14px
		font-weight: 600
		white-space: nowrap
		cursor: pointer
		&:hover, &:focus-visible
			background: var(--pretalx-clr-primary, #3aa57c)
			color: #fff
			outline: none
		&.current
			background: var(--pretalx-clr-primary, #3aa57c)
			color: #fff
		&.ellipsis, &:disabled
			cursor: default
			opacity: 0.55
		&.ellipsis:disabled
			border-color: transparent
			background: transparent
			color: $clr-secondary-text-light
			opacity: 1
	&.directional
		padding: 0
		.page-controls
			gap: 12px
			margin-top: 8px
			overflow: visible
		.page-status
			text-align: center
		.page-btn
			min-width: 0
			height: auto
			padding: 4px 10px
			font-size: 13px
			background: $clr-white
			&:disabled, &:disabled:hover
				opacity: 0.45
				cursor: default
				background: $clr-white
				color: var(--pretalx-clr-primary, var(--clr-primary))

@media (max-width: 600px)
	.list-pagination:not(.directional)
		padding: 12px 8px 20px
		&.compact
			padding: 8px 8px 16px
		.page-controls
			gap: 4px
		.page-btn
			min-width: 30px
			height: 32px
			padding: 0 7px
			font-size: 13px
			border-radius: 7px
		.page-btn.nav-prev,
		.page-btn.nav-next
			min-width: 32px
			padding: 0 8px
</style>

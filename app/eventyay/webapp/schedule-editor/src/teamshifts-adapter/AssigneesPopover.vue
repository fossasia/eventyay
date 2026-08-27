<template lang="pug">
teleport(to="body")
	.role-assignees-popover(
		v-if="open",
		:style="panelStyle",
		@click.stop="",
		@pointerdown.stop="")
		.role-assignees-popover-title {{ title }}
		ul.role-assignees-popover-list
			li(v-for="(user, i) in assignees", :key="user.id || i")
				svg.role-user-icon(viewBox="0 0 24 24", aria-hidden="true")
					path(fill="currentColor", d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z")
				span.role-assignees-popover-name {{ user.name }}
</template>

<script lang="ts" setup>
import { computed } from 'vue'

const props = defineProps<{
  open: boolean
  title: string
  assignees: Array<{ id?: number | string, name: string }>
  top: number
  left: number
  width?: number
  maxHeight?: number
}>()

const panelStyle = computed(() => ({
  '--assignees-popover-top': `${props.top}px`,
  '--assignees-popover-left': `${props.left}px`,
  '--assignees-popover-width': `${props.width ?? 260}px`,
  '--assignees-popover-max-height': `${props.maxHeight ?? 280}px`,
}))
</script>

<style lang="stylus">
.role-assignees-popover
	position: fixed
	top: var(--assignees-popover-top)
	left: var(--assignees-popover-left)
	width: var(--assignees-popover-width)
	max-height: var(--assignees-popover-max-height)
	z-index: 4000
	box-sizing: border-box
	background: $clr-white
	border: 1px solid $clr-dividers-light
	border-radius: 6px
	box-shadow: 0 8px 24px rgba(0, 0, 0, 0.16)
	padding: 10px
	display: flex
	flex-direction: column
	min-width: 0
	.role-assignees-popover-title
		font-size: 11px
		font-weight: 700
		text-transform: uppercase
		letter-spacing: 0.03em
		color: $clr-secondary-text-light
		margin: 0 0 8px
		flex-shrink: 0
	.role-assignees-popover-list
		list-style: none
		margin: 0
		padding: 0
		overflow: auto
		display: flex
		flex-direction: column
		gap: 8px
		min-height: 0
		li
			display: flex
			align-items: flex-start
			gap: 8px
			min-width: 0
		.role-user-icon
			width: 12px
			height: 12px
			flex-shrink: 0
			margin-top: 2px
			color: $clr-secondary-text-light
		.role-assignees-popover-name
			min-width: 0
			flex: 1
			font-size: 12px
			line-height: 1.4
			overflow-wrap: anywhere
			word-break: break-word
</style>

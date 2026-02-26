<template lang="pug">
router-link.c-room-list-item.table-row(:to="{name: 'admin:rooms:item', params: {roomId: room.id}}", :class="{'mystery': !inferredType}")
	.handle.mdi.mdi-drag-vertical(:class="{disabled}", v-handle, v-tooltip="disabled ? 'sorting is disabled while searching' : ''")
	.name(v-html="$emojify($localize(room.name))")
	.badge-cell
		.room-type-badge(:class="badgeClass")
			.mdi(:class="badgeIcon")
			span {{ badgeLabel }}
</template>
<script>
import { ElementMixin, HandleDirective } from 'vue-slicksort'
import { inferRoomType, inferType } from 'lib/room-types'

export default {
	directives: { handle: HandleDirective },
	mixins: [ElementMixin],
	props: {
		room: Object
	},
	computed: {
		inferredType () {
			const fromConfig = Array.isArray(this.room?.module_config)
				? inferType({ module_config: this.room.module_config })
				: null
			return fromConfig || inferRoomType(this.room)
		},
		badgeLabel () {
			return this.inferredType ? this.inferredType.name : 'Unconfigured'
		},
		badgeIcon () {
			return this.inferredType ? `mdi-${this.inferredType.icon}` : 'mdi-help-circle-outline'
		},
		badgeClass () {
			return this.inferredType ? `type-${this.inferredType.id}` : 'type-mystery'
		}
	}
}
</script>
<style lang="stylus">
.c-room-list-item
	display: flex
	align-items: center
	color: $clr-primary-text-light
	&.mystery
		border-left: 3px solid $clr-orange
	.handle
		user-select: none
		cursor: row-resize
		font-size: 24px
		&.disabled
			cursor: auto
			color: $clr-grey-300
	.name
		flex: auto
		ellipsis()
	.badge-cell
		display: flex
		align-items: center
		justify-content: flex-end
	.room-type-badge
		display: flex
		align-items: center
		gap: 4px
		flex: none
		max-width: 220px
		padding: 4px 10px
		border-radius: 999px
		font-size: 12px
		line-height: 16px
		background-color: $clr-grey-100
		color: $clr-secondary-text-light
		border: 1px solid $clr-grey-200
		white-space: nowrap
		.mdi
			font-size: 14px
			flex: none
		span
			min-width: 0
			overflow: hidden
			text-overflow: ellipsis
			display: block
		&.type-mystery
			background-color: $clr-orange-100
			color: $clr-orange-900
			border-color: $clr-orange-100
		&.type-stage
			background-color: $clr-blue-50
			color: $clr-blue-900
			border-color: $clr-blue-50
		&.type-channel-bbb,
		&.type-channel-janus,
		&.type-channel-zoom,
		&.type-channel-roulette
			background-color: $clr-blue-grey-200
			color: $clr-blue-grey-900
			border-color: $clr-blue-grey-200
		&.type-channel-text,
		&.type-page-static,
		&.type-page-iframe,
		&.type-page-landing,
		&.type-page-userlist
			background-color: $clr-grey-50
			color: $clr-grey-800
			border-color: $clr-grey-200
		&.type-exhibition,
		&.type-posters
			background-color: $clr-green-300
			color: $clr-green-800
			border-color: $clr-green-300
</style>

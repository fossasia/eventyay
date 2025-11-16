<template lang="pug">
.c-room-list-item.table-row
	.handle.mdi.mdi-drag-vertical(:class="{disabled}", v-handle, v-tooltip="disabled ? 'sorting is disabled while searching' : ''")
	router-link.name(:to="{name: 'admin:rooms:item', params: {roomId: room.id}}", v-html="$emojify($localize(room.name))")
	.visibility
		i.fa(:class="visibilityIconClass")
	.actions
		bunt-button(size="small", @click.stop="openRoomConfig") {{ actionLabel }}
</template>
<script>
import { ElementMixin, HandleDirective } from 'vue-slicksort'
export default {
	directives: { handle: HandleDirective },
	mixins: [ElementMixin],
	props: {
		room: Object,
		disabled: Boolean
	},
	computed: {
		isConfigured() {
			return !!this.room.setup_complete
		},
		actionLabel() {
			return this.isConfigured ? 'Configure' : 'Complete Setup'
		},
		visibilityIconClass() {
			if (this.room.hidden) return 'fa-eye-slash hidden-room'
			if (!this.room.setup_complete) return 'fa-eye-slash setup-incomplete'
			if (this.room.sidebar_hidden) return 'fa-eye-slash sidebar-hidden'
			return 'fa-eye visible-room'
		}
	},
	methods: {
		openRoomConfig() {
			this.$router.push({name: 'admin:rooms:item', params: {roomId: this.room.id}})
		}
	}
}
</script>
<style lang="stylus">
.c-room-list-item
	display: flex
	align-items: center
	color: $clr-primary-text-light
	width: 100%
	box-sizing: border-box
	.handle
		user-select: none
		cursor: row-resize
		font-size: 24px
		&.disabled
			cursor: auto
			color: $clr-grey-300
	.visibility
		width: 80px
		text-align: center
		font-size: 18px
		.fa
			font-size: 20px
			color: $clr-primary-text-light
	.actions
		width: 160px
		display: flex
		justify-content: flex-end

.c-room-list-item.slick-sortable-helper
	width: 100%
	box-sizing: border-box
	background-color: $clr-grey-50
	box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08)
</style>

<template lang="pug">
.c-admin-rooms
	.header
		.actions
			h2 Rooms
			bunt-link-button.btn-create(:to="{name: 'admin:rooms:new'}") Create a new room
		.right-actions
			.export-actions(v-if="canExportBroadcastConfiguration")
				a.export-button(:href="exportUrl('xlsx')") Export XLSX
				a.export-button.secondary(:href="exportUrl('csv-excel')") CSV
			bunt-input.search(name="search", placeholder="Search rooms", icon="search", v-model="search")
	.error(v-if="error")
		span Failed to load rooms.
		span(v-if="errorCode")  ({{ errorCode }})
		span(v-if="errorCode === 'protocol.denied'")  You likely lack admin permissions.
	.rooms-list(v-else)
		.header
			.drag
			.name Name
		SlickList.tbody(v-if="rooms", v-model:list="rooms", lockAxis="y", :useDragHandle="true", helperClass="sorting-helper", v-scrollbar.y="", @update:list="onListSort")
			RoomListItem(
				v-for="(room, index) of rooms",
				:index="index",
				:key="room.id",
				:room="room",
				:disabled="!!search",
				v-show="isRoomVisible(room)"
			)
		bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
// TODO show inferred type
import api from 'lib/api'
import fuzzysearch from 'lib/fuzzysearch'
import { mapGetters } from 'vuex'
import { SlickList } from 'vue-slicksort'
import RoomListItem from './RoomListItem'

export default {
	name: 'AdminRooms',
	components: { SlickList, RoomListItem },
	data() {
		return {
			rooms: null,
			search: '',
			error: null,
			errorCode: null,
			_unwatchConnected: null
		}
	},
	watch: {
		'$store.state.rooms'(storeRooms) {
			if (!Array.isArray(this.rooms) || !Array.isArray(storeRooms)) return
			const currentIds = this.rooms.map(r => r.id)
			const storeIds = storeRooms.map(r => r.id)
			const changed =
				currentIds.length !== storeIds.length ||
				currentIds.some((id, i) => id !== storeIds[i])
			if (changed) {
				this.fetchRooms()
			}
		}
	},
	async created() {
		await this.ensureConnectedAndFetch()
	},
	beforeUnmount() {
		if (this._unwatchConnected) this._unwatchConnected()
	},
	computed: {
		...mapGetters(['eventRouting', 'hasPermission']),
		canExportBroadcastConfiguration() {
			return this.hasPermission('room:update') && this.eventRouting.organizer && this.eventRouting.event
		}
	},
	methods: {
		exportUrl(format) {
			const organizer = encodeURIComponent(this.eventRouting.organizer)
			const event = encodeURIComponent(this.eventRouting.event)
			return `/api/v1/organizers/${organizer}/events/${event}/rooms/export-broadcast-configuration/?_format=${encodeURIComponent(format)}`
		},
		isRoomVisible(room) {
			if (!this.search) return true
			const search = this.search.trim()
			return String(room.id) === search || fuzzysearch(this.search.toLowerCase(), this.$localize(room.name).toLowerCase())
		},
		async ensureConnectedAndFetch() {
			if (this.$store.state.connected) return this.fetchRooms()
			this._unwatchConnected = this.$store.watch(
				state => state.connected,
				(connected) => {
					if (connected) {
						if (this._unwatchConnected) this._unwatchConnected()
						this._unwatchConnected = null
						this.fetchRooms()
					}
				}
			)
		},
		async fetchRooms() {
			try {
				this.error = null
				this.errorCode = null
				this.rooms = await api.call('room.config.list')
			} catch (e) {
				this.error = e
				this.errorCode = e?.code || e?.message || String(e)
				console.error(e)
			}
		},
		async onListSort(newList) {
			if (this.search) return
			const previousRooms = [...this.rooms]
			try {
				await api.call('room.config.reorder', newList.map(room => room.id))
			} catch (e) {
				this.rooms = previousRooms
				console.error(e)
			}
		}
	}
}
</script>
<style lang="stylus">
@import 'flex-table'

.c-admin-rooms
	display: flex
	flex-direction: column
	min-height: 0
	background-color: $clr-white
	> .header
		display: flex
		align-items: center
		justify-content: space-between
		background-color: $clr-grey-50
		.actions
			display: flex
			flex: none
			align-items: center
			.bunt-button:not(:last-child)
				margin-right: 16px
			.btn-create
				themed-button-primary()
		.right-actions
			display: flex
			align-items: center
			margin-left: auto
		.export-actions
			display: flex
			align-items: center
			.export-button
				display: inline-flex
				align-items: center
				height: 32px
				padding: 0 12px
				margin-right: 8px
				border-radius: 3px
				background-color: $clr-primary
				color: $clr-white
				font-size: 13px
				font-weight: 500
				text-decoration: none
				&.secondary
					background-color: transparent
					color: $clr-primary
				&:focus
					outline: 2px solid $clr-primary
					outline-offset: 2px
	h2
		margin: 16px
	.search
		input-style(size: compact)
		padding: 0
		margin: 8px
		flex: none
		background-color: $clr-white
	.rooms-list
		flex-table()
		.room
			display: flex
			align-items: center
			color: $clr-primary-text-light
		.drag
			width: 24px
		.name
			flex: auto
			ellipsis()

.sorting-helper
	height: 48px
	line-height: 48px
	background-color: $clr-white
	box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15)
	cursor: grabbing
	z-index: 9999
	> *
		padding: 0 24px
</style>

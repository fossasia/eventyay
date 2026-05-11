<template lang="pug">
.c-admin-rooms
	.header
		.actions
			h2 Rooms
			bunt-link-button.btn-create(:to="{name: 'admin:rooms:new'}") Create a new room
		bunt-input.search(name="search", placeholder="Search rooms", icon="search", v-model="search")
	.error(v-if="error")
		span Failed to load rooms.
		span(v-if="errorCode")  ({{ errorCode }})
		span(v-if="errorCode === 'protocol.denied'")  You likely lack admin permissions.
	.rooms-list(v-else)
		.header
			.drag
			.name Name
		SlickList.tbody(v-if="rooms", :list="rooms", lockAxis="y", :useDragHandle="true", v-scrollbar.y="", @update:list="onListSort")
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
	methods: {
		isRoomVisible(room) {
			if (!this.search) return true
			return room.id === this.search.trim() || fuzzysearch(this.search.toLowerCase(), this.$localize(room.name).toLowerCase())
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
			const previousRooms = this.rooms
			this.rooms = newList
			try {
				this.rooms = await api.call('room.config.reorder', this.rooms.map(room => room.id))
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
	.header
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
</style>

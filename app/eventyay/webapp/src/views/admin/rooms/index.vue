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
			.visibility Visibility
			.actions Actions
		template(v-if="rooms")
			SlickList.tbody(
				v-if="!search",
				v-model:list="rooms",
				lockAxis="y",
				:valueKey='"id"',
				:valueKey="'id'",
				:useDragHandle="true",
				v-scrollbar.y="",
				@update:list="onListSort"
			)
				RoomListItem(v-for="(room, index) of rooms" :index="index", :key="room.id", :room="room", :disabled="rooms.length < 2")
			.table-body(v-else, v-scrollbar.y="")
				RoomListItem(v-for="room of filteredRooms", :key="room.id", :room="room", :disabled="filteredRooms.length < 2")
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
	computed: {
		filteredRooms() {
			if (!this.rooms) return
			if (!this.search) return this.rooms
			return this.rooms.filter(room => room.id === this.search.trim() || fuzzysearch(this.search.toLowerCase(), this.$localize(room.name).toLowerCase()))
		}
	},
	async created() {
		await this.ensureConnectedAndFetch()
	},
	beforeUnmount() {
		if (this._unwatchConnected) this._unwatchConnected()
	},
	methods: {
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
		async onListSort() {
			const idList = this.rooms.map(room => String(room.id))
			const previousOrder = [...this.rooms]
			try {
				this.rooms = await api.call('room.config.reorder', idList)
			} catch (e) {
				console.error(e)
				// Rollback to previous order on error
				this.rooms = previousOrder
				await this.fetchRooms()
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
			h2
				margin: 16px
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
		.header
			margin-bottom: 0
			padding-bottom: 8px
			border-bottom: border-separator()
		.slick-list
			margin-top: 0
		.table-row
			width: 100%
			box-sizing: border-box
		.table-body
			display: block
			max-height: calc(100vh - 260px)
			overflow: auto
		.room
			display: flex
			align-items: center
			color: $clr-primary-text-light
		.drag
			width: 24px
		.name
			flex: auto
			ellipsis()
		.visibility
			width: 80px
			text-align: center
		.actions
			width: 160px
			text-align: right
</style>

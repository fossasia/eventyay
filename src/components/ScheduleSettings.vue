<template lang="pug">
.settings
	app-dropdown(key="tracks", lazy)
		template(v-slot:toggler)
			span Tracks
		app-dropdown-content
			app-dropdown-item(v-for="track in languageFilteredTracks", :key="track.value")
				.checkbox-line(:style="{'--track-color': track.color}")
					bunt-checkbox(type="checkbox", :label="track.label", :name="track.value + track.label", :model-value="track.selected", @input="$emit('trackToggled', track.value)")

	app-dropdown(key="rooms", lazy)
		template(v-slot:toggler)
			span Rooms
		app-dropdown-content
			app-dropdown-item(v-for="room in languageFilteredRooms", :key="room.value")
				.checkbox-line(:style="{'--track-color': room.color}")
					bunt-checkbox(type="checkbox", :label="room.label", :name="room.value + room.label", :model-value="room.selected" @input="$emit('roomToggled', room.value)")

	app-dropdown(v-if="languageFilteredSessionTypes.length", key="session-types", lazy)
		template(v-slot:toggler)
			span Types
		app-dropdown-content
			app-dropdown-item(v-for="sesstype in languageFilteredSessionTypes", :key="sesstype.value")
				.checkbox-line(:style="{'--track-color': sesstype.color}")
					bunt-checkbox(type="checkbox", :label="sesstype.label", :name="sesstype.value + sesstype.label", :model-value="sesstype.selected", @input="$emit('sessionTypeToggled', sesstype.value)")

	template(v-if="filteredTracksCount") ({{ filteredTracksCount }})
	bunt-button.fav-toggle(v-if="favsCount", @click="$emit('toggleFavs')", :class="onlyFavs ? ['active'] : []")
		svg#star(viewBox="0 0 24 24")
			polygon(
				:style="{fill: '#FFA000', stroke: '#FFA000'}"
				points="14.43,10 12,2 9.57,10 2,10 8.18,14.41 5.83,22 12,17.31 18.18,22 15.83,14.41 22,10"
			)
		| {{ favsCount }}
	template(v-if="!inEventTimezone")
		bunt-select.timezone-item(name="timezone", :options="timezoneOptions", v-model="timezoneModel", @blur="$emit('saveTimezone')")
	template(v-else)
		div.timezone-label.timezone-item.bunt-tab-header-item {{ scheduleTimezone }}
</template>

<script>
import AppDropdown from './AppDropdown.vue'
import AppDropdownContent from './AppDropdownContent.vue'
import AppDropdownItem from './AppDropdownItem.vue'

export default {
	name: 'ScheduleSettings',
	components: { AppDropdown, AppDropdownContent, AppDropdownItem },
	props: {
		tracks: {
			type: Array,
			default: () => []
		},
		filteredTracksCount: {
			type: Number,
			default: 0
		},
		// @type: {Array<{value: string, label: string, selected: boolean}>}
		languageFilteredTracks: {
			type: Array,
			default: () => []
		},
		languageFilteredRooms: {
			type: Array,
			default: () => []
		},
		languageFilteredSessionTypes: {
			type: Array,
			default: () => []
		},
		favsCount: {
			type: Number,
			default: 0
		},
		onlyFavs: {
			type: Boolean,
			default: false
		},
		inEventTimezone: {
			type: Boolean,
			default: true
		},
		currentTimezone: String,
		scheduleTimezone: String,
		userTimezone: String
	},
	emits: ['openFilter', 'toggleFavs', 'saveTimezone', 'update:currentTimezone', 'trackToggled', 'roomToggled', 'sessionTypeToggled'],
	computed: {
		timezoneOptions () {
			return [
				{ id: this.scheduleTimezone, label: this.scheduleTimezone },
				{ id: this.userTimezone, label: this.userTimezone }
			]
		},
		timezoneModel: {
		  get() {
				return this.currentTimezone
			},
			set (value) {
				this.$emit('update:currentTimezone', value)
			}
		}
	}
}
</script>

<style lang="stylus">
.settings
	align-self: flex-start
	display: flex
	align-items: center
	z-index: 100
	width: min(calc(100% - 36px), var(--schedule-max-width))
	.fav-toggle
		margin-right: 8px
		display: flex
		&.active
			border: #FFA000 2px solid
		.bunt-button-text
			display: flex
			align-items: center
		svg
			width: 20px
			height: 20px
			margin-right: 6px
	.filter-tracks
		margin: 0 8px
		display: flex
		.bunt-button-text
			display: flex
			align-items: center
			padding-right: 8px
		svg
			width: 36px
			height: 36px
			margin-right: 6px
	.bunt-select
		max-width: 300px
		padding-right: 8px
	.timezone-label
		cursor: default
		color: $clr-secondary-text-light
	.timezone-item
		margin-left: auto
</style>

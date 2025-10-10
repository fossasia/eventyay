<template lang="pug">
.settings
	bunt-button.filter-tracks(v-if="tracks.length", @click="$emit('openFilter')")
		svg#filter(viewBox="0 0 752 752")
			path(d="m401.57 264.71h-174.75c-6.6289 0-11.84 5.2109-11.84 11.84 0 6.6289 5.2109 11.84 11.84 11.84h174.75c5.2109 17.523 21.312 30.309 40.727 30.309 18.941 0 35.52-12.785 40.254-30.309h43.098c6.6289 0 11.84-5.2109 11.84-11.84 0-6.6289-5.2109-11.84-11.84-11.84h-43.098c-5.2109-17.523-21.312-30.309-40.254-30.309-19.414 0-35.516 12.785-40.727 30.309zm58.723 11.84c0 10.418-8.5234 18.469-18.469 18.469s-18.469-8.0508-18.469-18.469 8.5234-18.469 18.469-18.469c9.4727-0.003906 18.469 8.0469 18.469 18.469z")
			path(d="m259.5 359.43h-32.676c-6.6289 0-11.84 5.2109-11.84 11.84s5.2109 11.84 11.84 11.84h32.676c5.2109 17.523 21.312 30.309 40.727 30.309 18.941 0 35.52-12.785 40.254-30.309h185.17c6.6289 0 11.84-5.2109 11.84-11.84s-5.2109-11.84-11.84-11.84h-185.17c-5.2109-17.523-21.312-30.309-40.254-30.309-19.418 0-35.52 12.785-40.73 30.309zm58.723 11.84c0 10.418-8.5234 18.469-18.469 18.469-9.9453 0-18.469-8.0508-18.469-18.469s8.5234-18.469 18.469-18.469c9.9453 0 18.469 8.0508 18.469 18.469z")
			path(d="m344.75 463.61h-117.92c-6.6289 0-11.84 5.2109-11.84 11.84s5.2109 11.84 11.84 11.84h117.92c5.2109 17.523 21.312 30.309 40.727 30.309 18.941 0 35.52-12.785 40.254-30.309h99.926c6.6289 0 11.84-5.2109 11.84-11.84s-5.2109-11.84-11.84-11.84h-99.926c-5.2109-17.523-21.312-30.309-40.254-30.309-19.418 0-35.52 12.785-40.727 30.309zm58.723 11.84c0 10.418-8.5234 18.469-18.469 18.469s-18.469-8.0508-18.469-18.469 8.5234-18.469 18.469-18.469 18.469 8.0508 18.469 18.469z")
		| Filter
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
export default {
	name: 'ScheduleSettings',
	props: {
		tracks: {
			type: Array,
			default: () => []
		},
		filteredTracksCount: {
			type: Number,
			default: 0
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
	emits: ['openFilter', 'toggleFavs', 'saveTimezone', 'update:currentTimezone'],
	computed: {
		timezoneOptions () {
			return [
				{ id: this.scheduleTimezone, label: this.scheduleTimezone },
				{ id: this.userTimezone, label: this.userTimezone }
			]
		},
		timezoneModel: {
			get () {
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
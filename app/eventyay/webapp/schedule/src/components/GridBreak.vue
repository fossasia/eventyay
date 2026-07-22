<template lang="pug">
.c-grid-schedule-break(:style="style")
	.time-box
		.start(v-if="hasAmPm", class="has-ampm")
			.time {{ session.start.clone().tz(timezone).format('h:mm') }}
			.ampm {{ session.start.clone().tz(timezone).format('A') }}
		.start(v-else)
			.time {{ session.start.clone().tz(timezone).format('HH:mm') }}
		.duration {{ getPrettyDuration(session.start, session.end) }}
		.buffer
	.info
		.title {{ getLocalizedString(session.title) }}
</template>
<script>
import { getLocalizedString, getPrettyDuration } from '../utils'

export default {
	props: {
		session: {
			type: Object,
			required: true,
		},
		timezone: {
			type: String,
			required: true,
		},
		hasAmPm: Boolean,
		style: {
			type: [Object, String],
			default: null,
		},
	},
	methods: {
		getLocalizedString,
		getPrettyDuration,
	},
}
</script>
<style lang="stylus">
// Grid breaks are plain divs, not Session.vue instances. Keep card layout here so
// styles always ship with the grid chunk (same pattern as schedule-editor isbreak).
.c-grid-schedule-break
	z-index: 10
	display: flex
	align-items: stretch
	min-height: 96px
	overflow: hidden
	color: rgb(13 15 16)
	position: relative
	font-size: 14px
	border-radius: 6px
	background-color: $clr-grey-200
	.time-box
		width: 64px
		flex-shrink: 0
		box-sizing: border-box
		padding: 10px 4px 6px
		border-radius: 6px 0 0 6px
		display: flex
		flex-direction: column
		align-items: center
		background-color: $clr-grey-500
		.start
			display: flex
			flex-direction: column
			align-items: center
			text-align: center
			width: 100%
			color: $clr-primary-text-dark
			&.has-ampm
				align-self: stretch
			.time
				font-size: 14px
				font-weight: 700
				line-height: 1.2
			.ampm
				font-size: 10px
				margin-top: 1px
				opacity: 0.85
				text-transform: uppercase
		.duration
			font-size: 11px
			margin-top: 4px
			color: $clr-secondary-text-dark
		.buffer
			flex: auto
	.info
		flex: auto
		display: flex
		flex-direction: column
		padding: 8px
		min-width: 0
		border-radius: 0 6px 6px 0
		background-color: $clr-grey-200
		border: none
		justify-content: center
		align-items: center
		.title
			font-size: 16px
			font-weight: 500
			color: $clr-secondary-text-light
			text-align: center
</style>

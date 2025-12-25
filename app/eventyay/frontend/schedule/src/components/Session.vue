<template lang="pug">
a.c-linear-schedule-session(:class="{faved}", :style="style", :href="link", @click="onSessionLinkClick($event, session)", :target="linkTarget")
	.time-box
		.start(:class="{'has-ampm': hasAmPm}")
			.date(v-if="showDate") {{ shortDate }}
			.time {{ startTime.time }}
			.ampm(v-if="startTime.ampm") {{ startTime.ampm }}
		.duration {{ getPrettyDuration(session.start, session.end) }}
		.buffer
		.is-live(v-if="isLive") live
	.info
		.title {{ getLocalizedString(session.title) }}
		.speakers(v-if="session.speakers")
			.avatars
				template(v-for="speaker of session.speakers")
					img(v-if="speaker.avatar_thumbnail_tiny", :src="speaker.avatar_thumbnail_tiny")
					img(v-else-if="speaker.avatar_thumbnail_default", :src="speaker.avatar_thumbnail_default")
					img(v-else-if="speaker.avatar", :src="speaker.avatar")
			.names {{ session.speakers.map(s => s.name).join(', ') }}
		.abstract(v-if="showAbstract", v-html="abstractText")
		.bottom-info
			.track(v-if="session.track") {{ getLocalizedString(session.track.name) }}
			.room(v-if="showRoom && session.room") {{ getLocalizedString(session.room.name) }}
	.session-icons
		fav-button(@toggleFav="toggleFav")
		svg.do-not-record(v-if="session.do_not_record", viewBox="0 0 116.59076 116.59076", width="4116.59076mm", height="116.59076mm", fill="none", xmlns="http://www.w3.org/2000/svg")
			g(transform="translate(-9.3465481,-5.441411)")
				rect(style="fill:#000000;fill-opacity;stroke:none;stroke-width:11.2589;stroke-linecap:round;stroke-dasharray:none;stroke-opacity:1;paint-order:markers stroke fill", width="52.753284", height="39.619537", x="35.496307", y="43.927021", rx="5.5179553", ry="7.573648")
				path(style="fill:#000000;fill-opacity:1;stroke:none;stroke-width:18.7997;stroke-linecap:round;stroke-dasharray:none;stroke-opacity:1;paint-order:markers stroke fill", d="M 99.787546,47.04792 V 80.425654 L 77.727407,63.736793 Z")
				path(style="fill:none;stroke:#b23e65;stroke-width:12;stroke-linecap:round;stroke-dasharray:none;stroke-opacity:1;paint-order:markers stroke fill", d="m 35.553146,95.825578 64.177559,-64.17757 m 16.294055,32.08879 A 48.382828,48.382828 0 0 1 67.641925,112.11961 48.382828,48.382828 0 0 1 19.259099,63.736798 48.382828,48.382828 0 0 1 67.641925,15.353968 48.382828,48.382828 0 0 1 116.02476,63.736798 Z")

</template>
<script>
import { DateTime } from 'luxon'
import MarkdownIt from 'markdown-it'
import { getLocalizedString, getPrettyDuration, getSessionTime } from '~/utils'
import FavButton from '~/components/FavButton.vue'

const markdownIt = MarkdownIt({
	linkify: true,
	breaks: true
})

export default {
	props: {
		now: Object,
		session: Object,
		showAbstract: {
			type: Boolean,
			default: true
		},
		showRoom: {
			type: Boolean,
			default: true
		},
		showDate: {
			type: Boolean,
			default: false
		},
		faved: {
			type: Boolean,
			default: false
		},
		hasAmPm: {
			type: Boolean,
			default: false
		},
		locale: String,
		timezone: String,
		onHomeServer: Boolean
	},
	inject: {
		eventUrl: { default: null },
		linkTarget: { default: '_self' },
		generateSessionLinkUrl: {
			default () {
				return ({eventUrl, session}) => {
					if (!this.onHomeServer) return `#session/${session.id}/`
					return`${eventUrl}talk/${session.id}/`
				}
			}
		},
		onSessionLinkClick: {
			default () {
				return () => {}
			}
		}
	},
	components: {
		FavButton
	},
	data () {
		return {
			getPrettyDuration,
			getLocalizedString,
			getSessionTime,
		}
	},
	computed: {
		link () {
			return this.generateSessionLinkUrl({eventUrl: this.eventUrl, session: this.session})
		},
		style () {
			return {
				'--track-color': this.session.track?.color || 'var(--pretalx-clr-primary)'
			}
		},
		startTime () {
			return getSessionTime(this.session, this.timezone, this.locale, this.hasAmPm)
		},
		shortDate () {
			return this.session.start.setZone(this.timezone).toLocaleString({
				month: 'short',
				day: 'numeric'
			})
		},
		isLive () {
			return this.session.start < this.now && this.session.end > this.now
		},
		abstractText () {
			try {
				return markdownIt.renderInline(this.session.abstract)
			} catch (error) {
				return this.session.abstract
			}
		}
	},
	methods: {
		toggleFav () {
			console.log("toggling fav")
			if (this.faved) {
				this.$emit('unfav', this.session.id)
			} else {
				this.$emit('fav', this.session.id)
			}
		}
	}
}
</script>
<style lang="stylus">
.c-linear-schedule-session, .break
	z-index: 10
	display: flex
	min-width: 300px
	min-height: 96px
	margin: 8px
	overflow: hidden
	color: rgb(13 15 16)
	position: relative
	font-size: 14px
	.time-box
		width: 69px
		box-sizing: border-box
		background-color: var(--track-color)
		padding: 12px 16px 8px 12px
		border-radius: 6px 0 0 6px
		display: flex
		flex-direction: column
		align-items: center
		.start
			color: $clr-primary-text-dark
			font-size: 16px
			font-weight: 600
			margin-bottom: 8px
			.date
				margin-bottom: 4px
				white-space: nowrap
			display: flex
			flex-direction: column
			align-items: flex-end
			&.has-ampm
				align-self: stretch
			.ampm
				font-weight: 400
				font-size: 13px
		.duration
			color: $clr-secondary-text-dark
		.buffer
			flex: auto
		.is-live
			align-self: stretch
			text-align: center
			font-weight: 600
			padding: 2px 4px
			border-radius: 4px
			margin: 0 -10px 0 -6px // HACK
			background-color: $clr-danger
			color: $clr-primary-text-dark
			letter-spacing: 0.5px
			text-transform: uppercase
	.info
		flex: auto
		display: flex
		flex-direction: column
		padding: 8px
		border: border-separator()
		border-left: none
		border-radius: 0 6px 6px 0
		background-color: $clr-white
		min-width: 0
		.title
			font-size: 16px
			font-weight: 500
			margin-bottom: 4px
			margin-right: 20px
		.speakers
			color: $clr-secondary-text-light
			display: flex
			.avatars
				flex: none
				> *:not(:first-child)
					margin-left: -20px
				img
					background-color: $clr-white
					border-radius: 50%
					height: 24px
					width: @height
					margin: 0 8px 0 0
					object-fit: cover
			.names
				line-height: 24px
		.abstract
			margin: 8px 0 12px 0
			// TODO make this take up more space if available?
			display: -webkit-box
			-webkit-line-clamp: 3
			-webkit-box-orient: vertical
			overflow: hidden
		.bottom-info
			flex: auto
			display: flex
			align-items: flex-end
			.track
				flex: 1
				color: var(--track-color)
				ellipsis()
				margin-right: 4px
			.room
				flex: 1
				text-align: right
				color: $clr-secondary-text-light
				ellipsis()
	.do-not-record
		width: 24px
		height: 24px
	.session-icons
		position: absolute
		top: 2px
		right: 2px
		display: flex
		.do-not-record
			padding: 6px 6px 6px 0
		.btn-fav-container
			margin-top: 2px
			display: inline-flex
			icon-button-style(style: clear)
			padding: 2px
			width: 32px
			height: 32px
	&:hover
		.info
			border: 1px solid var(--track-color)
			border-left: none
			.title
				color: var(--pretalx-clr-primary)
@media(hover: none)
	.c-linear-schedule-session .session-icons .btn-fav-container
		display: inline-flex
</style>

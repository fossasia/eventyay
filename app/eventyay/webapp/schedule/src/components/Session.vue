<template lang="pug">
a.c-linear-schedule-session(:class="{faved, 'has-date': showDate}", :style="style", :href="link", @click="onSessionLinkClick($event, session)", :target="linkTarget")
	.time-box
		.start(:class="{'has-ampm': hasAmPm}")
			.date(v-if="showDate") {{ shortDate }}
			.time {{ startTime.time }}
			.ampm(v-if="startTime.ampm") {{ startTime.ampm }}
			.duration {{ getPrettyDuration(session.start, session.end) }}
		.buffer
		.is-live(v-if="showLiveBadge && isLive") live
	.info
		.title {{ getLocalizedString(session.title) }}
		.speakers(v-if="session.speakers")
			.avatars
				template(v-for="speaker of session.speakers")
					img(v-if="speaker.avatar_thumbnail_tiny", :src="speaker.avatar_thumbnail_tiny")
					img(v-else-if="speaker.avatar_thumbnail_default", :src="speaker.avatar_thumbnail_default")
					img(v-else-if="speaker.avatar || speaker.avatar_url", :src="speaker.avatar || speaker.avatar_url")
			.names {{ session.speakers.map(s => s.name).join(', ') }}
		.do_not_record(v-if="session.do_not_record")
			svg(viewBox="0 0 116.59076 116.59076", width="24px", height="24px", fill="none", xmlns="http://www.w3.org/2000/svg")
				g(transform="translate(-9.3465481,-5.441411)")
					rect(style="fill:#000000;fill-opacity;stroke:none;stroke-width:11.2589;stroke-linecap:round;stroke-dasharray:none;stroke-opacity:1;paint-order:markers stroke fill", width="52.753284", height="39.619537", x="35.496307", y="43.927021", rx="5.5179553", ry="7.573648")
					path(style="fill:#000000;fill-opacity:1;stroke:none;stroke-width:18.7997;stroke-linecap:round;stroke-dasharray:none;stroke-opacity:1;paint-order:markers stroke fill", d="M 99.787546,47.04792 V 80.425654 L 77.727407,63.736793 Z")
					path(style="fill:none;stroke:#b23e65;stroke-width:12;stroke-linecap:round;stroke-dasharray:none;stroke-opacity:1;paint-order:markers stroke fill", d="m 35.553146,95.825578 64.177559,-64.17757 m 16.294055,32.08879 A 48.382828,48.382828 0 0 1 67.641925,112.11961 48.382828,48.382828 0 0 1 19.259099,63.736798 48.382828,48.382828 0 0 1 67.641925,15.353968 48.382828,48.382828 0 0 1 116.02476,63.736798 Z")
		.tags-box(v-if="showTags && session.tags && session.tags.length")
			.tags(v-for="tag_item of session.tags")
				.tag-item(:style="{'background-color': tag_item.color, 'color': getContrastColor(tag_item.color)}") {{ tag_item.tag }}
		.abstract(v-if="showAbstract", v-html="abstractText")
		.bottom-info
			.track(v-if="session.track") {{ getLocalizedString(session.track.name) }}
			.room(v-if="showRoom && session.room") {{ getLocalizedString(session.room.name) }}
		.fav-count(v-if="showFavCount && session.fav_count > 0") {{ session.fav_count > 99 ? "99+" : session.fav_count }}
	.stream-indicator(v-if="canOpenStream", :class="{live: isLive}", :title="streamTooltip", @click.prevent.stop="openStream")
		svg(viewBox="0 0 24 24", width="20", height="20", fill="currentColor", xmlns="http://www.w3.org/2000/svg")
			path(d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z")
	.session-icons
		fav-button(@toggleFav="toggleFav")

</template>
<script>
import MarkdownIt from 'markdown-it'
import { getLocalizedString, getPrettyDuration, getSessionTime, getContrastColor } from '../utils'
import FavButton from './FavButton.vue'

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
		showTags: {
			type: Boolean,
			default: false
		},
		showFavCount: {
			type: Boolean,
			default: false
		},
		showLiveBadge: {
			type: Boolean,
			default: true
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
		scheduleData: { default: null },
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
		},
		getJoinRoomLink: { default: () => () => '' },
		translationMessages: { default: () => ({}) }
	},
	components: {
		FavButton
	},
	data () {
		return {
			getPrettyDuration,
			getLocalizedString,
			getSessionTime,
			getContrastColor,
		}
	},
	computed: {
		effectiveNow () {
			return this.now ?? this.scheduleData?.now
		},
		effectiveTimezone () {
			return this.timezone ?? this.scheduleData?.timezone
		},
		effectiveHasAmPm () {
			// When timezone prop is explicitly passed, hasAmPm was also intentionally set
			if (this.timezone != null) return this.hasAmPm
			return this.scheduleData?.hasAmPm ?? this.hasAmPm
		},
		link () {
			return this.generateSessionLinkUrl({eventUrl: this.eventUrl, session: this.session})
		},
		style () {
			return {
				'--track-color': this.session.track?.color || 'var(--pretalx-clr-primary)'
			}
		},
		startTime () {
			return getSessionTime(this.session, this.effectiveTimezone, this.locale, this.effectiveHasAmPm)
		},
		shortDate () {
			return this.session.start.clone().tz(this.effectiveTimezone).format('MMM D')
		},
		isLive () {
			const now = this.effectiveNow
			return now && this.session.start < now && this.session.end > now
		},
		canOpenStream () {
			// Only show when the session is live and the backend indicates there's a stream scheduled.
			// Always link to the internal video room page (no external redirects).
			return this.isLive && !!this.session.stream_url && !!this.streamLink
		},
		streamLink () {
			const joinLink = this.getJoinRoomLink(this.session)
			return joinLink || ''
		},
		streamTooltip () {
			const m = this.translationMessages || {}
			return m.watch_live || m.watchLive || 'Watch live'
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
			if (this.faved) {
				this.$emit('unfav', this.session.id)
			} else {
				this.$emit('fav', this.session.id)
			}
		},
		openStream () {
			const link = this.streamLink
			if (link) {
				window.open(link, '_blank', 'noopener,noreferrer')
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
	margin: 8px 6px
	overflow: hidden
	color: rgb(13 15 16)
	position: relative
	font-size: 14px
	.time-box
		width: 62px
		box-sizing: border-box
		background-color: var(--track-color)
		padding: 10px 8px 6px 8px
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
				font-size: 13px
				font-weight: 500
				text-transform: uppercase
				letter-spacing: 0.3px
			display: flex
			flex-direction: column
			align-items: center
			text-align: center
			&.has-ampm
				align-self: stretch
			.ampm
				font-weight: 400
				font-size: 13px
			.duration
				font-weight: 400
				font-size: 13px
				color: $clr-secondary-text-dark
				margin-top: 2px
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
	&.has-date
		.time-box
			width: 88px
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
		.fav-count
			border: 1px solid
			border-radius: 50%
			position: absolute
			top: 5px
			right: 40px
			width: 25px
			height: 25px
			display: flex
			justify-content: center
			align-items: center
			text-align: center
			background-color: var(--track-color)
			color: $clr-primary-text-dark
	.do_not_record
		margin: 10px 0px
	.tags-box
		display: flex
		flex-wrap: wrap
		margin: 5px 0px
		.tags
			margin: 0px 2px
			.tag-item
				padding: 3px
				border-radius: 3px
				font-size: 12px
	.stream-indicator
		position: absolute
		right: 6px
		top: 50%
		transform: translateY(-50%)
		width: 32px
		height: 32px
		display: flex
		align-items: center
		justify-content: center
		border-radius: 50%
		background-color: var(--track-color)
		color: $clr-primary-text-dark
		cursor: pointer
		z-index: 20
		box-shadow: 0 2px 6px rgba(0,0,0,0.25)
		transition: transform 0.15s ease, background-color 0.15s ease
		&.live
			background-color: $clr-danger
		&:hover
			transform: translateY(-50%) scale(1.15)
	svg
			pointer-events: none
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

@media (max-width: 600px)
	.c-linear-schedule-session, .break
		min-width: 0
		margin: 6px 4px
		min-height: 80px
		.time-box
			width: 56px
			padding: 8px 6px
			.start
				font-size: 14px
		.info
			padding: 6px
			.title
				font-size: 14px
			.abstract
				-webkit-line-clamp: 2
			.bottom-info
				font-size: 12px
	.c-linear-schedule-session.has-date
		.time-box
			width: 76px
</style>

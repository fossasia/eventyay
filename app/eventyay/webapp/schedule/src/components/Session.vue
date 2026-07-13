<template lang="pug">
a.c-linear-schedule-session(:class="{faved, 'has-date': showDate, 'short-session': isShortSession, 'grid-very-short': isGridVeryShort, 'schedule-pending-session': isSchedulePending, 'has-fav-count': hasFavCount}", :style="style", :href="link", @click="onSessionLinkClick($event, session)", :target="linkTarget")
	.time-box
		.start.schedule-pending(v-if="isSchedulePending")
			svg.schedule-pending-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2", stroke-linecap="round", stroke-linejoin="round", aria-hidden="true")
				rect(x="3", y="4", width="18", height="18", rx="2", ry="2")
				line(x1="16", y1="2", x2="16", y2="6")
				line(x1="8", y1="2", x2="8", y2="6")
				line(x1="3", y1="10", x2="21", y2="10")
			.schedule-pending-label
				span.schedule-pending-text {{ schedulePendingText }}
		template(v-else)
			.start(:class="{'has-ampm': hasAmPm}")
				.date(v-if="showDate")
					.weekday {{ weekdayLabel }}
					.day-month {{ dayMonthLabel }}
				.time {{ startTime.time }}
				.ampm(v-if="startTime.ampm") {{ startTime.ampm }}
				.duration {{ getPrettyDuration(session.start, session.end) }}
		.buffer(v-if="!isSchedulePending")
		.is-live(v-if="showLiveBadge && isLive") live
	.info(:class="{'has-icons': hasAnyRightIcons, 'grid-session-info': showSessionType, 'has-bottom-icons': hasBottomIcons}", :style="bottomIconsPaddingStyle")
		template(v-if="showSessionType")
			.title(:class="gridTitleClampClass", :title="gridMetaTitle(getLocalizedString(session.title))") {{ getLocalizedString(session.title) }}
			.session-type(v-if="sessionTypeLabel", :class="{'single-line-clamped': isGridVeryShort}", :title="gridMetaTitle(sessionTypeLabel)") {{ sessionTypeLabel }}
		template(v-else)
			.title(:class="{'title-clamped': isShortSession}") {{ getLocalizedString(session.title) }}
		.speakers-row(v-if="namedSpeakers.length")
			.speakers(
				ref="speakersRow",
				:class="{'names-clamped': isShortSession}",
				:aria-label="speakersAriaLabel")
				span.speaker(v-for="(speaker, i) of namedSpeakers", :key="speaker.code || i")
					img(
						v-if="speaker.avatar_thumbnail_tiny || speaker.avatar_thumbnail_default || speaker.avatar || speaker.avatar_url",
						:src="speaker.avatar_thumbnail_tiny || speaker.avatar_thumbnail_default || speaker.avatar || speaker.avatar_url",
						alt="",
						aria-hidden="true")
					span.speaker-label {{ speaker.name }}
					span.speaker-separator(v-if="i + 1 < namedSpeakers.length", aria-hidden="true") ,
			span.speakers-overflow-hint(
				v-if="speakersHiddenCount > 0",
				:aria-label="speakersOverflowLabel") {{ speakersOverflowHint }}
		.tags-box(v-if="showTags && session.tags && session.tags.length")
			.tags(v-for="tag_item of session.tags")
				.tag-item(:style="{'background-color': tag_item.color, 'color': getContrastColor(tag_item.color)}") {{ tag_item.tag }}
		.abstract(v-if="showAbstract", v-html="abstractText")
		.bottom-info
			.track(v-if="session.track", :class="{'single-line-clamped': isGridVeryShort}", :title="gridMetaTitle(getLocalizedString(session.track.name))") {{ getLocalizedString(session.track.name) }}
			.room(v-if="showRoom && session.room", :title="getLocalizedString(session.room.name)") {{ getLocalizedString(session.room.name) }}
		.session-bottom-icons(v-if="hasBottomIcons")
			.interpretation(v-if="showRoomInterpretation", :title="roomInterpretationTooltip", :aria-label="roomInterpretationTooltip")
				svg.globe-icon(viewBox="0 0 24 24", width="18", height="18", fill="currentColor", xmlns="http://www.w3.org/2000/svg", aria-hidden="true")
					path(d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z")
			.do_not_record(v-if="session.do_not_record", :title="doNotRecordTooltip", :aria-label="doNotRecordTooltip")
				svg(viewBox="0 0 116.59076 116.59076", width="24px", height="24px", fill="none", xmlns="http://www.w3.org/2000/svg", aria-hidden="true")
					g(transform="translate(-9.3465481,-5.441411)")
						rect(style="fill:#000000;fill-opacity;stroke:none;stroke-width:11.2589;stroke-linecap:round;stroke-dasharray:none;stroke-opacity:1;paint-order:markers stroke fill", width="52.753284", height="39.619537", x="35.496307", y="43.927021", rx="5.5179553", ry="7.573648")
						path(style="fill:#000000;fill-opacity:1;stroke:none;stroke-width:18.7997;stroke-linecap:round;stroke-dasharray:none;stroke-opacity:1;paint-order:markers stroke fill", d="M 99.787546,47.04792 V 80.425654 L 77.727407,63.736793 Z")
						path(style="fill:none;stroke:#b23e65;stroke-width:12;stroke-linecap:round;stroke-dasharray:none;stroke-opacity:1;paint-order:markers stroke fill", d="m 35.553146,95.825578 64.177559,-64.17757 m 16.294055,32.08879 A 48.382828,48.382828 0 0 1 67.641925,112.11961 48.382828,48.382828 0 0 1 19.259099,63.736798 48.382828,48.382828 0 0 1 67.641925,15.353968 48.382828,48.382828 0 0 1 116.02476,63.736798 Z")
	span.fav-count(v-if="hasFavCount", :aria-label="favCountLabel") {{ favCountLabel }}
	.stream-indicator(v-if="canOpenStream", :class="{live: isLive}", :title="streamTooltip", @click.prevent.stop="openStream")
		svg(viewBox="0 0 24 24", width="20", height="20", fill="currentColor", xmlns="http://www.w3.org/2000/svg")
			path(d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z")
	.session-icons(v-if="!favsReadOnly")
		fav-button(@toggleFav="toggleFav")

</template>
<script>
import MarkdownIt from 'markdown-it'
import { getLocalizedString, getPrettyDuration, getSessionTime, getContrastColor, normalizePopularityCount, getSessionTypeLabel } from '../utils'
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
		showSessionType: {
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
		favsReadOnly: { default: false },
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
			speakersHiddenCount: 0,
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
			if (this.isSchedulePending) {
				return { time: this.schedulePendingText }
			}
			return getSessionTime(this.session, this.effectiveTimezone, this.locale, this.effectiveHasAmPm)
		},
		isSchedulePending () {
			return Boolean(this.session.schedule_pending || !this.session.start)
		},
		schedulePendingText () {
			const m = this.translationMessages || {}
			return m.schedule_pending_secondary || 'Coming soon'
		},
		weekdayLabel () {
			return this.session.start.clone().tz(this.effectiveTimezone).locale(this.locale || 'en').format('ddd')
		},
		dayMonthLabel () {
			return this.session.start.clone().tz(this.effectiveTimezone).locale(this.locale || 'en').format('D MMM')
		},
		isLive () {
			const now = this.effectiveNow
			return now && this.session.start < now && this.session.end > now
		},
		canOpenStream () {
			// Only show when the session is live and the backend indicates there's a stream scheduled
			// or the room itself has video modules enabled.
			// Always link to the internal video room page (no external redirects).
			return this.isLive && (!!this.session.stream_url || !!this.session.has_video_room) && !!this.streamLink
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
		},
		hasFavCount () {
			return this.showFavCount && normalizePopularityCount(this.session) > 0
		},
		favCountLabel () {
			const count = normalizePopularityCount(this.session)
			return String(count)
		},
		doNotRecordTooltip () {
			const m = this.translationMessages || {}
			return m.schedule_do_not_record || 'This session will not be recorded.'
		},
		roomInterpretationTooltip () {
			const m = this.translationMessages || {}
			return m.schedule_room_has_interpretation || 'This room has live interpretation.'
		},
		showRoomInterpretation () {
			return Boolean(this.session.room?.has_interpretation)
		},
		hasBottomIcons () {
			return this.showRoomInterpretation || this.session.do_not_record
		},
		bottomIconsPaddingStyle () {
			if (!this.hasBottomIcons) return {}
			const count = (this.showRoomInterpretation ? 1 : 0) + (this.session.do_not_record ? 1 : 0)
			return { '--session-bottom-icons-width': `${count * 32}px` }
		},
		sessionTypeLabel () {
			return getSessionTypeLabel(this.session.session_type)
		},
		hasAnyRightIcons () {
			return !this.favsReadOnly || this.canOpenStream || this.session.do_not_record
		},
		isShortSession () {
			const minutes = this.sessionDurationMinutes
			return minutes > 0 && minutes <= 15
		},
		isGridVeryShort () {
			return this.showSessionType && this.isVeryShortSession
		},
		gridTitleClampClass () {
			if (!this.isGridVeryShort) {
				return {}
			}
			return { 'single-line-clamped': true }
		},
		sessionDurationMinutes () {
			if (this.session.duration) {
				return Number(this.session.duration)
			}
			if (this.session.start && this.session.end?.diff) {
				return Math.round(this.session.end.diff(this.session.start, 'minutes', true))
			}
			return 0
		},
		isVeryShortSession () {
			const minutes = this.sessionDurationMinutes
			return minutes > 0 && minutes <= 10
		},
		namedSpeakers () {
			return (this.session.speakers || []).filter(s => (s.name || '').trim())
		},
		speakersAriaLabel () {
			return this.namedSpeakers.map(speaker => speaker.name).join(', ')
		},
		speakersOverflowHint () {
			if (!this.speakersHiddenCount) return ''
			const m = this.translationMessages || {}
			const template = m.schedule_speakers_overflow_hint || '+%(count)s more'
			return template.replace('%(count)s', this.speakersHiddenCount)
		},
		speakersOverflowLabel () {
			if (!this.speakersHiddenCount) return ''
			const m = this.translationMessages || {}
			const template = m.schedule_speakers_overflow_label || '+%(count)s more speakers'
			return template.replace('%(count)s', this.speakersHiddenCount)
		}
	},
	watch: {
		namedSpeakers () {
			this.$nextTick(() => this.updateSpeakersOverflow())
		},
		isShortSession () {
			this.$nextTick(() => this.setupSpeakersOverflowObserver())
		}
	},
	mounted () {
		this.$nextTick(() => this.setupSpeakersOverflowObserver())
	},
	beforeUnmount () {
		this._speakersResizeObserver?.disconnect?.()
	},
	methods: {
		gridMetaTitle (text) {
			if (!this.isGridVeryShort || !text) return null
			return text
		},
		toggleFav () {
			if (this.favsReadOnly) return
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
		},
		setupSpeakersOverflowObserver () {
			this._speakersResizeObserver?.disconnect?.()
			if (!this.isShortSession) {
				if (this.speakersHiddenCount !== 0) {
					this.speakersHiddenCount = 0
				}
				return
			}
			const row = this.$refs.speakersRow
			if (!row || typeof ResizeObserver === 'undefined') {
				this.updateSpeakersOverflow()
				return
			}
			this._speakersResizeObserver = new ResizeObserver(() => {
				this.updateSpeakersOverflow()
			})
			this._speakersResizeObserver.observe(row)
			this.updateSpeakersOverflow()
		},
		updateSpeakersOverflow () {
			const row = this.$refs.speakersRow
			if (!row || !this.isShortSession || !this.namedSpeakers.length) {
				if (this.speakersHiddenCount !== 0) {
					this.speakersHiddenCount = 0
				}
				return
			}
			const rowRect = row.getBoundingClientRect()
			let visible = 0
			for (const el of row.querySelectorAll('.speaker')) {
				const rect = el.getBoundingClientRect()
				if (rect.bottom <= rowRect.bottom + 1 && rect.top >= rowRect.top - 1 && rect.left < rowRect.right) {
					visible += 1
				}
			}
			visible = Math.min(visible, this.namedSpeakers.length)
			const hidden = Math.max(0, this.namedSpeakers.length - visible)
			if (hidden !== this.speakersHiddenCount) {
				this.speakersHiddenCount = hidden
			}
		}
	}
}
</script>
<style lang="stylus">
sessionTextClamp(lines)
	min-width: 0
	display: -webkit-box
	-webkit-line-clamp: lines
	line-clamp: lines
	-webkit-box-orient: vertical
	overflow: hidden
	overflow-wrap: break-word
	overflow-wrap: anywhere
	word-break: break-word
	text-overflow: ellipsis

sessionTextExpand()
	display: block
	-webkit-line-clamp: unset
	line-clamp: unset
	-webkit-box-orient: unset
	overflow: hidden
	white-space: normal
	overflow-wrap: break-word
	overflow-wrap: anywhere
	word-break: break-word
	text-overflow: clip

sessionMetaClamp()
	min-width: 0
	max-width: 100%
	width: 100%
	flex: 0 1 auto
	display: block
	overflow: hidden
	white-space: nowrap
	text-overflow: ellipsis
	overflow-wrap: normal
	word-break: normal

sessionMetaExpand()
	white-space: normal
	overflow: visible
	text-overflow: clip
	overflow-wrap: anywhere
	word-break: break-word
	max-width: none
	width: auto
	flex: 1 1 100%

expandGridVeryShortSession()
	z-index: 20
	.info.grid-session-info
		overflow: visible
		.bottom-info
			overflow: visible
			align-items: flex-start
			align-content: flex-start
		.single-line-clamped
			sessionMetaExpand()

expandClampedSessionText()
	.title.title-clamped
		sessionTextExpand()
	.single-line-clamped
		sessionMetaExpand()
	.speakers.names-clamped
		max-height: none
		overflow: visible
	.speakers-overflow-hint
		display: none

.c-linear-schedule-session, .break
	z-index: 10
	display: flex
	align-items: stretch
	min-width: 300px
	min-height: 96px
	margin: 8px 0
	margin-right: 8px
	overflow: hidden
	color: rgb(13 15 16)
	position: relative
	font-size: 14px
	.time-box
		width: 64px
		flex-shrink: 0
		box-sizing: border-box
		background-color: var(--track-color)
		padding: 10px 4px 6px 4px
		border-radius: 6px 0 0 6px
		display: flex
		flex-direction: column
		align-items: center
		.start.schedule-pending
			display: flex
			flex-direction: column
			align-items: center
			justify-content: center
			gap: 4px
			width: 100%
			margin-bottom: 0
			flex: 1
			color: $clr-primary-text-dark
			.schedule-pending-icon
				width: 16px
				height: 16px
				opacity: 0.9
				flex-shrink: 0
			.schedule-pending-label
				display: flex
				flex-direction: column
				align-items: center
				width: 100%
			.schedule-pending-text
				font-size: 11px
				font-weight: 600
				line-height: 1.25
				text-align: center
				letter-spacing: 0.02em
				color: $clr-primary-text-dark
				max-width: 100%
				word-break: break-word
		.start
			color: $clr-primary-text-dark
			display: flex
			flex-direction: column
			align-items: center
			text-align: center
			width: 100%
			&.has-ampm
				align-self: stretch
			.date
				display: inline-flex
				flex-direction: column
				align-items: center
				justify-content: center
				background-color: rgba(255, 255, 255, 0.18)
				color: rgba(255, 255, 255, 0.95)
				border-radius: 6px
				padding: 4px 6px
				margin-bottom: 6px
				max-width: 100%
				box-sizing: border-box
				text-align: center
				.weekday
					font-size: 10px
					font-weight: 700
					text-transform: uppercase
					letter-spacing: 0.5px
					line-height: 1
				.day-month
					font-size: 11px
					font-weight: 600
					text-transform: uppercase
					letter-spacing: 0.3px
					line-height: 1
					margin-top: 2px
			.time
				font-size: 14px
				font-weight: 700
				line-height: 1.2
			.ampm
				font-weight: 400
				font-size: 10px
				margin-top: 1px
				opacity: 0.85
				text-transform: uppercase
			.duration
				font-weight: 400
				font-size: 11px
				color: rgba(255, 255, 255, 0.7)
				margin-top: 4px
		.buffer
			flex: auto
		.is-live
			align-self: stretch
			text-align: center
			font-weight: 600
			padding: 2px 4px
			border-radius: 4px
			margin: 0 -8px 0 -4px // HACK
			background-color: $clr-danger
			color: $clr-primary-text-dark
			letter-spacing: 0.5px
			text-transform: uppercase
	&.schedule-pending-session
		.time-box
			justify-content: center
	&.has-date
		.time-box
			width: 88px
	.info
		position: relative
		flex: auto
		display: flex
		flex-direction: column
		padding: 8px
		padding-right: 8px
		&.has-icons
			padding-right: 44px
		border: border-separator()
		border-left: none
		border-radius: 0 6px 6px 0
		background-color: $clr-white
		min-width: 0
		.title
			font-size: 16px
			font-weight: 500
			margin-bottom: 4px
			margin-right: 0
			&.title-clamped
				sessionTextClamp(2)
		.single-line-clamped
			sessionMetaClamp()
		.session-type
			font-size: 12px
			font-weight: 600
			text-transform: uppercase
			letter-spacing: 0.04em
			color: $clr-secondary-text-light
			margin-bottom: 2px
			display: block
			min-width: 0
			max-width: 100%
			&:not(.single-line-clamped)
				white-space: normal
				overflow-wrap: anywhere
				word-break: break-word
		.speakers-row
			display: flex
			align-items: center
			gap: 4px
			min-width: 0
			.speakers-overflow-hint
				flex: 0 0 auto
				white-space: nowrap
				font-size: 12px
				color: $clr-secondary-text-light
				font-weight: 500
		.speakers
			--session-speaker-line-height: 24px
			--session-speaker-avatar-size: 24px
			color: $clr-secondary-text-light
			display: flex
			flex-flow: row wrap
			align-items: center
			align-content: flex-start
			gap: 0 6px
			flex: 1 1 auto
			min-width: 0
			line-height: var(--session-speaker-line-height)
			word-break: normal
			overflow-wrap: normal
			.speaker
				display: inline-flex
				align-items: center
				flex: 0 0 auto
				max-width: 100%
				white-space: nowrap
				overflow-wrap: normal
				img
					background-color: $clr-white
					border-radius: 50%
					height: var(--session-speaker-avatar-size)
					width: var(--session-speaker-avatar-size)
					margin: 0 6px 0 0
					object-fit: cover
					flex: 0 0 auto
				.speaker-label
					min-width: 0
					overflow: hidden
					text-overflow: ellipsis
					white-space: nowrap
				.speaker-separator
					flex: 0 0 auto
					white-space: nowrap
			&.names-clamped
				max-height: var(--session-speaker-line-height)
				overflow: hidden
		.abstract
			margin: 8px 0 12px 0
			// TODO make this take up more space if available?
			sessionTextClamp(3)
		.bottom-info
			flex: auto
			display: flex
			align-items: flex-end
			gap: 4px
			min-width: 0
			overflow: hidden
			.track
				flex: 1 1 0%
				min-width: 0
				color: var(--track-color)
				&:not(.single-line-clamped)
					ellipsis()
				&.single-line-clamped
					sessionMetaClamp()
			.room
				flex: 1
				min-width: 0
				text-align: right
				color: $clr-secondary-text-light
				white-space: nowrap
				overflow: hidden
				text-overflow: ellipsis
		&.has-bottom-icons .bottom-info
			padding-right: var(--session-bottom-icons-width, 32px)
		.session-bottom-icons
			position: absolute
			right: 2px
			bottom: 2px
			display: flex
			align-items: center
			z-index: 5
			.interpretation, .do_not_record
				width: 32px
				height: 32px
				display: flex
				justify-content: center
				align-items: center
				line-height: 0
				flex-shrink: 0
				pointer-events: auto
				cursor: help
				svg
					pointer-events: none
			.interpretation
				color: $clr-secondary-text-light
				.globe-icon
					display: block
		&.grid-session-info
			min-width: 0
			overflow: hidden
			.bottom-info .track:not(.single-line-clamped)
				display: block
				flex: 1 1 auto
				white-space: normal
				overflow: visible
				text-overflow: clip
				overflow-wrap: anywhere
				word-break: break-word
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
	.fav-count
		position: absolute
		top: 10px
		right: 38px
		z-index: 25
		display: inline-flex
		align-items: center
		justify-content: center
		min-width: 20px
		height: 18px
		padding: 0 6px
		border-radius: 999px
		font-size: 10px
		font-weight: 700
		line-height: 1
		letter-spacing: 0.02em
		white-space: nowrap
		color: var(--track-color)
		background-color: unquote('color-mix(in srgb, var(--track-color) 16%, transparent)')
		border: 1px solid unquote('color-mix(in srgb, var(--track-color) 32%, transparent)')
		box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08)
		pointer-events: none
	.session-icons
		position: absolute
		top: 2px
		right: 2px
		display: flex
		.btn-fav-container
			margin-top: 2px
			display: inline-flex
			icon-button-style(style: clear)
			padding: 2px
			width: 32px
			height: 32px
	&.has-fav-count
		.info.has-icons
			padding-right: 68px
	&.grid-very-short
		position: relative
	&:hover
		.info
			border: 1px solid var(--track-color)
			border-left: none
			.title
				color: var(--pretalx-clr-primary)
	&:focus-visible
		expandClampedSessionText()
	@media (hover: hover) and (pointer: fine)
		&:hover
			expandClampedSessionText()
		&.grid-very-short:hover
			expandGridVeryShortSession()
@media(hover: none)
	.c-linear-schedule-session .session-icons .btn-fav-container
		display: inline-flex

@media (max-width: 600px)
	.c-linear-schedule-session, .break
		min-width: 0
		margin: 8px 0
		margin-right: 8px
		min-height: 80px
		.time-box
			width: 58px
			padding: 8px 6px 6px 2px
			.start
				.date
					padding: 3px 5px
					margin-bottom: 4px
					border-radius: 5px
					.weekday
						font-size: 9px
					.day-month
						font-size: 10px
				.time
					font-size: 13px
				.ampm
					font-size: 9px
				.duration
					font-size: 10px
		.info
			padding: 6px
			padding-right: 6px
			&.has-icons
				padding-right: 40px
			.title
				font-size: 14px
			.abstract
				sessionTextClamp(2)
			.bottom-info
				font-size: 12px
		&.has-fav-count .info.has-icons
			padding-right: 62px
		.fav-count
			top: 8px
			right: 34px
			height: 16px
			min-width: 18px
			padding: 0 5px
			font-size: 9px

.density-compact .c-linear-schedule-session,
.density-compact .break
	min-height: 64px
	margin: 4px 4px
	font-size: 12px
	.time-box
		width: 56px
		padding: 6px 4px 4px 4px
		.start
			.date
				padding: 3px 4px
				margin-bottom: 4px
				border-radius: 5px
				.weekday
					font-size: 9px
				.day-month
					font-size: 10px
			.time
				font-size: 12px
			.ampm
				font-size: 9px
			.duration
				font-size: 10px
	.info
		padding: 4px
		padding-right: 4px
		&.has-icons
			padding-right: 36px
		.title
			font-size: 13px
		.speakers
			font-size: 12px
		.bottom-info
			font-size: 11px
	&.has-fav-count .info.has-icons
		padding-right: 60px

.density-comfortable .c-linear-schedule-session,
.density-comfortable .break
	min-height: 120px
	margin: 12px 8px
	font-size: 16px
	.time-box
		width: 72px
		padding: 14px 6px 8px 6px
		.start
			font-size: 16px
			margin-bottom: 10px
			.date
				padding: 5px 8px
				margin-bottom: 6px
				border-radius: 8px
				.weekday
					font-size: 11px
				.day-month
					font-size: 12px
			.time
				font-size: 16px
			.duration
				font-size: 13px
			.ampm
				font-size: 12px
	.info
		padding: 12px
		padding-right: 12px
		&.has-icons
			padding-right: 52px
		.title
			font-size: 18px
		.speakers
			font-size: 15px
		.bottom-info
			font-size: 14px
	&.has-fav-count .info.has-icons
		padding-right: 76px
</style>

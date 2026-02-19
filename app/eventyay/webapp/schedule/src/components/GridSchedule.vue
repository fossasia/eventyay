<template lang="pug">
.c-grid-schedule
	.sticky-header
		.rooms-bar(ref="roomsBar")
			.rooms-inner(:style="{'--total-rooms': rooms.length, 'min-width': scrollContentWidth ? (scrollContentWidth + 'px') : 'min-content'}")
				.room
				.room(v-for="(room, index) of rooms") {{ getLocalizedString(room.name) }}
					bunt-button.room-description(v-if="getLocalizedString(room.description)", :tooltip="getLocalizedString(room.description)", tooltip-placement="bottom-end") ?
				.room(v-if="hasSessionsWithoutRoom") no location
		.custom-scrollbar(ref="customScrollbar", v-show="scrollThumbWidth > 0 && scrollThumbWidth < 100")
			.scroll-track(ref="scrollTrack", @mousedown="onTrackClick")
				.scroll-thumb(ref="scrollThumb", :style="{'width': scrollThumbWidth + '%', 'left': scrollThumbLeft + '%'}", @mousedown.stop="onThumbMousedown")
	.grid-viewport(ref="gridViewport", @scroll="onViewportScroll")
		.grid(:style="gridStyle")
			template(v-for="slice of visibleTimeslices")
				.timeslice(:ref="slice.name", :class="getSliceClasses(slice)", :data-slice="slice.date.toISOString()", :style="getSliceStyle(slice)") {{ getSliceLabel(slice) }}
				.timeline(:class="getSliceClasses(slice)", :style="getSliceStyle(slice)")
			.now(v-if="nowSlice", ref="now", :class="{'on-daybreak': nowSlice.onDaybreak}", :style="{'grid-area': `${nowSlice.slice.name} / 1 / auto / auto`, '--offset': nowSlice.offset}")
				svg(viewBox="0 0 10 10")
					path(d="M 0 0 L 10 5 L 0 10 z")
			template(v-for="session of sessions")
				session(
					v-if="isProperSession(session)",
					:session="session",
					:now="now",
					:locale="locale",
					:timezone="timezone",
					:style="getSessionStyle(session)",
					:showAbstract="false", :showRoom="false",
					:faved="favs.includes(session.id)",
					:hasAmPm="hasAmPm",
					:onHomeServer="onHomeServer",
					@fav="$emit('fav', session.id)",
					@unfav="$emit('unfav', session.id)"
				)
				.break(v-else, :style="getSessionStyle(session)")
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
	.print-grids
		template(v-for="(chunk, chunkIdx) of printRoomChunks", :key="chunkIdx")
			.print-chunk
				.print-rooms-bar(:style="{'--total-rooms': chunk.length}")
					.room
					.room(v-for="room of chunk") {{ getLocalizedString(room.name) }}
				.print-grid(:style="getPrintChunkGridStyle(chunk)")
					template(v-for="slice of visibleTimeslices")
						.timeslice(:class="getSliceClasses(slice)", :style="getSliceStyle(slice)") {{ getSliceLabel(slice) }}
						.timeline(:class="getSliceClasses(slice)", :style="getSliceStyle(slice)")
					template(v-for="session of getChunkSessions(chunk)")
						session(
							v-if="isProperSession(session)",
							:session="session",
							:now="now",
							:locale="locale",
							:timezone="timezone",
							:style="getChunkSessionStyle(session, chunk)",
							:showAbstract="false", :showRoom="false",
							:faved="favs.includes(session.id)",
							:hasAmPm="hasAmPm",
							:onHomeServer="onHomeServer",
							@fav="$emit('fav', session.id)",
							@unfav="$emit('unfav', session.id)"
						)
						.break(v-else, :style="getChunkSessionStyle(session, chunk)")
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
// TODO
// - handle click on already selected day (needs some buntpapier hacking)
// - optionally only show venueless rooms
import moment from 'moment-timezone'
import Session from './Session'
import { getLocalizedString, getPrettyDuration } from '../utils'

const getSliceName = function (date) {
	return `slice-${date.format('MM-DD-HH-mm')}`
}

export default {
	components: { Session },
	props: {
		sessions: Array,
		rooms: Array,
		favs: {
			type: Array,
			default () {
				return []
			}
		},
		currentDay: String,
		forceScrollDay: { type: Number, default: 0 },
		now: Object,
		timezone: String,
		locale: String,
		hasAmPm: Boolean,
		scrollParent: Element,
		onHomeServer: Boolean,
		disableAutoScroll: Boolean
	},
	data () {
		return {
			getLocalizedString,
			getPrettyDuration,
			scrollContentWidth: 0,
			scrollThumbWidth: 100,
			scrollThumbLeft: 0,
			_scrollSource: null,
			_thumbDrag: null
		}
	},
	computed: {
		hasSessionsWithoutRoom () {
			return this.sessions.some(s => !s.room)
		},
		printRoomChunks () {
			const chunkSize = 4
			const chunks = []
			for (let i = 0; i < this.rooms.length; i += chunkSize) {
				chunks.push(this.rooms.slice(i, i + chunkSize))
			}
			return chunks.length ? chunks : [this.rooms]
		},
		timeslices () {
			const minimumSliceMins = 30
			const slices = []
			const slicesLookup = {}
			const pushSlice = function (date, {hasSession = false, hasBreak = false, hasStart = false, hasEnd = false} = {}) {
				const name = getSliceName(date)
				let slice = slicesLookup[name]
				if (slice) {
					slice.hasSession = slice.hasSession || hasSession
					slice.hasBreak = slice.hasBreak || hasBreak
					slice.hasStart = slice.hasStart || hasStart
					slice.hasEnd = slice.hasEnd || hasEnd
				} else {
					slice = {
						date,
						name,
						hasSession,
						hasBreak,
						hasStart,
						hasEnd,
						datebreak: date.valueOf() === date.clone().startOf('day').valueOf()
					}
					slices.push(slice)
					slicesLookup[name] = slice
				}
			}
			const fillHalfHours = function (start, end, {hasSession, hasBreak} = {}) {
				// fill to the nearest half hour, then each half hour, then fill to end
				let mins = end.diff(start, 'minutes')
				const startingMins = minimumSliceMins - start.minute() % minimumSliceMins
				// buffer slices because we need to remove hasSession from the last one
				const halfHourSlices = []
				if (startingMins) {
					halfHourSlices.push(start.clone().add(startingMins, 'minutes'))
					mins -= startingMins
				}
				const endingMins = end.minute() % minimumSliceMins
				for (let i = 1; i <= mins / minimumSliceMins; i++) {
					halfHourSlices.push(start.clone().add(startingMins + minimumSliceMins * i, 'minutes'))
				}

				if (endingMins) {
					halfHourSlices.push(end.clone().subtract(endingMins, 'minutes'))
				}

				// last slice is actually just after the end of the session and has no session
				const lastSlice = halfHourSlices.pop()
				halfHourSlices.forEach(slice => pushSlice(slice, {hasSession, hasBreak}))
				pushSlice(lastSlice)
			}
			for (const session of this.sessions) {
				const lastSlice = slices[slices.length - 1]
				// gap to last slice
				if (!lastSlice) {
					pushSlice(session.start.clone().startOf('day'))
				} else if (session.start.isAfter(lastSlice.date)) {
					fillHalfHours(lastSlice.date, session.start)
				}

				const isProper = this.isProperSession(session)
				// add start and end slices for the session itself
				pushSlice(session.start, {hasSession: isProper, hasBreak: !isProper, hasStart: true})
				pushSlice(session.end, {hasEnd: true})
				// add half hour slices between a session
				fillHalfHours(session.start, session.end, {hasSession: isProper, hasBreak: !isProper})
			}

			const sliceIsFraction = function (slice) {
				if (!slice) return
				return slice.date.minute() !== 0 && slice.date.minute() !== minimumSliceMins
			}

			const sliceShouldDisplay = function (slice, index) {
				if (!slice) return
				// keep slices with sessions or when changing dates, or when sessions start or immediately after they end
				if (slice.hasSession || slice.datebreak || slice.hasStart || slice.hasEnd) return true
				const prevSlice = slices[index - 1]
				const nextSlice = slices[index + 1]

				// keep non-whole slices
				if (sliceIsFraction(slice)) return true
				// keep slices before and after non-whole slices, if by session or break
				if (
					((prevSlice?.hasSession || prevSlice?.hasBreak || prevSlice?.hasEnd) && sliceIsFraction(prevSlice)) ||
					((nextSlice?.hasSession || nextSlice?.hasBreak) && sliceIsFraction(nextSlice)) ||
					((!nextSlice?.hasSession || !nextSlice?.hasBreak) && (slice.hasSession || slice.hasBreak) && sliceIsFraction(nextSlice))
				) return true
				// but drop slices inside breaks
				if (prevSlice?.hasBreak && slice.hasBreak) return false
				return false
			}

			slices.sort((a, b) => a.date.diff(b.date))
			// remove empty gaps in slices
			const compactedSlices = []
			for (const [index, slice] of slices.entries()) {
				if (sliceShouldDisplay(slice, index)) {
					compactedSlices.push(slice)
					continue
				}
				// make the previous slice a gap slice if this one would be the first to be removed
				// but only if it isn't the start of the day
				const prevSlice = slices[index - 1]
				if (sliceShouldDisplay(prevSlice, index - 1) && !prevSlice.datebreak) {
					prevSlice.gap = true
				}
			}
			// Only count slice as gap if it is longer than 30 minutes
			compactedSlices.forEach((slice, index) => {
				if (slice.gap && index < compactedSlices.length - 1) {
					if (compactedSlices[index + 1].date.diff(slice.date, 'minutes') <= 30) slice.gap = false
				}
			})
			// remove gap at the end of the schedule
			if (compactedSlices[compactedSlices.length - 1].gap) compactedSlices.pop()
			return compactedSlices
		},
		visibleTimeslices () {
			return this.timeslices.filter(slice => slice.date.minute() % 30 === 0)
		},
		gridStyle () {
			let rows = ''
			rows += this.timeslices.map((slice, index) => {
				const next = this.timeslices[index + 1]
				let height = 60
				if (slice.gap) {
					height = 100
			} else if (slice.datebreak) {
				height = 36
				} else if (next) {
					height = Math.min(60, next.date.diff(slice.date, 'minutes') * 2)
				}
				return `[${slice.name}] minmax(${height}px, auto)`
			}).join(' ')
			return {
				'--total-rooms': this.rooms.length,
				'grid-template-rows': rows
			}
		},
		nowSlice () {
			let slice
			for (const s of this.timeslices) {
				if (this.now.isBefore(s.date)) break
				slice = s
			}
			if (slice) {
				const nextSlice = this.timeslices[this.timeslices.indexOf(slice) + 1]
				if (!nextSlice) return null
				// is on daybreak
				if (nextSlice.date.diff(slice.date, 'minutes') > 30) return {
					slice: nextSlice,
					offset: 0,
					onDaybreak: true
				}
				return {
					slice,
					offset: this.now.diff(slice.date, 'minutes') / nextSlice.date.diff(slice.date, 'minutes')
				}
			}
			return null
		}
	},
	watch: {
		currentDay (day) {
			// Always scroll to the start of the selected day
			this.scrollToDayStart(day)
		},
		forceScrollDay () {
			this.scrollToDayStart(this.currentDay)
		}
	},
	async mounted () {
		this.observer = new IntersectionObserver(this.onIntersect, {
			root: this.scrollParent,
			rootMargin: '-45% 0px'
		})
		for (const [ref, el] of Object.entries(this.$refs)) {
			if (!ref.startsWith('slice') || !ref.endsWith('00-00')) continue
			this.observer.observe(el[0])
		}
		await this.$nextTick()
		this.initScrollSync()
		// scroll to now, unless URL overrides now
		let fragmentIsDate = false
		const fragment = window.location.hash.slice(1)
		if (fragment && fragment.length === 10) {
			const initialDay = moment.tz(fragment, this.timezone)
			if (initialDay.isValid()) {
				fragmentIsDate = true
			}
		}
		if (fragmentIsDate || !this.$refs.now) return
		// Skip auto-scroll if disabled via prop
		if (this.disableAutoScroll) return
		const clearance = this.getStickyHeaderClearance()
		const rect = this.$refs.now.getBoundingClientRect()
		if (this.scrollParent) {
			this.scrollParent.scrollTop += rect.top - clearance
		} else {
			window.scrollBy({top: rect.top - clearance})
		}
	},
	beforeUnmount () {
		if (this._gridResizeObserver) {
			this._gridResizeObserver.disconnect()
		}
	},
	methods: {
		isProperSession (session) {
			// breaks and such don't have ids
			return !!session.id
		},
		getChunkSessions (chunkRooms) {
			return this.sessions.filter(s => {
				if (!this.isProperSession(s)) {
					return !s.room || chunkRooms.includes(s.room)
				}
				return chunkRooms.includes(s.room)
			})
		},
		getChunkSessionStyle (session, chunkRooms) {
			const roomIndex = chunkRooms.indexOf(session.room)
			const gridRow = `${getSliceName(session.start)} / ${getSliceName(session.end)}`
			if (roomIndex > -1) {
				return { 'grid-row': gridRow, 'grid-column': roomIndex + 2 }
			}
			return { 'grid-row': gridRow, 'grid-column': `2 / ${chunkRooms.length + 2}` }
		},
		getPrintChunkGridStyle (chunk) {
			const rows = this.timeslices.map((slice, index) => {
				const next = this.timeslices[index + 1]
				let height = 60
				if (slice.gap) {
					height = 100
				} else if (slice.datebreak) {
					height = 36
				} else if (next) {
					height = Math.min(60, next.date.diff(slice.date, 'minutes') * 2)
				}
				return `[${slice.name}] minmax(${height}px, auto)`
			}).join(' ')
			return {
				'--total-rooms': chunk.length,
				'grid-template-rows': rows
			}
		},
		getSessionStyle (session) {
			const roomIndex = this.rooms.indexOf(session.room)
			return {
				'grid-row': `${getSliceName(session.start)} / ${getSliceName(session.end)}`,
				'grid-column': roomIndex > -1 ? roomIndex + 2 : null
			}
		},
		getStickyHeaderClearance () {
			const stickyHeader = this.$el.querySelector('.sticky-header')
			// 40px page header (when stuck) + 40px toolbar + rooms bar + scrollbar + buffer
			return 80 + (stickyHeader ? stickyHeader.offsetHeight : 0) + 10
		},
		getScrolledDay () {
			// go through all timeslices, on the first one that is actually visible in current scroll, return its date
			for (const slice of this.timeslices) {
				const el = this.$refs[slice.name]?.[0]
				if (!el) continue
				const rect = el.getBoundingClientRect()
				// only count as visible if at least 100px are visible
				const buffer = 100
				if (rect.top + buffer < window.innerHeight && rect.bottom - buffer > 0) {
					return slice.date
				}
			}
		},
		getSliceClasses (slice) {
			return {
				datebreak: slice.datebreak,
				gap: slice.gap
			}
		},
		getSliceStyle (slice) {
			if (slice.datebreak) {
				let index = this.timeslices.findIndex(s => s.date.clone().startOf('day').isAfter(slice.date.clone().startOf('day')))
				if (index < 0) {
					index = this.timeslices.length - 1
				}
				return {'grid-area': `${slice.name} / 1 / ${this.timeslices[index].name} / auto`}
			}
			return {'grid-area': `${slice.name} / 1 / auto / auto`}
		},
		getSliceLabel (slice) {
			if (slice.datebreak) {
				const date = slice.date
				return date.format('ddd') + '\n' + date.format('D MMM')
			}
			return slice.date.clone().tz(this.timezone).format('h:mm A')
		},
		changeDay (day) {
			this.scrollToDayStart(day)
		},
		scrollToDayStart (day) {
			const el = this.$refs[getSliceName(moment.tz(day, this.timezone))]?.[0]
			if (!el) return
			const clearance = this.getStickyHeaderClearance()
			const rect = el.getBoundingClientRect()
			if (this.scrollParent) {
				this.scrollParent.scrollTop += rect.top - clearance
			} else {
				window.scrollBy({top: rect.top - clearance})
			}
		},
		initScrollSync () {
			const viewport = this.$refs.gridViewport
			if (!viewport) return
			this.updateScrollbar()
			this._gridResizeObserver = new ResizeObserver(() => this.updateScrollbar())
			const grid = viewport.querySelector('.grid')
			if (grid) this._gridResizeObserver.observe(grid)
			setTimeout(() => this.updateScrollbar(), 200)
		},
		updateScrollbar () {
			const viewport = this.$refs.gridViewport
			if (!viewport) return
			this.scrollContentWidth = viewport.scrollWidth
			const ratio = viewport.clientWidth / viewport.scrollWidth
			this.scrollThumbWidth = Math.min(100, ratio * 100)
			const maxScroll = viewport.scrollWidth - viewport.clientWidth
			if (maxScroll > 0) {
				this.scrollThumbLeft = (viewport.scrollLeft / maxScroll) * (100 - this.scrollThumbWidth)
			} else {
				this.scrollThumbLeft = 0
			}
		},
		onViewportScroll () {
			if (this._scrollSource === 'thumb') return
			this._scrollSource = 'viewport'
			const viewport = this.$refs.gridViewport
			const roomsBar = this.$refs.roomsBar
			if (roomsBar) roomsBar.scrollLeft = viewport.scrollLeft
			this.updateScrollbar()
			requestAnimationFrame(() => { this._scrollSource = null })
		},
		onTrackClick (e) {
			const track = this.$refs.scrollTrack
			const viewport = this.$refs.gridViewport
			if (!track || !viewport) return
			const rect = track.getBoundingClientRect()
			const clickRatio = (e.clientX - rect.left) / rect.width
			const maxScroll = viewport.scrollWidth - viewport.clientWidth
			viewport.scrollLeft = clickRatio * maxScroll
			if (this.$refs.roomsBar) this.$refs.roomsBar.scrollLeft = viewport.scrollLeft
			this.updateScrollbar()
		},
		onThumbMousedown (e) {
			e.preventDefault()
			const track = this.$refs.scrollTrack
			const viewport = this.$refs.gridViewport
			if (!track || !viewport) return
			const trackRect = track.getBoundingClientRect()
			const startX = e.clientX
			const startScrollLeft = viewport.scrollLeft
			const maxScroll = viewport.scrollWidth - viewport.clientWidth
			const trackWidth = trackRect.width
			const thumbWidthPx = (this.scrollThumbWidth / 100) * trackWidth
			const scrollableTrack = trackWidth - thumbWidthPx

			const onMouseMove = (ev) => {
				this._scrollSource = 'thumb'
				const dx = ev.clientX - startX
				const scrollDelta = (dx / scrollableTrack) * maxScroll
				viewport.scrollLeft = startScrollLeft + scrollDelta
				if (this.$refs.roomsBar) this.$refs.roomsBar.scrollLeft = viewport.scrollLeft
				this.updateScrollbar()
			}
			const onMouseUp = () => {
				this._scrollSource = null
				document.removeEventListener('mousemove', onMouseMove)
				document.removeEventListener('mouseup', onMouseUp)
			}
			document.addEventListener('mousemove', onMouseMove)
			document.addEventListener('mouseup', onMouseUp)
		},
		onIntersect (entries) {
			// TODO still gets stuck when scrolling fast above threshold and back
			const entry = entries.sort((a, b) => b.ts - a.ts).find(entry => entry.isIntersecting)
			if (!entry) return
			const day = moment(entry.target.dataset.slice).startOf('day')
			if (day.format('YYYY-MM-DD') !== this.currentDay) {
				this.$emit('changeDay', day)
			}
		}
	}
}
</script>
<style lang="stylus">
.c-grid-schedule
	flex: auto
	background-color: $clr-grey-50
	.sticky-header
		position: sticky
		top: calc(var(--pretalx-sticky-top-offset, 0px) + 40px)
		z-index: 25
		background-color: $clr-white
	.rooms-bar
		overflow: hidden
		.rooms-inner
			display: grid
			grid-template-columns: 78px repeat(var(--total-rooms), 1fr) auto
			min-width: min-content
			> .room
				display: flex
				justify-content: center
				align-items: center
				font-size: 18px
				background-color: $clr-white
				padding: 8px 4px
				.room-description
					border: 2px solid $clr-grey-400
					border-radius: 100%
					height: 20px
					width: 20px
					padding: 0
					font-weight: bold
					min-width: 0
					button-style(color: $clr-white, text-color: $clr-grey-500)
					margin-left: 8px
					.bunt-tooltip
						height: auto
						width: 200px
						white-space: normal
	.custom-scrollbar
		padding: 0
		.scroll-track
			height: 3px
			background: rgba(0, 0, 0, 0.10)
			border-radius: 2px
			position: relative
			cursor: pointer
			.scroll-thumb
				position: absolute
				top: 50%
				transform: translateY(-50%)
				height: 5px
				background: var(--pretalx-clr-primary, #3b82f6)
				border-radius: 3px
				cursor: grab
				&:active
					cursor: grabbing
	.grid-viewport
		overflow-x: auto
		overflow-y: clip
		scrollbar-width: none
		&::-webkit-scrollbar
			display: none
		.grid
			display: grid
			grid-template-columns: 78px repeat(var(--total-rooms), 1fr) auto
			position: relative
			min-width: min-content
		.break
			.time-box
				background-color: $clr-grey-500
				.start
					color: $clr-primary-text-dark
				.duration
					color: $clr-secondary-text-dark
			.info
				background-color: $clr-grey-200
				border: none
				justify-content: center
				align-items: center
				.title
					font-size: 16px
					font-weight: 500
					color: $clr-secondary-text-light
					align: center
	.timeslice
		color: $clr-secondary-text-light
		padding: 8px 10px 0 16px
		white-space: nowrap
		position: sticky
		left: 0
		text-align: center
		background-color: $clr-grey-50
		border-top: 1px solid $clr-dividers-light
		z-index: 20
		&.datebreak
			font-weight: 800
			border-top: 3px solid $clr-dividers-light
			white-space: pre
			padding-top: 2px
			font-size: 13px
			line-height: 1.2
			overflow: hidden
			max-height: 100%
			align-content: start
		&.gap
			&::before
				content: ''
				display: block
				width: 6px
				height: calc(100% - 30px - 12px)
				position: absolute
				top: 30px
				left: 50%
				background-image: radial-gradient(circle closest-side, $clr-grey-500 calc(100% - .5px), transparent 100%)
				background-position: 0 0
				background-size: 5px 15px
				background-repeat: repeat-y

	.timeline
		height: 1px
		background-color: $clr-dividers-light
		position: absolute
		width: 100%
		&.datebreak
			height: 3px
	.now
		z-index: 20
		position: sticky
		left: 2px
		&::before
			content: ''
			display: block
			height: 2px
			background-color: $clr-red
			position: absolute
			top: calc(var(--offset) * 100%)
			width: 100%
		&.on-daybreak::before
			background: repeating-linear-gradient(to right, transparent, transparent 5px, $clr-red 5px, $clr-red 10px)
		svg
			position: absolute
			top: calc(var(--offset) * 100% - 11px)
			height: 24px
			width: 24px
			fill: $clr-red
	.bunt-scrollbar-rail-wrapper-x, .bunt-scrollbar-rail-wrapper-y
		z-index: 30
	.print-grids
		display: none

@media print
	.c-grid-schedule
		.sticky-header
			display: none !important
		.grid-viewport
			display: none !important
		.print-grids
			display: block !important
			.print-chunk
				break-inside: avoid
				page-break-inside: avoid
				&:not(:last-child)
					page-break-after: always
				.print-rooms-bar
					display: grid
					grid-template-columns: 78px repeat(var(--total-rooms), 1fr) auto
					.room
						text-align: center
						font-size: 16px
						font-weight: 600
						padding: 8px 4px
						border-bottom: 2px solid #ccc
				.print-grid
					display: grid
					grid-template-columns: 78px repeat(var(--total-rooms), 1fr) auto
					position: relative
					.break
						.time-box
							-webkit-print-color-adjust: exact
							print-color-adjust: exact
							color-adjust: exact
						.info
							-webkit-print-color-adjust: exact
							print-color-adjust: exact
							color-adjust: exact
</style>

<template lang="pug">
.c-linear-schedule(v-scrollbar.y="", :class="'density-' + density")
	.bucket(v-for="({date, sessions}, index) of sessionBuckets")
		.bucket-label(:ref="getBucketName(date)", :data-date="date.toISOString()")
			.day(v-if="showDayHeaders && (index === 0 || date.clone().startOf('day').diff(sessionBuckets[index - 1].date.clone().startOf('day'), 'days') > 0)")  {{ date.clone().tz(timezone).format('dddd, D MMMM') }}
			template(v-for="session of sessions")
				component(
					:is="SessionComponent",
					v-if="isProperSession(session)",
					:session="session",
					:now="now",
					:timezone="timezone",
					:locale="locale",
					:hasAmPm="hasAmPm",
					:showFavCount="showFavCount",
					:faved="session.id && favSet.has(session.id)",
					:onHomeServer="onHomeServer",
					:showDate="showsMultiDay",
					@fav="$emit('fav', session.id)",
					@unfav="$emit('unfav', session.id)"
				)
				.break(v-else-if="showBreaks")
					.title {{ getLocalizedString(session.title) }}
</template>
<script>
import moment from 'moment-timezone'
import { getLocalizedString, normalizePopularityCount } from '../utils'
import TalkSession from './Session'
import ShiftSession from '../teamshifts-adapter/Session.vue'
import { isShiftSchedule } from '../teamshifts-adapter'
import { getDayAtScrollPosition, updateDayEndSpace } from '../dayNavigation'

export default {
	components: { TalkSession, ShiftSession },
	inject: {
		scheduleData: { default: null },
	},
	props: {
		sessions: Array,
		rooms: Array,
		locale: String,
		hasAmPm: Boolean,
		timezone: String,
		showFavCount: {
			type: Boolean,
			default: false
		},
		favs: {
			type: Array,
			default () {
				return []
			}
		},
		currentDay: String,
		forceScrollDay: { type: Number, default: 0 },
		navigationDay: String,
		now: Object,
		scrollParent: Element,
		onHomeServer: Boolean,
		disableAutoScroll: Boolean,
		sortBy: {
			type: String,
			default: 'title',
			validator: v => ['title', 'title_desc', 'popularity'].includes(v)
		},
		includeRoomSortKey: {
			type: Boolean,
			default: false
		},
		includeDateSortKey: {
			type: Boolean,
			default: false
		},
		includePopularitySortKey: {
			type: Boolean,
			default: false
		},
		showBreaks: {
			type: Boolean,
			default: true
		},
		density: {
			type: String,
			default: 'default'
		}
	},
	data () {
		return {
			getLocalizedString,
			scrolledDay: null
		}
	},
	computed: {
		SessionComponent () {
			const data = this.scheduleData?.value ?? this.scheduleData
			return isShiftSchedule(data) ? ShiftSession : TalkSession
		},
		popularitySortEnabled () {
			return this.includePopularitySortKey || this.sortBy === 'popularity'
		},
		favSet () {
			return new Set(this.favs || [])
		},
		showsMultiDay () {
			return !this.includeDateSortKey
		},
		/** First session bucket per calendar day (for toolbar day jump without scanning all buckets). */
		bucketFirstByDay () {
			const map = Object.create(null)
			for (const b of this.sessionBuckets) {
				const k = b.date.format('YYYY-MM-DD')
				if (map[k] === undefined) map[k] = b
			}
			return map
		},
		showDayHeaders () {
			return this.includeDateSortKey
		},
		sessionBuckets () {
			if (!this.includeDateSortKey) {
				const sortedFlat = this.sortBucketSessions(this.sessions)
				const firstStart = sortedFlat.find(session => session.start)?.start
				const fallbackDate = firstStart ? firstStart.clone().startOf('day') : moment()
				return [{
					date: fallbackDate,
					sessions: sortedFlat
				}]
			}

			const buckets = {}
			const seenBreakIds = {}
			const pendingSessions = []
			for (const session of this.sessions) {
				if (!session.start) {
					if (session.id) pendingSessions.push(session)
					continue
				}
				const key = this.getBucketName(session.start)
				if (!buckets[key]) {
					buckets[key] = []
					seenBreakIds[key] = new Set()
				}
				if (!session.id) {
					// Remove duplicate breaks (same start, end and text) using a Set for O(1) lookup.
					const breakId = `${session.start}${session.end}${session.title}`
					session.break_id = breakId
					if (!seenBreakIds[key].has(breakId)) {
						seenBreakIds[key].add(breakId)
						buckets[key].push(session)
					}
				} else {
					buckets[key].push(session)
				}
			}
			const needsTitleSort = ['title', 'title_desc'].includes(this.sortBy) && !this.includeDateSortKey
			const groupedBuckets = Object.entries(buckets).map(([date, sessions]) => {
				const sortedSessions = this.sortBucketSessions(sessions)
				const bucket = {
					date: sessions[0].start,
					sessions: sortedSessions
				}
				if (needsTitleSort) {
					let repr = null
					for (const s of sortedSessions) {
						if (this.isProperSession(s)) { repr = s; break }
					}
					bucket._sortKey = repr || sortedSessions[0]
				}
				return bucket
			})

			if (needsTitleSort) {
				return groupedBuckets.sort((a, b) => {
					const bySort = this.sessionComparator(a._sortKey, b._sortKey)
					if (bySort !== 0) return bySort
					return a.date.diff(b.date)
				})
			}
			if (pendingSessions.length) {
				const sortedPending = this.sortBucketSessions(pendingSessions)
				groupedBuckets.push({
					date: moment(),
					sessions: sortedPending,
				})
			}
			return groupedBuckets
		},
		sortObserverKey () {
			return [this.sortBy, this.includeRoomSortKey, this.includeDateSortKey, this.includePopularitySortKey].join('|')
		}
	},
	watch: {
		forceScrollDay () {
			this.$nextTick(() => this.scrollToDay(this.currentDay, { force: true }))
		},
		sortObserverKey () {
			this.$nextTick(() => this.onScheduleScroll())
		},
		sessionBuckets () {
			this.$nextTick(() => this.onScheduleScroll())
		},
		scrollParent () {
			this.bindScrollParent()
		}
	},
	async mounted () {
		const navigationDay = this.navigationDay
		await this.$nextTick()
		this.bindScrollParent()
		if (navigationDay && navigationDay === this.currentDay) {
			this.scrollToDay(navigationDay, { force: true })
			return
		}
		// scroll to now
		// scroll to now, unless URL overrides now
		let fragmentIsDate = false
		const fragment = window.location.hash.slice(1)
		if (fragment && fragment.length === 10) {
			const initialDay = moment.tz(fragment, this.timezone)
			if (initialDay.isValid()) {
				fragmentIsDate = true
			}
		}
		if (this.disableAutoScroll) return
		const today = this.now.clone().tz(this.timezone).format('YYYY-MM-DD')
		if (this.currentDay !== today) return // Auto-scroll does not trigger when viewing a non-current day
		await new Promise(resolve => requestAnimationFrame(resolve))
		this.scrollToNow()
	},
	beforeUnmount () {
		this._dayScrollTarget?.removeEventListener('scroll', this.onScheduleScroll)
		window.removeEventListener('resize', this.onScheduleScroll)
		cancelAnimationFrame(this._dayScrollFrame)
	},
	methods: {
		bindScrollParent () {
			this._dayScrollTarget?.removeEventListener('scroll', this.onScheduleScroll)
			this._dayScrollTarget = this.scrollParent || window
			this._dayScrollTarget.addEventListener('scroll', this.onScheduleScroll, { passive: true })
			window.addEventListener('resize', this.onScheduleScroll)
			this.$nextTick(() => this.onScheduleScroll())
		},
		titleSortKey (session) {
			const localizedTitle = getLocalizedString(session?.title)
			return (localizedTitle || '').toString().toLowerCase()
		},
		roomSortKey (session) {
			const localizedRoom = getLocalizedString(session?.room?.name)
			return (localizedRoom || '').toString().toLowerCase()
		},
		trackSortKey (session) {
			const localizedTrack = getLocalizedString(session?.track?.name)
			return (localizedTrack || '').toString().toLowerCase()
		},
		sessionComparator (a, b) {
			if (!a?.id && b?.id) return 1
			if (a?.id && !b?.id) return -1
			if (!a?.id && !b?.id) return 0

			if (this.popularitySortEnabled) {
				const popularityA = normalizePopularityCount(a)
				const popularityB = normalizePopularityCount(b)
				const popCmp = popularityB - popularityA
				if (popCmp !== 0) return popCmp
			}

			if (this.includeRoomSortKey) {
				const roomCmp = this.roomSortKey(a).localeCompare(this.roomSortKey(b))
				if (roomCmp !== 0) return roomCmp
			}

			if (this.includeDateSortKey) {
				if (a.schedule_pending && !b.schedule_pending) return 1
				if (!a.schedule_pending && b.schedule_pending) return -1
				if (a.schedule_pending || b.schedule_pending || !a.start || !b.start) {
					const direction = this.sortBy === 'title_desc' ? -1 : 1
					return this.titleSortKey(a).localeCompare(this.titleSortKey(b)) * direction
				}
				const dateCmp = a.start.diff(b.start)
				if (dateCmp !== 0) return dateCmp
				const roomCmp = this.roomSortKey(a).localeCompare(this.roomSortKey(b))
				if (roomCmp !== 0) return roomCmp
				const trackCmp = this.trackSortKey(a).localeCompare(this.trackSortKey(b))
				if (trackCmp !== 0) return trackCmp
			}

			const direction = this.sortBy === 'title_desc' ? -1 : 1
			const titleCmp = this.titleSortKey(a).localeCompare(this.titleSortKey(b))
			if (titleCmp !== 0) return titleCmp * direction

			return 0
		},
		sortBucketSessions (sessions) {
			return [...sessions].sort((a, b) => this.sessionComparator(a, b))
		},
		isProperSession (session) {
			// breaks and such don't have ids
			return !!session.id
		},
		getBucketName (date) {
			return `bucket-${date.format('YYYY-MM-DD-HH-mm')}`
		},
		getOffsetTop () {
			const rect = this.$parent.$el.getBoundingClientRect()
			return rect.top + window.scrollY
		},
		getStickyClearance () {
			const root = this.$el.closest('.pretalx-schedule') || this.$el.closest('.c-schedule-view')
			let offset = 40
			if (root) {
				const parsed = parseFloat(getComputedStyle(root).getPropertyValue('--pretalx-sticky-top-offset'))
				if (Number.isFinite(parsed)) offset = parsed
			}
			let toolbarHeight = 0
			const toolbar = root?.querySelector('.c-schedule-toolbar')
			if (toolbar) toolbarHeight = toolbar.getBoundingClientRect().height
			let versionWarning = 0
			if (root) {
				const vh = parseFloat(getComputedStyle(root).getPropertyValue('--pretalx-version-warning-height'))
				versionWarning = Number.isFinite(vh) ? vh : 0
			}
			return Math.max(0, offset) + toolbarHeight + versionWarning + 6
		},
		scrollToNow() {
			const nowIndex = this.sessionBuckets.findIndex(bucket => this.now < bucket.date)
			if (nowIndex < 0) return
			const nowBucket = this.sessionBuckets[Math.max(0, nowIndex - 1)]
			const el = this.$refs[this.getBucketName(nowBucket.date)]?.[0]
			if (!el) return
			if (this.scrollParent) {
				const top = el.getBoundingClientRect().top - this.scrollParent.getBoundingClientRect().top + this.scrollParent.scrollTop - this.getStickyClearance()
				this.scrollParent.scrollTop = top
			} else {
				window.scroll({top: el.offsetTop + this.getOffsetTop() - this.getStickyClearance()})
			}
		},
		scrollToDay (day, { force = false } = {}) {
			if (!this.showDayHeaders || !day) return
			const dayStr = day.format ? day.format('YYYY-MM-DD') : day
			if (!force && this.scrolledDay?.format('YYYY-MM-DD') === dayStr) return
			const dayBucket = this.bucketFirstByDay[dayStr]
			if (!dayBucket) return
			const el = this.$refs[this.getBucketName(dayBucket.date)]?.[0]
			if (!el) return
			this.updateDayEndSpace()
			const clearance = this.getStickyClearance()
			if (this.scrollParent) {
				const top = el.getBoundingClientRect().top - this.scrollParent.getBoundingClientRect().top + this.scrollParent.scrollTop - clearance
				this.scrollParent.scrollTo({ top, behavior: 'instant' })
			} else {
				window.scrollBy({ top: el.getBoundingClientRect().top - clearance, behavior: 'instant' })
			}
			this.scrolledDay = moment.tz(dayStr, 'YYYY-MM-DD', this.timezone).startOf('day')
		},
		updateDayEndSpace () {
			const bucket = Object.values(this.bucketFirstByDay).at(-1)
			const lastDay = bucket && this.showDayHeaders ? this.$refs[this.getBucketName(bucket.date)]?.[0] : null
			updateDayEndSpace(this.$el, lastDay, this.scrollParent?.clientHeight || window.innerHeight, this.getStickyClearance())
		},
		onScheduleScroll () {
			if (this._dayScrollFrame) return
			this._dayScrollFrame = requestAnimationFrame(() => {
				this._dayScrollFrame = null
				this.updateDayEndSpace()
				if (!this.showDayHeaders) return
				const top = (this.scrollParent?.getBoundingClientRect().top || 0) + this.getStickyClearance()
				const bounds = this.$el.getBoundingClientRect()
				if (bounds.bottom <= top) return
				const starts = Object.values(this.bucketFirstByDay).map(bucket => {
					const el = this.$refs[this.getBucketName(bucket.date)]?.[0]
					return el ? { day: bucket.date.format('YYYY-MM-DD'), top: el.getBoundingClientRect().top } : null
				}).filter(Boolean)
				const day = getDayAtScrollPosition(starts, top)
				if (!day) return
				this.scrolledDay = moment.tz(day, this.timezone).startOf('day')
				this.$emit('changeDay', this.scrolledDay)
			})
		}
	}
}
</script>
<style lang="stylus">
.c-linear-schedule
	display: flex
	padding-bottom: var(--schedule-day-end-padding, 0px)
	flex-direction: column
	min-height: 0
	.bucket
		padding-top: 8px
		.bucket-label
			font-size: 14px
			font-weight: 500
			color: $clr-secondary-text-light
			padding-left: 0
			.day
				font-weight: 600
		.break
			z-index: 10
			margin: 8px 0
			margin-right: 8px
			padding: 8px
			border-radius: 4px
			background-color: $clr-grey-200
			display: flex
			justify-content: center
			align-items: center
			.title
				font-size: 20px
				font-weight: 500
				color: $clr-secondary-text-light

@media (max-width: 600px)
	.c-linear-schedule
		.bucket
			.bucket-label
				font-size: 13px
				padding-left: 0
			.break
				margin: 6px 0
				margin-right: 4px
				.title
					font-size: 16px

.c-linear-schedule.density-compact
	.bucket
		padding-top: 4px
		.bucket-label
			font-size: 12px
		.break
			margin: 4px 4px
			padding: 4px
			.title
				font-size: 16px

.c-linear-schedule.density-comfortable
	.bucket
		padding-top: 14px
		.bucket-label
			font-size: 16px
		.break
			margin: 12px 8px
			padding: 12px
			.title
				font-size: 22px

@media print
	.c-linear-schedule
		padding-bottom: 0
</style>

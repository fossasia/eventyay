<template lang="pug">
.c-linear-schedule(v-scrollbar.y="", :class="'density-' + density")
	.bucket(v-for="({date, sessions}, index) of sessionBuckets")
		.bucket-label(:ref="getBucketName(date)", :data-date="date.toISOString()")
			.day(v-if="showDayHeaders && (index === 0 || date.clone().startOf('day').diff(sessionBuckets[index - 1].date.clone().startOf('day'), 'days') > 0)")  {{ date.clone().tz(timezone).format('dddd, D MMMM') }}
			template(v-for="session of sessions")
				session(
					v-if="isProperSession(session)",
					:session="session",
					:now="now",
					:timezone="timezone",
					:locale="locale",
					:hasAmPm="hasAmPm",
					:showFavCount="showFavCount",
					:faved="session.id && favs.includes(session.id)",
					:onHomeServer="onHomeServer",
					@fav="$emit('fav', session.id)",
					@unfav="$emit('unfav', session.id)"
				)
				.break(v-else-if="showBreaks")
					.title {{ getLocalizedString(session.title) }}
</template>
<script>
import moment from 'moment-timezone'
import { getLocalizedString } from '../utils'
import Session from './Session'

export default {
	components: { Session },
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
			default: true
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
		showDayHeaders () {
			return !(['title', 'title_desc'].includes(this.sortBy) && !this.includeDateSortKey)
		},
		sessionBuckets () {
			const buckets = {}
			for (const session of this.sessions) {
				const key = this.getBucketName(session.start)
				if (!buckets[key]) {
					buckets[key] = []
				}
				if (!session.id) {
					// Remove duplicate breaks, meaning same start, end and text
					session.break_id = `${session.start}${session.end}${session.title}`
					if (buckets[key].filter(s => s.break_id === session.break_id).length === 0) buckets[key].push(session)
				} else {
					buckets[key].push(session)
				}
			}
			const groupedBuckets = Object.entries(buckets).map(([date, sessions]) => ({
				date: sessions[0].start,
				sessions: this.sortBucketSessions(sessions)
			}))

			if (['title', 'title_desc'].includes(this.sortBy) && !this.includeDateSortKey) {
				return groupedBuckets.sort((a, b) => {
					const aSession = a.sessions.find(s => this.isProperSession(s)) || a.sessions[0]
					const bSession = b.sessions.find(s => this.isProperSession(s)) || b.sessions[0]
					const bySort = this.sessionComparator(aSession, bSession)
					if (bySort !== 0) return bySort
					return a.date.diff(b.date)
				})
			}

			return groupedBuckets
		}
	},
	watch: {
		sortBy() { this.$forceUpdate() },
		includeRoomSortKey() { this.$forceUpdate() },
		includeDateSortKey() { this.$forceUpdate() },
		currentDay: 'changeDay'
	},
	async mounted () {
		await this.$nextTick()
		this.observer = new IntersectionObserver(this.onIntersect, {
			root: this.scrollParent,
			rootMargin: '-45% 0px'
		})
		let lastBucket
		for (const [ref, el] of Object.entries(this.$refs)) {
			if (!ref.startsWith('bucket')) continue
			const date = moment(el[0].dataset.date).tz(this.timezone)
			if (lastBucket) {
				if (lastBucket.format('YYYY-MM-DD') === date.format('YYYY-MM-DD')) continue
			}
			lastBucket = date
			this.observer.observe(el[0])
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
		if (fragmentIsDate) return
		// Skip auto-scroll if disabled via prop
		if (this.disableAutoScroll) return
		const nowIndex = this.sessionBuckets.findIndex(bucket => this.now < bucket.date)
		// do not scroll if the event has not started yet
		if (nowIndex < 0) return
		const nowBucket = this.sessionBuckets[Math.max(0, nowIndex - 1)]
		const scrollTop = this.$refs[this.getBucketName(nowBucket.date)]?.[0]?.offsetTop - 90
		if (this.scrollParent) {
			this.scrollParent.scrollTop = scrollTop
		} else {
			window.scroll({top: scrollTop + this.getOffsetTop()})
		}
	},
	methods: {
		titleSortKey (session) {
			const localizedTitle = getLocalizedString(session?.title)
			return (localizedTitle || '').toString().toLowerCase()
		},
		roomSortKey (session) {
			const localizedRoom = getLocalizedString(session?.room?.name)
			return (localizedRoom || '').toString().toLowerCase()
		},
		sessionComparator (a, b) {
			if (!a?.id && b?.id) return 1
			if (a?.id && !b?.id) return -1
			if (!a?.id && !b?.id) return 0

			if (this.sortBy === 'popularity') {
				return (b.fav_count || 0) - (a.fav_count || 0)
			}

			const direction = this.sortBy === 'title_desc' ? -1 : 1
			const titleCmp = this.titleSortKey(a).localeCompare(this.titleSortKey(b))
			if (titleCmp !== 0) return titleCmp * direction

			if (this.includeRoomSortKey) {
				const roomCmp = this.roomSortKey(a).localeCompare(this.roomSortKey(b))
				if (roomCmp !== 0) return roomCmp * direction
			}

			if (this.includeDateSortKey) {
				const dateCmp = a.start.diff(b.start)
				if (dateCmp !== 0) return dateCmp
			}

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
		changeDay (day) {
			if (!this.showDayHeaders) return
			if (this.scrolledDay?.format('YYYY-MM-DD') === day) return
			const dayBucket = this.sessionBuckets.find(bucket => day === bucket.date.format('YYYY-MM-DD'))
			if (!dayBucket) return
			const el = this.$refs[this.getBucketName(dayBucket.date)]?.[0]
			if (!el) return
			const scrollTop = el.offsetTop + this.getOffsetTop() - 8
			if (this.scrollParent) {
				this.scrollParent.scrollTop = scrollTop
			} else {
				window.scroll({top: scrollTop})
			}
		},
		onIntersect (results) {
			if (!this.showDayHeaders) return
			const intersection = results[0]
			const day = moment(intersection.target.dataset.date).tz(this.timezone).startOf('day')
			if (intersection.isIntersecting) {
				this.scrolledDay = day
				this.$emit('changeDay', this.scrolledDay)
			} else if (intersection.rootBounds && (intersection.boundingClientRect.y - intersection.rootBounds.y) > 0) {
				this.scrolledDay = day.clone().subtract(1, 'day')
				this.$emit('changeDay', this.scrolledDay)
			}
		}
	}
}
</script>
<style lang="stylus">
.c-linear-schedule
	display: flex
	flex-direction: column
	min-height: 0
	.bucket
		padding-top: 8px
		.bucket-label
			font-size: 14px
			font-weight: 500
			color: $clr-secondary-text-light
			padding-left: 5px
			.day
				font-weight: 600
		.break
			z-index: 10
			margin: 8px
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
				padding-left: 8px
			.break
				margin: 6px 4px
				.title
					font-size: 16px

.c-linear-schedule.density-compact
	.bucket
		padding-top: 4px
		.bucket-label
			font-size: 12px
		.break
			margin: 4px
			padding: 4px
			.title
				font-size: 16px

.c-linear-schedule.density-comfortable
	.bucket
		padding-top: 14px
		.bucket-label
			font-size: 16px
		.break
			margin: 12px
			padding: 12px
			.title
				font-size: 22px
</style>

<template lang="pug">
.c-linear-schedule(v-scrollbar.y="")
	.bucket(v-if="sortBy == 'time'", v-for="({date, sessions}, index) of sessionBuckets", :key="date.toISO()")
		.bucket-label(:ref="getBucketName(date)", :data-date="date.toISO()")
			.day(v-if="index === 0 || date.startOf('day').diff(sessionBuckets[index - 1].date.startOf('day')).shiftTo('days').days > 0")  {{ date.setZone(timezone).toLocaleString({ weekday: 'long', day: 'numeric', month: 'long' }) }}
			.time {{ date.setZone(timezone).toLocaleString({ hour: 'numeric', minute: 'numeric' }) }}
			template(v-for="session of sessions")
				session(
					v-if="isProperSession(session)",
					:key="session.id"
					:session="session",
					:now="now",
					:timezone="timezone",
					:locale="locale",
					:hasAmPm="hasAmPm",
					:faved="session.id && favs.includes(session.id)",
					:onHomeServer="onHomeServer",
					@fav="$emit('fav', session.id)",
					@unfav="$emit('unfav', session.id)",
					isLinearSchedule=true
				)
				.break(v-else)
					.title {{ getLocalizedString(session.title) }}
	.bucket(v-if="sortBy == 'popularity' || sortBy == 'title'", v-for="session of sessionBuckets", :key="session.id")
		.sorted-session
			session(
				v-if="isProperSession(session)",
				:session="session",
				:faved="session.id && favs.includes(session.id)",
				@fav="$emit('fav', session.id)",
				@unfav="$emit('unfav', session.id)",
				isLinearSchedule=true
			)
			.break(v-else)
				.title {{ getLocalizedString(session.title) }}
</template>
<script>
import { DateTime } from 'luxon'
import { getLocalizedString } from '~/utils'
import Session from './Session'

export default {
	components: { Session },
	props: {
		sessions: Array,
		rooms: Array,
		locale: String,
		hasAmPm: Boolean,
		timezone: String,
		favs: {
			type: Array,
			default () {
				return []
			}
		},
		currentDay: String,
		now: Object,
		scrollParent: Element,
		sortBy: String,
		onHomeServer: Boolean
	},
	data () {
		return {
			getLocalizedString,
			scrolledDay: null
		}
	},
	computed: {
        // TODO: Bring back our implementation of `sortBy`.
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
			return Object.entries(buckets).map(([date, sessions]) => ({
				date: sessions[0].start,
				// sort by room for stable sort across time buckets
				sessions: sessions.sort((a, b) => this.rooms.findIndex(room => room.id === a.room.id) - this.rooms.findIndex(room => room.id === b.room.id))
			}))
		}
	},
	watch: {
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
			const date = DateTime.fromISO(el[0].dataset.date, {zone: this.timezone})
			if (lastBucket) {
				if (lastBucket.toISODate() === date.toISODate()) continue
			}
			lastBucket = date
			this.observer.observe(el[0])
		}
		// scroll to now
		// scroll to now, unless URL overrides now
		let fragmentIsDate = false
		const fragment = window.location.hash.slice(1)
		if (fragment && fragment.length === 10) {
			const initialDay = DateTime.fromISO(fragment, {zone: this.timezone})
			if (initialDay) {
				fragmentIsDate = true
			}
		}
		if (fragmentIsDate) return
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
		isProperSession (session) {
			// breaks and such don't have ids
			return !!session.id
		},
		getBucketName (date) {
			return `bucket-${date.toFormat('yyyy-LL-dd-HH-mm')}`
		},
		getOffsetTop () {
			const rect = this.$parent.$el.getBoundingClientRect()
			return rect.top + window.scrollY
		},
		changeDay (day) {
			if (this.scrolledDay?.toISODate() === day) return
			const dayBucket = this.sessionBuckets.find(bucket => day === bucket.date.toISODate())
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
			const intersection = results[0]
			const day = DateTime.fromISO(intersection.target.dataset.date, {zone: this.timezone}).startOf('day')
			if (intersection.isIntersecting) {
				this.scrolledDay = day
				this.$emit('changeDay', this.scrolledDay)
			} else if (intersection.rootBounds && (intersection.boundingClientRect.y - intersection.rootBounds.y) > 0) {
				this.scrolledDay = day.minus({days: 1})
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
			padding-left: 16px
			.day
				font-weight: 600
		.sorted-session
			padding-left: 16px
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
</style>

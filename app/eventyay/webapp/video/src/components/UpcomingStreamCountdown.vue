<template lang="pug">
.upcoming-stream-countdown(v-if="shouldShow")
	.content
		.label Up Next:
		.title {{ upcomingStream.title || 'Upcoming Stream' }}
		.separator |
		.countdown-label in
		.countdown {{ formattedCountdown }}
		.time-label at
		.time {{ formattedStartTime }}
</template>
<script>
import moment from 'lib/timetravelMoment'
import { mapState } from 'vuex'
import api from 'lib/api'

export default {
	name: 'UpcomingStreamCountdown',
	props: {
		room: {
			type: Object,
			required: true
		}
	},
	data() {
		return {
			upcomingStream: null,
			timeUntilStart: 0,
			countdownInterval: null,
			fetching: false,
			tickOffsetSeconds: 0
		}
	},
	computed: {
		...mapState(['now']),
		effectiveNow() {
			return moment(this.now).add(this.tickOffsetSeconds, 'seconds')
		},
		eventTimezone() {
			return this.$store.state.world?.timezone || 'UTC'
		},
		shouldShow() {
			return this.upcomingStream && this.timeUntilStart > 0
		},
		formattedCountdown() {
			if (this.timeUntilStart <= 0) return ''
			const duration = moment.duration(this.timeUntilStart, 'seconds')
			const hours = Math.floor(duration.asHours())
			const minutes = duration.minutes()
			const seconds = duration.seconds()
			if (hours > 0) {
				return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
			}
			return `${minutes}:${String(seconds).padStart(2, '0')}`
		},
		formattedStartTime() {
			if (!this.upcomingStream) return ''
			return moment(this.upcomingStream.start_time).format('HH:mm')
		}
	},
	watch: {
		now() {
			this.tickOffsetSeconds = 0
			this.updateCountdown()
		},
		room: {
			handler: 'fetchNextStream',
			immediate: true
		},
		upcomingStream() {
			this.startCountdownTimer()
		},
		'room.upcomingStream'(stream) {
			if (this.isStreamUpcoming(stream)) {
				this.upcomingStream = stream
				this.updateCountdown()
			} else {
				this.clearStream()
			}
		}
	},
	created() {
		this.startCountdownTimer()
		document.addEventListener('visibilitychange', this.onVisibilityChange)
	},
	beforeUnmount() {
		if (this.countdownInterval) {
			clearInterval(this.countdownInterval)
		}
		document.removeEventListener('visibilitychange', this.onVisibilityChange)
	},
	methods: {
		getTickIntervalMs() {
			if (!this.upcomingStream) return 5000
			return document.visibilityState === 'visible' ? 1000 : 5000
		},
		startCountdownTimer() {
			const intervalMs = this.getTickIntervalMs()
			if (this.countdownInterval) {
				clearInterval(this.countdownInterval)
			}
			this.countdownInterval = setInterval(() => {
				this.tickOffsetSeconds += intervalMs / 1000
				this.updateCountdown()
			}, intervalMs)
		},
		onVisibilityChange() {
			this.startCountdownTimer()
			this.updateCountdown()
		},
		isStreamUpcoming(stream) {
			if (!stream || !stream.start_time) return false
			const startTime = moment(stream.start_time)
			return startTime.isAfter(this.effectiveNow)
		},
		clearStream() {
			this.upcomingStream = null
			this.timeUntilStart = 0
		},
		async fetchNextStream() {
			if (!this.room?.id || this.fetching) return

			this.fetching = true
			try {
				const { organizer, event } = this.$store.getters.eventRouting
				if (!organizer || !event) {
					this.clearStream()
					return
				}

				const url = `/api/v1/organizers/${encodeURIComponent(organizer)}/events/${encodeURIComponent(event)}/rooms/${this.room.id}/streams/next`
				const authHeader = api._config.token
					? `Bearer ${api._config.token}`
					: api._config.clientId
						? `Client ${api._config.clientId}`
						: null
				const headers = { Accept: 'application/json' }
				if (authHeader) headers.Authorization = authHeader

				const response = await fetch(url, { headers, credentials: 'include' })
				if (response.ok) {
					const stream = await response.json()
					if (this.isStreamUpcoming(stream)) {
						this.upcomingStream = stream
						this.updateCountdown()
					} else {
						this.clearStream()
					}
				} else {
					this.clearStream()
				}
			} catch (error) {
				this.clearStream()
			} finally {
				this.fetching = false
			}
		},
		updateCountdown() {
			if (!this.upcomingStream) {
				this.timeUntilStart = 0
				return
			}
			const startTime = moment(this.upcomingStream.start_time)
			const now = this.effectiveNow
			this.timeUntilStart = Math.max(0, startTime.diff(now, 'seconds'))

			if (this.timeUntilStart === 0 || !this.isStreamUpcoming(this.upcomingStream)) {
				this.clearStream()
				if (!this.fetching) {
					this.fetchNextStream()
				}
			}
		}
	}
}
</script>
<style lang="stylus">
.upcoming-stream-countdown
	position: absolute
	bottom: 8px
	left: 8px
	z-index: 100
	background: linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(250, 250, 255, 0.95) 100%)
	color: var(--clr-primary-text-dark)
	padding: 10px 16px
	border-radius: 6px
	border: 1px solid var(--clr-grey-300)
	box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12), 0 0 0 1px rgba(255, 255, 255, 0.5)
	max-width: calc(100% - 16px)
	.content
		display: flex
		flex-direction: row
		align-items: center
		gap: 8px
		white-space: nowrap
		.label
			font-size: 13px
			font-weight: 700
			color: var(--clr-primary)
			text-transform: uppercase
		.title
			font-size: 14px
			font-weight: 600
			color: var(--clr-primary-text-dark)
		.separator
			font-size: 13px
			color: var(--clr-grey-400)
		.countdown-label
			font-size: 13px
			color: var(--clr-secondary-text-dark)
		.countdown
			font-size: 16px
			font-weight: 700
			font-family: monospace
			color: var(--clr-primary)
		.time-label
			font-size: 13px
			color: var(--clr-secondary-text-dark)
		.time
			font-size: 14px
			font-weight: 600
			color: var(--clr-primary-text-dark)
</style>

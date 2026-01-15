<template lang="pug">
.upcoming-stream-countdown
	.content(v-if="shouldShow")
		.title {{ upcomingStream.title || 'Upcoming Stream' }}
		.countdown {{ formattedCountdown }}
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
			countdownInterval: null
		}
	},
	computed: {
		...mapState(['now']),
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
		room: {
			handler: 'fetchNextStream',
			immediate: true
		},
		'room.upcomingStream'(stream) {
			if (stream) {
				this.upcomingStream = stream
				this.updateCountdown()
			}
		}
	},
	created() {
		this.countdownInterval = setInterval(() => {
			this.updateCountdown()
		}, 1000)
	},
	beforeUnmount() {
		if (this.countdownInterval) {
			clearInterval(this.countdownInterval)
		}
	},
	methods: {
		async fetchNextStream() {
			if (!this.room?.id) return
			try {
				const world = this.$store?.state?.world
				
				let organizer = world?.organizer || world?.organizer_slug
				let event = world?.slug || world?.id
				
				if (!organizer || organizer === 'default') {
					const pathParts = window.location.pathname.split('/').filter(Boolean)
					if (pathParts.length >= 2) {
						organizer = pathParts[0]
						event = pathParts[1]
					}
				}
				
				if (!organizer || !event) return
				
				const url = `/api/v1/organizers/${organizer}/events/${event}/rooms/${this.room.id}/streams/next`
				const authHeader = api._config.token
					? `Bearer ${api._config.token}`
					: api._config.clientId
					? `Client ${api._config.clientId}`
					: null
				const headers = { Accept: 'application/json' }
				if (authHeader) headers.Authorization = authHeader

				const response = await fetch(url, { headers, credentials: 'include' })
				if (response.ok) {
					this.upcomingStream = await response.json()
					this.updateCountdown()
				} else if (response.status === 404) {
					this.upcomingStream = null
				}
			} catch (error) {
				console.error('[UpcomingStreamCountdown] Failed to fetch next stream:', error)
			}
		},
		updateCountdown() {
			if (!this.upcomingStream) {
				this.timeUntilStart = 0
				return
			}
			const startTime = moment(this.upcomingStream.start_time)
			const now = moment()
			this.timeUntilStart = Math.max(0, startTime.diff(now, 'seconds'))
			if (this.timeUntilStart === 0) {
				this.upcomingStream = null
				this.fetchNextStream()
			}
		}
	}
}
</script>
<style lang="stylus">
.upcoming-stream-countdown
	position: fixed
	bottom: 16px
	right: 16px
	z-index: 100
	background: rgba(0, 0, 0, 0.8)
	color: white
	padding: 12px 16px
	border-radius: 8px
	box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3)
	.content
		display: flex
		flex-direction: column
		gap: 4px
		.title
			font-size: 14px
			font-weight: 500
		.countdown
			font-size: 20px
			font-weight: 600
			font-family: monospace
		.time
			font-size: 12px
			opacity: 0.8
</style>


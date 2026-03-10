<template lang="pug">
.c-public-stars
	.stars-wrapper(v-if="!loading")
		.stars-header
			h2 {{ heading }}
		.stars-sessions(v-if="filteredSessions.length")
			session(
				v-for="s in filteredSessions",
				:key="s.id",
				:session="s",
				:showDate="true",
				:now="resolvedNow",
				:timezone="resolvedTimezone",
				:hasAmPm="resolvedHasAmPm",
				:faved="!!(s.id && resolvedMyFavs.includes(s.id))",
				:onHomeServer="true",
				@fav="onFav(s.id)",
				@unfav="onUnfav(s.id)"
			)
		p.empty-state(v-else) {{ t.no_starred_sessions }}
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>

<script>
import moment from 'moment-timezone'
import Session from './Session.vue'

export default {
	name: 'PublicStars',
	components: { Session },
	inject: {
		scheduleData: { default: null },
		scheduleFav: { default: null },
		scheduleUnfav: { default: null },
		translationMessages: { default: () => ({}) }
	},
	props: {
		userCode: {
			type: String,
			required: true
		},
		baseUrl: {
			type: String,
			default: ''
		}
	},
	data() {
		return {
			loading: true,
			starredCodes: [],
			userName: null,
		}
	},
	async mounted() {
		if (!this.baseUrl || !this.userCode) {
			this.loading = false
			return
		}
		try {
			const response = await fetch(`${this.baseUrl}people/${this.userCode}/stars.json`, {
				credentials: 'same-origin'
			})
			if (response.ok) {
				const data = await response.json()
				if (Array.isArray(data)) {
					this.starredCodes = data
				} else if (data && Array.isArray(data.favs)) {
					this.starredCodes = data.favs
					this.userName = data.name || null
				}
			}
		} catch {
			// leave starredCodes empty on error
		}
		this.loading = false
	},
	computed: {
		t() {
			const m = this.translationMessages || {}
			return {
				starred_by: m.starred_by || 'Starred by',
				no_starred_sessions: m.no_starred_sessions || 'No starred sessions.',
			}
		},
		heading() {
			const name = this.userName || this.userCode
			return `${this.t.starred_by}: ${name}`
		},
		resolvedNow() {
			return this.scheduleData?.now || moment()
		},
		resolvedTimezone() {
			return this.scheduleData?.timezone || moment.tz.guess()
		},
		resolvedHasAmPm() {
			if (this.scheduleData?.hasAmPm !== undefined) return this.scheduleData.hasAmPm
			return new Intl.DateTimeFormat(undefined, { hour: 'numeric' }).resolvedOptions().hour12
		},
		resolvedMyFavs() {
			return this.scheduleData?.favs || []
		},
		filteredSessions() {
			if (!this.starredCodes.length) return []
			const sessions = this.scheduleData?.sessions || []
			return sessions.filter(s => this.starredCodes.includes(s.id))
				.sort((a, b) => (a.start?.diff ? a.start.diff(b.start) : 0))
		}
	},
	methods: {
		onFav(id) {
			if (this.scheduleFav) this.scheduleFav(id)
		},
		onUnfav(id) {
			if (this.scheduleUnfav) this.scheduleUnfav(id)
		}
	}
}
</script>

<style lang="stylus">
.c-public-stars
	display: flex
	flex-direction: column
	background-color: $clr-white
	.stars-wrapper
		flex: auto
		display: flex
		flex-direction: column
		padding: 16px
	.stars-header
		margin-bottom: 16px
		h2
			margin: 0
	.stars-sessions
		.c-linear-schedule-session
			box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.08)
			border-radius: 6px
			margin: 8px 0
	.empty-state
		color: rgba(0, 0, 0, 0.54)
		text-align: center
		padding: 32px 0
</style>

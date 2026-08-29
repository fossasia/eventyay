<template lang="pug">
.c-standalone-next-session(:class="[mode, {empty: !nextSession}]")
	template(v-if="nextSession")
		h2(v-if="mode !== 'compact'") {{ $t('Next Session') }}
		Session(:session="nextSession", :now="now", :faved="favs.includes(nextSession.id)")
	.empty-card(v-else)
		i.mdi.mdi-calendar-clock
		h2 {{ $t('No Upcoming Session') }}
		p {{ $t('The next scheduled session in this room will appear here.') }}
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import Session from '@schedule/components/Session.vue'

export default {
	components: {Session},
	props: {
		room: Object,
		mode: {
			type: String,
			default: 'focus'
		}
	},
	computed: {
		...mapState(['now']),
		...mapGetters('schedule', ['sessions', 'favs']),
		nextSession() {
			if (!this.sessions || !this.room) return null
			const roomId = String(this.room.id)
			return this.sessions.find(session => {
				if (!session?.room || !session.start?.isAfter?.(this.now)) return false
				const sessionRoomId = typeof session.room === 'object' ? session.room.id : session.room
				return String(sessionRoomId) === roomId
			}) || null
		},
	},
}
</script>
<style lang="stylus">
.c-standalone-next-session
	display: flex
	flex-direction: column
	align-items: center
	justify-content: center
	width: 100%
	max-width: 760px
	height: 100%
	margin: 0 auto
	padding: 20px 24px
	box-sizing: border-box
	color: #1e2327

	&.compact
		max-width: none
		padding: 4px
		justify-content: flex-start
		align-items: stretch
		.c-linear-schedule-session
			min-width: 0
			transform: none
		.empty-card
			i.mdi
				font-size: 36px
				margin-bottom: 8px
			h2
				font-size: 16px
			p
				font-size: 12px

	h2
		margin: 0 0 16px
		font-size: 22px
		font-weight: 700
	.c-linear-schedule-session
		min-width: min(100%, 520px)
		transform: scale(1.35)
		transform-origin: top center

	.empty-card
		display: flex
		flex-direction: column
		align-items: center
		justify-content: center
		text-align: center
		flex: 1
		color: #4b5563
		i.mdi
			font-size: 56px
			margin-bottom: 16px
			color: var(--clr-primary, #2185d0)
		h2
			margin: 0 0 8px
			font-size: 22px
			font-weight: 700
			color: #1e2327
		p
			margin: 0
			max-width: 360px
			font-size: 15px
</style>

<template lang="pug">
.c-landing-page(v-scrollbar.y="", :style="{'--header-background-color': module.config.header_background_color || 'var(--clr-primary)', '--header-background-image': module.config.header_background_image ? `url(${module.config.header_background_image})` : 'none'}")
	.hero(:class="{'has-no-image': !module.config.header_image && !module.config.header_background_image}")
		img(v-if="module.config.header_image", :src="module.config.header_image")
		h1.hero-text(v-else-if="world") {{ world.title }}
	.sponsors.splide(ref="sponsors", v-show="sponsors && sponsors.length")
		.splide__track
			ul.splide__list
				li.splide__slide(v-for="sponsor of sponsors")
					img.sponsor(:src="sponsor.logo", :alt="sponsor.name", @load="onSponsorImageLoad(sponsor.id)")
	.content-container
		.content
			rich-text-content(v-if="hasMainContent", :content="module.config.main_content")
			template(v-if="activeRooms && activeRooms.length")
				.header
					h3 {{ $t('LandingPage:rooms:header') || 'Active Rooms' }}
				.active-rooms
					.room-card(v-for="item of activeRooms", :key="item.room.id")
						.room-info
							.room-name {{ item.room.name }}
							.current-session(v-if="item.session")
								span.live-badge(v-if="item.isLive") LIVE
								span {{ item.session.title }}
						bunt-link-button(:to="{name: 'room', params: {roomId: item.room.id}}", :class="{'join-btn': item.isLive}")
							template(v-if="item.isLive") {{ $t('LandingPage:rooms:join') || 'Join Now' }}
							template(v-else) {{ $t('LandingPage:rooms:view') || 'View Room' }}
			template(v-if="featuredSessions && featuredSessions.length")
				.header
					h3 {{ $t('LandingPage:sessions:featured:header') }}
					bunt-link-button(:to="{name: 'schedule'}") {{ $t('LandingPage:sessions:featured:link') }}
				.sessions
					session(
						v-for="session of featuredSessions",
						:session="session",
						:now="now",
						:faved="favs.includes(session.id)",
						@fav="$store.dispatch('schedule/fav', $event)",
						@unfav="$store.dispatch('schedule/unfav', $event)"
					)
			.header
				h3 {{ $t('LandingPage:sessions:next:header') }}
				bunt-link-button(:to="{name: 'schedule'}") {{ $t('LandingPage:sessions:next:link') }}
			.sessions
				session(
					v-for="session of nextSessions",
					:session="session",
					:now="now",
					:faved="favs.includes(session.id)",
					@fav="$store.dispatch('schedule/fav', $event)",
					@unfav="$store.dispatch('schedule/unfav', $event)"
				)
		.speakers(v-if="speakers")
			.header
				h3 {{ $t('LandingPage:speakers:header', {speakers: speakers.length}) }}
				bunt-link-button(:to="{name: 'schedule:speakers'}") {{ $t('LandingPage:speakers:link') }}
			.speakers-list
				router-link.speaker(v-for="speaker of speakers.slice(0, 32)", :to="speaker.attendee ? {name: '', params: {}} : { name: 'schedule:speaker', params: { speakerId: speaker.code } }")
					img.avatar(v-if="speaker.avatar || speaker.avatar_url", :src="speaker.avatar || speaker.avatar_url")
					identicon(v-else, :user="{id: speaker.name, profile: {display_name: speaker.name}}")
					.name {{ speaker.name }}
				router-link.additional-speakers(v-if="speakers.length > 32", :to="{name: 'schedule:speakers'}") {{ $t('LandingPage:speakers:more', {additional_speakers: speakers.length - 32}) }}
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import '@splidejs/splide/dist/css/splide.min.css'
import Splide from '@splidejs/splide'
// Replace '@pretalx/schedule' Session import with local implementation
import Session from '@schedule/components/Session.vue'
import api from 'lib/api'
import moment from 'lib/timetravelMoment'
import Identicon from 'components/Identicon'
import MarkdownContent from 'components/MarkdownContent'
import RichTextContent from 'components/RichTextContent'

export default {
	components: { Identicon, MarkdownContent, Session, RichTextContent },
	props: {
		module: Object
	},
	data() {
		return {
			moment,
			sponsors: null,
			loadedSponsorImages: []
		}
	},
	computed: {
		...mapState(['now', 'rooms', 'world']),
		...mapState('schedule', ['schedule']),
		...mapGetters('schedule', ['sessions', 'favs', 'currentSessionPerRoom']),
		featuredSessions() {
			if (!this.sessions) return
			return this.sessions.filter(session => session.featured)
		},
		nextSessions() {
			if (!this.sessions) return
			// current or next sessions per room
			const sessions = []
			for (const session of this.sessions) {
				if (!session.room || !session.id) continue
				if (session.end.isBefore(this.now) || sessions.reduce((acc, s) => s.room === session.room ? ++acc : acc, 0) >= 2) continue
				sessions.push(session)
			}
			return sessions
		},
		speakers() {
			return this.schedule?.speakers.slice().sort((a, b) => a.name.split(' ').at(-1).localeCompare(b.name.split(' ').at(-1)))
		},
		hasMainContent() {
			return this.module.config.main_content?.ops?.some(op => op.insert.trim() !== '')
		},
		activeRooms() {
			if (!this.rooms) return []
			return this.rooms.filter(r => r.schedule_data || r.modules?.some(m => ['livestream.native', 'call.bigbluebutton', 'call.zoom', 'call.janus'].includes(m.type))).map(room => {
				const sessionInfo = this.currentSessionPerRoom?.[room.id]
				const session = sessionInfo?.session
				const hasVideo = room.modules && room.modules.some(m => ['livestream.native', 'livestream.youtube', 'livestream.iframe', 'call.bigbluebutton', 'call.zoom', 'call.janus'].includes(m.type))
				const isLive = !!session && hasVideo
				return { room, session, hasVideo, isLive }
			})
		},
	},
	async mounted() {
		// TODO make this configurable?
		const sponsorRoom = this.rooms.find(r => r.id === this.module.config.sponsor_room_id)
		if (!sponsorRoom) return
		this.sponsors = (await api.call('exhibition.list', {room: sponsorRoom.id})).exhibitors
		await this.$nextTick()
		const splide = new Splide(this.$refs.sponsors, {
			type: 'loop',
			autoWidth: true
		})

		splide.on('overflow', (isOverflow) => {
			splide.go(0)
			splide.options = {
				arrows: isOverflow,
				pagination: isOverflow,
				drag: isOverflow,
				focus: isOverflow ? 'center' : false,
				clones: isOverflow ? 50 : 0, // HACK setting this to 50 instead of undefined
			}
			splide.go(0)
		})

		splide.on('click', (slide) => {
			this.$router.push({name: 'exhibitor', params: {exhibitorId: this.sponsors[slide.slideIndex].id}})
		})

		splide.mount()
		this.sponsorSplide = splide
	},
	methods: {
		onSponsorImageLoad(sponsorId) {
			this.loadedSponsorImages.push(sponsorId)
			if (this.loadedSponsorImages.length === this.sponsors.length) {
				this.sponsorSplide.refresh()
			}
		}
	}
}
</script>
<style lang="stylus">
.c-landing-page
	flex: auto
	background-color: $clr-grey-50
	.hero
		height: calc(var(--vh) * 20)
		min-height: 120px
		display: flex
		align-items: center
		justify-content: center
		background-color: var(--header-background-color)
		background-image: var(--header-background-image)
		background-repeat: no-repeat
		background-size: cover
		background-position: center
		&.has-no-image
			height: auto
			padding: 48px 16px
			background-color: var(--clr-primary)
			color: $clr-primary-text-dark
		.hero-text
			font-size: 36px
			font-weight: 700
			text-align: center
			margin: 0
			padding: 0 16px
		img
			height: 100%
			max-width: 100%
			object-fit: contain
	.content-container
		display: flex
		justify-content: center
		gap: 32px
		padding: 0 16px
		> *
			flex: 1
			min-width: 0
			display: flex
			flex-direction: column
	.content
		display: flex
		flex-direction: column
		max-width: 960px
		.header
			padding: 0 8px
	.rich-text-content
		padding: 0 8px
	.header
		display: flex
		justify-content: space-between
		align-items: baseline
		height: 56px
		h3
			margin: 0
			line-height: 56px
		.bunt-link-button
			themed-button-primary()
	.speakers
		max-width: calc(124px * 3 + 2px)
	.speakers-list
		display: flex
		flex-wrap: wrap
		justify-content: center
		background-color: $clr-white
		border-radius: 6px
		border: border-separator()
		margin: 8px 0
		.speaker
			display: flex
			flex-direction: column
			align-items: center
			gap: 4px
			width: 124px
			cursor: pointer
			padding: 12px 4px
			box-sizing: border-box
			color: $clr-primary-text-light
			&:hover
				background-color: $clr-grey-200
			img
				border-radius: 50%
				height: 92px
				width: @height
				object-fit: cover
			.name
				text-align: center
				white-space: break-word
				font-weight: 500
				font-size: 14px
		.additional-speakers
			font-size: 18px
			font-weight: 600
			align-self: center
			width: 100%
			height: 92px
			text-align: center
			line-height: 90px
			&:hover
				background-color: $clr-grey-200
	.sponsors
		padding: 8px 0 16px 0
		margin: 0 0 8px 0
		background-color: $clr-white
		.sponsor
			height: 10vh
			max-height: 10vh
			max-width: unquote("min(260px, 90vw)")
			object-fit: contain
			user-select: none
			margin: 0 24px 0 24px
		// .splide__pagination
		.splide__pagination__page.is-active
			background-color: var(--clr-primary)
		.splide__arrow
			top: calc(50% - 12px)
		&:not(.is-overflow) .splide__list
			justify-content: center

	.active-rooms
		display: grid
		grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))
		gap: 16px
		padding: 0 8px
		margin-bottom: 24px
		.room-card
			display: flex
			flex-direction: column
			justify-content: space-between
			background: $clr-white
			border: border-separator()
			border-radius: 6px
			padding: 16px
			.room-name
				font-size: 18px
				font-weight: 600
				margin-bottom: 8px
			.current-session
				font-size: 14px
				color: $clr-secondary-text-light
				display: flex
				align-items: center
				gap: 8px
				margin-bottom: 16px
				.live-badge
					background-color: var(--clr-danger)
					color: var(--clr-primary-text-dark)
					padding: 2px 6px
					border-radius: 4px
					font-weight: bold
					font-size: 12px
			.bunt-link-button
				align-self: flex-start
				themed-button-secondary()
				&.join-btn
					themed-button-primary()

	+below('m')
		.content-container
			flex-direction: column
			align-items: center
			padding: 0 8px
			> *
				max-width: 100%
</style>

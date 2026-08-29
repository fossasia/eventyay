<template lang="pug">
.v-standalone-kiosk(:class="viewMode")
	// Full screen: pinned item, single enabled panel, or locally focused panel
	.kiosk-focus(v-if="focusPanel")
		.focus-toolbar(v-if="showFocusControls")
			span.focus-label
				i.mdi(:class="focusPanel.icon")
				| {{ focusPanel.label }}
			bunt-button.btn-unpin(
				@click="exitFocus",
				:loading="unpinning"
			) {{ focusPanel.canUnpin ? $t('Unpin') : $t('Show all') }}
		.focus-body
			component(
				:is="focusPanel.component",
				:room="room",
				mode="focus"
			)

	// Overview of every enabled panel (empty placeholders included)
	.kiosk-overview(v-else-if="overviewPanels.length > 1")
		.panel(
			v-for="panel in overviewPanels",
			:key="panel.id",
			:class="[panel.id, {featured: panel.featured, actionable: canPinPanels || panel.hasContent}]"
			@click="onPanelClick(panel)"
		)
			.panel-label
				i.mdi(:class="panel.icon")
				span {{ panel.label }}
				span.pinned-tag(v-if="panel.featured") {{ $t('Pinned') }}
				span.live-tag(v-else-if="panel.hasContent") {{ $t('Live') }}
				bunt-button.btn-pin(
					v-if="panel.hasContent && canPinPanels && panel.pinTarget && !panel.featured",
					@click.stop="pinPanel(panel)"
				) {{ $t('Pin') }}
			.panel-body
				component(
					:is="panel.component",
					:room="room",
					mode="compact"
				)

	// Nothing enabled in kiosk settings
	.kiosk-empty(v-else)
		i.mdi.mdi-monitor-dashboard
		h2 {{ $t('Stage display ready') }}
		p {{ emptyHint }}
</template>
<script>
import { mapGetters, mapState } from 'vuex'
import PollSlide from './Poll'
import QuestionSlide from './Question'
import NextSessionSlide from './NextSession'
import ViewersSlide from './Viewers'

export default {
	props: {
		room: Object,
		config: {
			type: Object,
			default: () => ({})
		}
	},
	data() {
		return {
			// Local override so operators can leave a pinned full-screen view
			// even if the kiosk token cannot call unpin APIs.
			forceOverview: false,
			localFocusId: null,
			unpinning: false
		}
	},
	computed: {
		...mapState(['roomViewers', 'now', 'user']),
		...mapState('poll', ['polls']),
		...mapState('question', ['questions']),
		...mapGetters(['hasPermission']),
		...mapGetters('poll', ['pinnedPoll']),
		...mapGetters('question', ['pinnedQuestion']),
		...mapGetters('schedule', ['sessions']),
		canPinPanels() {
			return this.hasPermission('room:poll.manage') || this.hasPermission('room:question.moderate')
		},
		// Prefer live store profile (updated via user.updated); fall back to prop.
		slidesSource() {
			return this.user?.profile?.slides ?? this.config?.slides ?? null
		},
		activePoll() {
			if (!this.polls) return null
			return this.polls.find(poll => poll.state === 'open' || poll.state === 'closed') || null
		},
		visibleQuestions() {
			if (!this.questions) return []
			return this.questions
				.filter(question => question.state === 'visible')
				.slice()
				.sort((a, b) => {
					if (a.is_pinned && !b.is_pinned) return -1
					if (!a.is_pinned && b.is_pinned) return 1
					return (b.score || 0) - (a.score || 0)
				})
		},
		topVisibleQuestion() {
			return this.visibleQuestions[0] || null
		},
		nextSession() {
			if (!this.room || !this.sessions) return null
			const roomId = String(this.room.id)
			return this.sessions.find(session => {
				if (!session?.room || !session.start?.isAfter?.(this.now)) return false
				const sessionRoomId = typeof session.room === 'object' ? session.room.id : session.room
				return String(sessionRoomId) === roomId
			}) || null
		},
		hasViewers() {
			if (!Array.isArray(this.roomViewers) || this.roomViewers.length === 0) return false
			const selfId = this.user?.id
			return this.roomViewers.some(viewer => {
				if (!viewer || viewer.deleted) return false
				if (selfId && String(viewer.id) === String(selfId)) return false
				return true
			})
		},
		overviewPanels() {
			const panels = []
			if (this.isSlideEnabled('pinned_poll')) {
				panels.push({
					id: 'poll',
					label: this.$t('Poll'),
					icon: 'mdi-poll',
					component: PollSlide,
					hasContent: !!(this.pinnedPoll || this.activePoll),
					featured: !!this.pinnedPoll,
					pinTarget: this.pinnedPoll || this.activePoll,
					pinType: 'poll'
				})
			}
			if (this.isSlideEnabled('pinned_question')) {
				panels.push({
					id: 'question',
					label: this.$t('Question'),
					icon: 'mdi-comment-question-outline',
					component: QuestionSlide,
					hasContent: this.visibleQuestions.length > 0,
					featured: !!this.pinnedQuestion,
					pinTarget: this.pinnedQuestion || this.topVisibleQuestion,
					pinType: 'question'
				})
			}
			if (this.isSlideEnabled('next_session')) {
				panels.push({
					id: 'nextSession',
					label: this.$t('Next Session'),
					icon: 'mdi-calendar-clock',
					component: NextSessionSlide,
					hasContent: !!this.nextSession,
					featured: this.localFocusId === 'nextSession',
					pinTarget: null,
					pinType: null
				})
			}
			if (this.isSlideEnabled('viewers')) {
				panels.push({
					id: 'viewers',
					label: this.$t('Viewers'),
					icon: 'mdi-account-group',
					component: ViewersSlide,
					hasContent: this.hasViewers,
					featured: this.localFocusId === 'viewers',
					pinTarget: null,
					pinType: null
				})
			}
			return panels
		},
		contentPanels() {
			return this.overviewPanels.filter(panel => panel.hasContent)
		},
		// Server pin takes priority; then local focus; then solo enabled panel.
		focusPanel() {
			if (this.forceOverview && this.overviewPanels.length > 1) return null

			if (!this.forceOverview && this.isSlideEnabled('pinned_poll') && this.pinnedPoll) {
				return {
					id: 'poll',
					label: this.$t('Poll'),
					icon: 'mdi-poll',
					component: PollSlide,
					canUnpin: true,
					unpinType: 'poll'
				}
			}
			if (!this.forceOverview && this.isSlideEnabled('pinned_question') && this.pinnedQuestion) {
				return {
					id: 'question',
					label: this.$t('Question'),
					icon: 'mdi-comment-question-outline',
					component: QuestionSlide,
					canUnpin: true,
					unpinType: 'question'
				}
			}
			if (this.localFocusId) {
				const panel = this.overviewPanels.find(item => item.id === this.localFocusId)
				if (panel) {
					return {
						...panel,
						canUnpin: false,
						unpinType: null
					}
				}
			}
			// Exactly one enabled panel → full screen (empty state or live content)
			if (this.overviewPanels.length === 1) {
				return {
					...this.overviewPanels[0],
					canUnpin: false,
					unpinType: null
				}
			}
			return null
		},
		// Show unpin/show-all whenever something is focused over a multi-panel overview.
		showFocusControls() {
			if (!this.focusPanel) return false
			if (this.focusPanel.canUnpin) return true
			return this.overviewPanels.length > 1
		},
		viewMode() {
			return this.focusPanel ? 'focus-mode' : 'overview-mode'
		},
		normalizedSlides() {
			const raw = this.slidesSource
			if (!raw || typeof raw !== 'object') return null
			const keys = ['pinned_poll', 'pinned_question', 'next_session', 'viewers']
			const present = keys.some(key => Object.prototype.hasOwnProperty.call(raw, key))
			if (!present) return null
			const normalize = (value) => value === true || value === 'true' || value === 1 || value === '1'
			return {
				pinned_poll: normalize(raw.pinned_poll),
				pinned_question: normalize(raw.pinned_question),
				next_session: normalize(raw.next_session),
				viewers: normalize(raw.viewers)
			}
		},
		emptyHint() {
			if (this.overviewPanels.length === 0) {
				return this.$t('Enable panels in kiosk settings to show them on this display.')
			}
			if (this.isSlideEnabled('viewers')) {
				return this.$t('Open a poll, approve a question, or wait for viewers and upcoming sessions — they will appear here.')
			}
			return this.$t('Open a poll, approve a question, or wait for upcoming sessions — they will appear here.')
		}
	},
	watch: {
		pinnedPoll() {
			this.forceOverview = false
			this.localFocusId = null
		},
		pinnedQuestion() {
			this.forceOverview = false
			this.localFocusId = null
		},
		'user.profile.slides': {
			deep: true,
			handler() {
				// Drop local focus if that panel was disabled in kiosk settings.
				if (this.localFocusId === 'viewers' && !this.isSlideEnabled('viewers')) {
					this.localFocusId = null
				}
				if (this.localFocusId === 'nextSession' && !this.isSlideEnabled('next_session')) {
					this.localFocusId = null
				}
				if (this.localFocusId === 'poll' && !this.isSlideEnabled('pinned_poll')) {
					this.localFocusId = null
				}
				if (this.localFocusId === 'question' && !this.isSlideEnabled('pinned_question')) {
					this.localFocusId = null
				}
				// After settings change, prefer the overview so newly enabled panels are visible.
				if (this.overviewPanels.length > 1 && !this.pinnedPoll && !this.pinnedQuestion) {
					this.forceOverview = true
					this.localFocusId = null
				}
			}
		}
	},
	methods: {
		isSlideEnabled(slide) {
			const slides = this.normalizedSlides
			if (!slides) {
				// Legacy kiosks without a slides config: show classic panels only.
				// Viewers is opt-in and must be explicitly enabled in kiosk settings.
				return slide !== 'viewers'
			}
			return slides[slide] === true
		},
		onPanelClick(panel) {
			if (this.overviewPanels.length < 2) return
			if (panel.pinType && panel.pinTarget && this.canPinPanels) {
				this.pinPanel(panel)
				return
			}
			this.forceOverview = false
			this.localFocusId = panel.id
		},
		async pinPanel(panel) {
			if (!panel.pinTarget || !panel.pinType) return
			try {
				if (panel.pinType === 'poll') {
					await this.$store.dispatch('poll/pinPoll', panel.pinTarget)
				} else if (panel.pinType === 'question') {
					await this.$store.dispatch('question/pinQuestion', panel.pinTarget)
				}
				this.forceOverview = false
				this.localFocusId = null
			} catch (error) {
				console.error('Failed to pin kiosk panel', panel.id, error)
			}
		},
		async exitFocus() {
			const panel = this.focusPanel
			if (!panel) return
			this.unpinning = true
			try {
				if (panel.unpinType === 'poll' && this.hasPermission('room:poll.manage')) {
					await this.$store.dispatch('poll/unpinAllPolls')
				} else if (panel.unpinType === 'question' && this.hasPermission('room:question.moderate')) {
					await this.$store.dispatch('question/unpinAllQuestions')
				} else {
					// Display-only kiosk / no permission: return to overview locally
					this.forceOverview = true
					this.localFocusId = null
				}
			} catch (error) {
				console.error('Failed to exit kiosk focus', error)
				this.forceOverview = true
				this.localFocusId = null
			} finally {
				this.unpinning = false
			}
		}
	}
}
</script>
<style lang="stylus">
.v-standalone-kiosk
	height: 100%
	width: 100%
	box-sizing: border-box
	background: #f3f4f6
	color: #1e2327
	overflow: hidden

	&.focus-mode
		.kiosk-focus
			height: 100%
			width: 100%
			display: flex
			flex-direction: column
			min-height: 0
			background: #ffffff

		.focus-toolbar
			display: flex
			align-items: center
			justify-content: space-between
			gap: 12px
			flex: none
			padding: 10px 14px
			border-bottom: 1px solid #e5e7eb
			background: #f8fafc

			.focus-label
				display: inline-flex
				align-items: center
				gap: 8px
				font-size: 14px
				font-weight: 700
				i.mdi
					color: var(--clr-primary, #2185d0)
					font-size: 18px

			.btn-unpin
				themed-button-secondary()

		.focus-body
			flex: 1 1 auto
			min-height: 0
			display: flex
			align-items: flex-start
			justify-content: flex-start
			padding: 12px
			box-sizing: border-box
			overflow: auto
			> *
				flex: 1 1 auto
				min-height: 0
				width: 100%
				height: auto
				max-height: 100%
				align-self: stretch

	&.overview-mode
		.kiosk-overview
			height: 100%
			width: 100%
			display: grid
			grid-template-columns: repeat(2, minmax(0, 1fr))
			grid-template-rows: repeat(2, minmax(0, 1fr))
			gap: 12px
			padding: 12px
			box-sizing: border-box

			.panel
				display: flex
				flex-direction: column
				min-height: 0
				min-width: 0
				border: 1px solid #e5e7eb
				border-radius: 8px
				background: #ffffff
				overflow: hidden
				box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04)

				&.empty .panel-label
					color: #6b7280

				&.featured
					border-color: var(--clr-primary, #2185d0)
					box-shadow: 0 0 0 1px var(--clr-primary, #2185d0)

				&.actionable
					cursor: pointer
					&:hover
						border-color: var(--clr-primary, #2185d0)

				.panel-label
					display: flex
					align-items: center
					gap: 8px
					flex: none
					padding: 10px 12px
					border-bottom: 1px solid #e5e7eb
					font-size: 13px
					font-weight: 700
					color: #1e2327
					background: #f8fafc

					i.mdi
						color: var(--clr-primary, #2185d0)
						font-size: 18px

					.live-tag, .pinned-tag
						margin-left: auto
						font-size: 10px
						font-weight: 700
						text-transform: uppercase
						letter-spacing: 0.4px
						color: #fff
						padding: 2px 6px
						border-radius: 3px

					.live-tag
						background: #d32f2f

					.pinned-tag
						background: var(--clr-primary, #2185d0)

					.btn-pin
						themed-button-primary()
						margin-left: 8px
						height: 28px
						line-height: 28px
						font-size: 11px
						padding: 0 10px

				.panel-body
					flex: 1 1 auto
					min-height: 0
					overflow: auto
					padding: 8px
					display: flex
					> *
						flex: 1 1 auto
						min-height: 0
						width: 100%
						max-width: 100%
						height: auto
						margin: 0
						padding: 8px

	.kiosk-empty
		height: 100%
		display: flex
		flex-direction: column
		align-items: center
		justify-content: center
		text-align: center
		padding: 32px
		color: #4b5563
		background: #ffffff
		i.mdi
			font-size: 56px
			color: var(--clr-primary, #2185d0)
			margin-bottom: 12px
		h2
			margin: 0 0 8px
			font-size: 22px
			color: #1e2327
		p
			margin: 0
			max-width: 420px
			font-size: 15px

@media (max-width: 700px)
	.v-standalone-kiosk.overview-mode .kiosk-overview
		grid-template-columns: 1fr
		grid-template-rows: none
		overflow: auto
		.panel
			min-height: 220px
</style>

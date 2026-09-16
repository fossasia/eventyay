<template lang="pug">
.c-standalone-poll(:class="[mode, { 'empty-poll': !displayPoll }]", :style="displayPoll ? {'--total-votes': totalVotes} : null")
	.poll-stage-header(v-if="showStageHeader")
		.total-votes-count(v-if="displayPoll")
			i.mdi.mdi-account-group
			span {{ totalVotes }} {{ $t('votes') }}
		.live-indicator(v-else)
			span.pulse-dot
	template(v-if="displayPoll")
		.question {{ displayPoll.content }}
		.options-list
			.option-item(
				v-for="option of displayPoll.options",
				:key="option.id",
				:class="{'most-votes': optionsWithMostVotes.includes(String(option.id)) && totalVotes > 0}"
			)
				.option-info
					span.content {{ option.content }}
					.option-meta
						span.leading-tag(v-if="optionsWithMostVotes.includes(String(option.id)) && totalVotes > 0")
							span {{ $t('Leading') }}
						span.percentage {{ getPercentage(option.id) }}%
				.progress-bar-container
					.progress-bar(:style="{ width: getPercentage(option.id) + '%' }")
	.empty-card(v-else)
		i.mdi.mdi-poll-box-outline
		h2 {{ $t('No Active Poll') }}
		p {{ emptyHint }}
</template>

<script>
import { mapGetters, mapState } from 'vuex'

export default {
	props: {
		room: Object,
		mode: {
			type: String,
			default: 'focus' // focus | compact
		}
	},
	computed: {
		...mapState('poll', ['polls']),
		...mapGetters('poll', ['pinnedPoll']),
		showStageHeader() {
			return this.mode !== 'compact'
		},
		// Overview can show an open/closed poll; pin still drives full-screen focus in kiosk.
		activePoll() {
			if (!this.polls) return null
			return this.polls.find(poll => poll.state === 'open' || poll.state === 'closed') || null
		},
		displayPoll() {
			return this.pinnedPoll || this.activePoll
		},
		emptyHint() {
			if (this.mode === 'compact') {
				return this.$t('Open or pin a poll in Manage to show results here. Pin expands it to full screen.')
			}
			return this.$t('The speaker or moderator will pin a live poll here during the session.')
		},
		totalVotes() {
			if (!this.displayPoll?.results) return 0
			return Object.values(this.displayPoll.results).reduce((acc, result) => acc + result, 0)
		},
		optionsWithMostVotes() {
			if (!this.displayPoll?.results) return []
			const sortedResults = Object.entries(this.displayPoll.results).slice().sort((a, b) => b[1] - a[1])
			if (sortedResults.length === 0) return []
			const mostVotes = sortedResults[0][1]
			if (mostVotes === 0) return []
			const optionsWithMostVotes = []
			for (const result of sortedResults) {
				if (result[1] !== mostVotes) break
				optionsWithMostVotes.push(String(result[0]))
			}
			return optionsWithMostVotes
		}
	},
	methods: {
		getPercentage(optionId) {
			if (!this.totalVotes || !this.displayPoll?.results?.[optionId]) return 0
			return Math.round((this.displayPoll.results[optionId] / this.totalVotes) * 100)
		}
	}
}
</script>

<style lang="stylus">
.c-standalone-poll
	display: flex
	flex-direction: column
	justify-content: flex-start
	align-items: stretch
	width: 100%
	max-width: none
	height: 100%
	margin: 0
	padding: 16px 24px
	box-sizing: border-box
	overflow: auto
	color: #1e2327

	&.compact
		max-width: none
		padding: 4px
		.question
			font-size: 18px
			margin-bottom: 12px
		.option-item
			gap: 6px
			.option-info .content
				font-size: 14px
			.option-meta .percentage
				font-size: 14px
		.progress-bar-container
			height: 8px
		.empty-card
			min-height: 0
			i.mdi
				font-size: 36px
				margin-bottom: 8px
			h2
				font-size: 16px
			p
				font-size: 12px

	.poll-stage-header
		display: flex
		align-items: center
		justify-content: flex-end
		gap: 10px
		padding-bottom: 12px
		margin-bottom: 16px
		border-bottom: 1px solid #e5e7eb

		.live-indicator
			display: inline-flex
			align-items: center
			margin-right: auto

			.pulse-dot
				width: 8px
				height: 8px
				background-color: #d32f2f
				border-radius: 50%
				animation: poll-pulse 1.8s infinite

		.total-votes-count
			display: inline-flex
			align-items: center
			gap: 6px
			flex: none
			font-size: 14px
			font-weight: 600
			color: #4b5563
			margin-left: auto

	.question
		font-size: 28px
		font-weight: 700
		line-height: 1.35
		margin: 0 0 24px
		color: #1e2327

	.options-list
		display: flex
		flex-direction: column
		gap: 16px

	.option-item
		display: flex
		flex-direction: column
		gap: 8px
		padding: 4px 0

		&.most-votes
			.percentage
				color: var(--clr-primary, #2185d0)

		.option-info
			display: flex
			justify-content: space-between
			align-items: center
			gap: 12px

			.content
				font-size: 18px
				font-weight: 600
				color: #1e2327
				flex: 1

			.option-meta
				display: flex
				align-items: center
				gap: 10px

				.leading-tag
					display: inline-flex
					align-items: center
					background: rgba(33, 133, 208, 0.12)
					color: var(--clr-primary, #2185d0)
					font-size: 11px
					font-weight: 700
					padding: 2px 8px
					border-radius: 4px
					text-transform: uppercase

				.percentage
					font-size: 18px
					font-weight: 800
					min-width: 45px
					text-align: right
					color: #1e2327

		.progress-bar-container
			height: 12px
			width: 100%
			background: #e5e7eb
			border-radius: 4px
			overflow: hidden

			.progress-bar
				height: 100%
				background: var(--clr-primary, #2185d0)
				border-radius: 4px
				transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1)

		&.most-votes .progress-bar
			background: var(--clr-primary-darken-15, #1a6fad)

	&.empty-poll, .empty-card
		.empty-card, &.empty-poll .empty-card
			display: flex
			flex-direction: column
			align-items: center
			justify-content: center
			text-align: center
			flex: 1
			min-height: 120px
			color: #4b5563

		i.mdi
			font-size: 56px
			margin-bottom: 16px
			color: var(--clr-primary, #2185d0)

		h2
			font-size: 22px
			font-weight: 700
			margin: 0 0 8px 0
			color: #1e2327

		p
			font-size: 15px
			max-width: 400px
			margin: 0

	.empty-card
		display: flex
		flex-direction: column
		align-items: center
		justify-content: center
		text-align: center
		flex: 1
		min-height: 120px
		color: #4b5563

		i.mdi
			font-size: 56px
			margin-bottom: 16px
			color: var(--clr-primary, #2185d0)

		h2
			font-size: 22px
			font-weight: 700
			margin: 0 0 8px 0
			color: #1e2327

		p
			font-size: 15px
			max-width: 400px
			margin: 0

@keyframes poll-pulse
	0%
		transform: scale(0.95)
		box-shadow: 0 0 0 0 rgba(211, 47, 47, 0.7)
	70%
		transform: scale(1)
		box-shadow: 0 0 0 8px rgba(211, 47, 47, 0)
	100%
		transform: scale(0.95)
		box-shadow: 0 0 0 0 rgba(211, 47, 47, 0)

@media (max-width: 600px)
	.c-standalone-poll
		padding: 12px
		.question
			font-size: 22px
			margin-bottom: 18px
		.option-item .option-info
			.content
				font-size: 16px
			.option-meta .percentage
				font-size: 16px
</style>

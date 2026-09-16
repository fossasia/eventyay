<template lang="pug">
.v-presentation-question(:class="[mode, { 'empty-question': !hasQuestions, 'single-focus': showPinnedOnly }]")
	template(v-if="hasQuestions")
		// Pinned full-screen focus: one question large
		template(v-if="showPinnedOnly")
			.question {{ pinnedQuestion.content }}
			.info
				.votes
					.mdi.mdi-thumb-up
					.vote-count {{ pinnedQuestion.score }}
				.user(v-if="senderFor(pinnedQuestion)")
					avatar(:user="senderFor(pinnedQuestion)", :size="mode === 'compact' ? 32 : 48")
					.username {{ displayNameFor(pinnedQuestion) }}
		// Otherwise list every visible question (pinned first)
		.questions-list(v-else)
			.question-item(
				v-for="question in visibleQuestions",
				:key="question.id",
				:class="{pinned: question.is_pinned}"
			)
				.question-main
					span.pinned-badge(v-if="question.is_pinned") {{ $t('Pinned') }}
					.question {{ question.content }}
				.info
					.votes
						.mdi.mdi-thumb-up
						.vote-count {{ question.score }}
					.user(v-if="senderFor(question)")
						avatar(:user="senderFor(question)", :size="mode === 'compact' ? 28 : 36")
						.username {{ displayNameFor(question) }}
	.empty-card(v-else)
		i.mdi.mdi-comment-question-outline
		h2 {{ $t('No questions yet') }}
		p {{ emptyHint }}
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import Avatar from 'components/Avatar'

export default {
	components: { Avatar },
	props: {
		room: Object,
		mode: {
			type: String,
			default: 'focus'
		}
	},
	computed: {
		...mapState('chat', ['usersLookup']),
		...mapState('question', ['questions']),
		...mapGetters('question', ['pinnedQuestion']),
		visibleQuestions() {
			if (!this.questions) return []
			return this.questions
				.filter(question => question.state === 'visible')
				.slice()
				.sort((a, b) => {
					// Pinned first, then highest score.
					if (a.is_pinned && !b.is_pinned) return -1
					if (!a.is_pinned && b.is_pinned) return 1
					return (b.score || 0) - (a.score || 0)
				})
		},
		hasQuestions() {
			return this.visibleQuestions.length > 0
		},
		// Full-screen pin takeover (kiosk focus when a question is pinned).
		showPinnedOnly() {
			return this.mode === 'focus' && !!this.pinnedQuestion
		},
		emptyHint() {
			if (this.mode === 'compact') {
				return this.$t('Approve questions in Manage to list them here. Pin one to show it full screen.')
			}
			return this.$t('Approved audience questions will appear here during the session.')
		}
	},
	watch: {
		visibleQuestions: {
			handler(questions) {
				const senderIds = questions
					.map(question => question.sender)
					.filter(Boolean)
				if (senderIds.length) {
					this.$store.dispatch('chat/fetchUsers', senderIds)
				}
			},
			immediate: true
		}
	},
	methods: {
		senderFor(question) {
			if (!question?.sender) return null
			return this.usersLookup[question.sender]
		},
		displayNameFor(question) {
			return this.senderFor(question)?.profile?.display_name ?? question?.sender
		}
	}
}
</script>
<style lang="stylus">
.v-presentation-question
	display: flex
	flex-direction: column
	justify-content: flex-start
	width: 100%
	max-width: none
	height: 100%
	margin: 0
	padding: 20px 24px
	box-sizing: border-box
	background: #ffffff
	color: #1e2327
	overflow: auto

	&.compact
		max-width: none
		padding: 4px
		.questions-list
			gap: 8px
		.question-item
			padding: 8px 10px
			.question
				font-size: 14px
			.info
				margin-top: 8px
				padding-top: 6px
				.votes .mdi, .votes .vote-count
					font-size: 16px
				.username
					font-size: 12px
		&.single-focus .question
			font-size: 16px
		.empty-card
			i.mdi
				font-size: 36px
				margin-bottom: 8px
			h2
				font-size: 16px
			p
				font-size: 12px

	.questions-list
		display: flex
		flex-direction: column
		gap: 12px
		width: 100%
		min-height: 0

	.question-item
		display: flex
		flex-direction: column
		width: 100%
		padding: 14px 16px
		border: 1px solid #e5e7eb
		border-radius: 8px
		background: #ffffff
		box-sizing: border-box
		&.pinned
			border-color: var(--clr-primary, #2185d0)
			box-shadow: 0 0 0 1px var(--clr-primary, #2185d0)
		.question-main
			display: flex
			flex-direction: column
			gap: 6px
			min-width: 0
		.pinned-badge
			align-self: flex-start
			font-size: 10px
			font-weight: 700
			text-transform: uppercase
			letter-spacing: 0.4px
			color: #fff
			background: var(--clr-primary, #2185d0)
			padding: 2px 6px
			border-radius: 3px
		.question
			font-size: 20px
			font-weight: 700
			line-height: 1.35
			color: #1e2327
		.info
			margin-top: 12px
			padding-top: 10px

	&.single-focus > .question
		font-size: 32px
		font-weight: 700
		line-height: 1.35
		color: #1e2327
	&.single-focus > .info
		margin-top: 20px
		padding-top: 12px

	.info
		display: flex
		justify-content: space-between
		align-items: center
		align-self: stretch
		border-top: 1px solid #e5e7eb
		.votes
			display: flex
			align-items: center
			.mdi
				font-size: 22px
				color: var(--clr-primary, #2185d0)
			.vote-count
				margin: 0 0 0 8px
				font-size: 20px
				font-weight: 700
				color: #1e2327
		.user
			display: flex
			align-items: center
			min-width: 0
			.username
				margin: 0 0 0 8px
				color: #4b5563
				font-weight: 600
				overflow: hidden
				text-overflow: ellipsis
				white-space: nowrap

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
			max-width: 400px
			font-size: 15px
</style>

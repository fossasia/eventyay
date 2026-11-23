<template lang="pug">
.c-poll(:class="[poll.state, {'has-voted': poll.answers, pinned: poll.is_pinned, managing: isManaging}]", :style="{'--total-votes': totalVotes}")
	.question {{ poll.content }}
	template(v-if="!isManaging && !poll.answers && poll.state === 'open'")
		bunt-button.btn-option(v-for="option of poll.options", :disabled="isVoting", @click="vote(option)") {{ option.content }}
	template(v-else)
		.option(v-for="option of poll.options", :class="{'most-votes': optionsWithMostVotes.includes(option.id), 'own-vote': ownAnswers.includes(option.id)}")
			.content
				| {{ option.content }}
				span.own-vote-label(v-if="ownAnswers.includes(option.id)")
					span.mdi.mdi-check(aria-hidden="true")
					| {{ $t('Your vote') }}
			.votes(:style="{'--votes': optionVotes(option)}") {{ totalVotes ? (optionVotes(option) / totalVotes * 100).toFixed() : 0 }}%
	.action-error(v-if="actionError", role="alert") {{ actionError }}
	.actions(v-if="isManaging && hasPermission('room:poll.manage')")
		bunt-icon-button(@click="$emit('edit')") pencil
		menu-dropdown(v-model="showModerationMenu", strategy="fixed")
			template(#button="{toggle}")
				bunt-icon-button(@click="toggle") dots-vertical
			template(#menu)
				.open-poll(v-if="['draft', 'closed'].includes(poll.state)", @click="doAction('open')") {{ $t('open for voting') }}
				.close-poll(v-if="poll.state === 'open'", @click="doAction('close')") {{ $t('close') }}
				.redraft-poll(v-if="poll.state === 'open'", @click="doAction('redraft')") {{ $t('re-draft') }}
				.pin-poll(v-if="['open', 'closed'].includes(poll.state) && !poll.is_pinned", @click="doAction('pin')") {{ $t('pin') }}
				.unpin-poll(v-if="poll.is_pinned", @click="doAction('unpin')") {{ $t('unpin') }}
				.archive-poll(v-if="poll.state !== 'archived'", @click="doAction('archive')") {{ $t('archive') }}
				.unarchive-poll(v-if="poll.state === 'archived'", @click="doAction('unarchive')") {{ $t('unarchive') }}
				.delete-poll(@click="requestDelete") {{ $t('delete') }}
	confirm-prompt(
		:open="showDeletePrompt",
		:title="$t('Delete this poll?')",
		:message="$t('This will permanently delete the poll.')",
		:confirm-label="$t('delete')",
		:cancel-label="$t('Cancel')",
		@close="showDeletePrompt = false",
		@confirm="confirmDelete"
	)
</template>
<script>
import { mapGetters } from 'vuex'
import ConfirmPrompt from 'components/ConfirmPrompt'
import MenuDropdown from 'components/MenuDropdown'
import { roomInteractionErrorMessage } from 'lib/roomInteractions'

export default {
	components: { ConfirmPrompt, MenuDropdown },
	props: {
		poll: Object
	},
	inject: {
		isManaging: {
			default: false
		}
	},
	emits: ['edit'],
	data() {
		return {
			showModerationMenu: false,
			showDeletePrompt: false,
			isVoting: false,
			actionError: null
		}
	},
	computed: {
		...mapGetters(['hasPermission']),
		ownAnswers() {
			return this.poll.answers || []
		},
		totalVotes() {
			if (!this.poll.results) return 0
			return Object.values(this.poll.results).reduce((acc, result) => acc + result, 0)
		},
		optionsWithMostVotes() {
			const sortedResults = Object.entries(this.poll.results || {}).sort((a, b) => b[1] - a[1])
			if (!sortedResults.length) return []
			const mostVotes = sortedResults[0][1]
			const optionsWithMostVotes = []
			for (const result of sortedResults) {
				if (result[1] !== mostVotes) break
				optionsWithMostVotes.push(result[0])
			}
			return optionsWithMostVotes
		}
	},
	methods: {
		optionVotes(option) {
			return this.poll.results?.[option.id] || 0
		},
		async vote(option) {
			if (this.isVoting) return
			this.isVoting = true
			this.actionError = null
			try {
				await this.$store.dispatch('poll/vote', {poll: this.poll, option})
			} catch (error) {
				console.error('Failed to vote on poll', this.poll.id, error)
				this.actionError = roomInteractionErrorMessage(error, key => this.$t(key))
			} finally {
				this.isVoting = false
			}
		},
		requestDelete() {
			this.showModerationMenu = false
			this.showDeletePrompt = true
		},
		async confirmDelete() {
			this.showDeletePrompt = false
			await this.doAction('delete')
		},
		async doAction(action) {
			this.actionError = null
			try {
				await this.$store.dispatch(`poll/${action}Poll`, this.poll)
			} catch (error) {
				console.error('Failed to moderate poll', action, this.poll.id, error)
				this.actionError = roomInteractionErrorMessage(error, key => this.$t(key))
			} finally {
				this.showModerationMenu = false
			}
		}
	}
}
</script>
<style lang="stylus">
.c-poll
	display: flex
	flex-direction: column
	padding: 16px
	border-bottom: border-separator()
	&.draft
		$clr-queued = alpha($clr-black, .05)
		background: repeating-linear-gradient(-45deg, transparent, transparent 10px, $clr-queued 10px, $clr-queued 20px, transparent 20px)
		&::after
			content: 'draft'
			display: block
			position: absolute
			right: 8px
			top: 8px
			font-size: 12px
			color: $clr-deep-orange
			font-weight: 600
	&.pinned
		border: 4px solid var(--clr-primary)
		border-bottom: none
		border-top: none
	&.archived
		background-color: $clr-grey-200
		color: $clr-disabled-text-light
		.votes, .vote-count
			color: $clr-disabled-text-light
		&::after
			content: 'archived'
			display: block
			position: absolute
			right: 8px
			top: 8px
			font-size: 12px
			color: $clr-secondary-text-light
			font-weight: 600
	.question
		font-size: 16px
		font-weight: 500
		margin-bottom: 8px
	.btn-option
		margin-top: 8px
		height: auto
		min-height: 36px
		button-style()
		.bunt-button-text
			white-space: normal
			line-height: 2
	.option
		.votes
			display: flex
			padding: 8px 0
			&::before
				content: ''
				display: block
				height: 16px
				background-color: $clr-grey-300
				width: calc(var(--votes) / var(--total-votes) * 100%)
				min-width: 4px
				margin-right: 4px
				border-radius: 8px
		&.most-votes
			.votes::before
				background-color: var(--clr-primary)
		&.own-vote .content
			font-weight: 600
		.own-vote-label
			display: inline-flex
			align-items: center
			gap: 2px
			margin-left: 8px
			font-size: 12px
			font-weight: 500
			color: $clr-green-800
	.action-error
		margin-top: 8px
		color: $clr-danger
		font-size: 13px
	.actions
		position: absolute
		top: 4px
		right: 4px
		display: none
		z-index: 102
		.bunt-icon-button
			icon-button-style()
			background-color: $clr-white
		.delete-poll
			color: $clr-danger
			&:hover
				background-color: $clr-danger
				color: $clr-primary-text-dark
	&.managing
		position: relative
		&:hover
			background-color: $clr-grey-100
			.actions
				display: flex
				gap: 4px
		&.closed
			&::after
				content: 'closed'
				display: block
				position: absolute
				right: 8px
				top: 8px
				font-size: 12px
				color: $clr-secondary-text-light
				font-weight: 600
</style>

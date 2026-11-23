<template lang="pug">
.c-questions
	.deactivated(v-if="!module.config.active")
		| {{ $t('Questions are currently disabled.') }}
	template(v-else)
		.asking-form(v-if="showAskingForm")
			bunt-input-outline-container(:label="$t('Your question')")
				template(#default="{focus, blur}")
					textarea(v-model="question", :maxlength="maxQuestionLength", :aria-invalid="submitError ? 'true' : 'false'", @focus="focus", @blur="blur")
			.submit-error(v-if="submitError", role="alert") {{ submitError }}
			.actions
				bunt-button#btn-cancel(@click="closeAskingForm") {{ $t('cancel') }}
				bunt-button#btn-submit-question(:disabled="!canSubmit", :loading="isSubmitting", @click="submitQuestion") {{ $t('Submit your question') }}
		template(v-else-if="!isManaging")
			bunt-button#btn-ask-question(v-if="hasPermission('room:question.ask')", @click="openAskingForm") {{ $t('Ask a Question') }}
			//- v-else ?
	.questions(v-if="questions && module.config.active", :class="{'can-vote': hasPermission('room:question.vote')}", v-scrollbar.y="")
		.empty-placeholder(v-if="sortedQuestions.length === 0") {{ $t('No questions yet, why not ask one?') }}
		question(v-for="question of sortedQuestions", :question="question", :key="question.id")
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import {
	MAX_QUESTION_LENGTH,
	canSubmitQuestion,
	normalizeQuestion,
	roomInteractionErrorMessage
} from 'lib/roomInteractions'
import Question from './Question'

export default {
	components: { Question },
	props: {
		module: {
			type: Object,
			required: true
		}
	},
	inject: {
		isManaging: {
			default: false
		}
	},
	emits: ['change'],
	data() {
		return {
			question: '',
			showAskingForm: false,
			isSubmitting: false,
			submitError: null,
			hasLoaded: false,
			maxQuestionLength: MAX_QUESTION_LENGTH
		}
	},
	computed: {
		...mapState('question', ['questions']),
		...mapGetters(['hasPermission']),
		canSubmit() {
			return canSubmitQuestion(this.question, this.isSubmitting)
		},
		sortedQuestions() {
			if (!this.questions) return
			let questions
			if (this.isManaging || !this.hasPermission('room:question.moderate')) {
				questions = this.questions.slice()
			} else {
				// filter questions for moderators looking at the list like a normal attendee
				questions = this.questions.filter(p => p.state === 'visible')
			}
			const weight = q => q.is_pinned * 10 + (q.state !== 'archived') + (q.state === 'mod_queue') // assume archived and mod_queue cannot be pinned
			questions.sort((a, b) =>
				weight(b) - weight(a) ||
				(this.isManaging ? b.score - a.score : 0) ||
				new Date(b.timestamp) - new Date(a.timestamp))
			return questions
		}
	},
	watch: {
		question() {
			this.submitError = null
		},
		sortedQuestions() {
			// HACK suppress firing event on `question.list`
			if (this.hasLoaded) {
				this.$emit('change')
			} else {
				this.hasLoaded = true
			}
		}
	},
	methods: {
		openAskingForm() {
			this.question = ''
			this.submitError = null
			this.showAskingForm = true
		},
		closeAskingForm() {
			this.submitError = null
			this.showAskingForm = false
		},
		async submitQuestion() {
			if (!this.canSubmit) return
			this.isSubmitting = true
			this.submitError = null
			try {
				await this.$store.dispatch('question/submitQuestion', normalizeQuestion(this.question))
				this.question = ''
				this.showAskingForm = false
			} catch (error) {
				// keep the form open with the text so the user can retry
				console.error('Failed to submit question', error)
				this.submitError = roomInteractionErrorMessage(error, key => this.$t(key))
			} finally {
				this.isSubmitting = false
			}
		}
	}
}
</script>
<style lang="stylus">
.c-questions
	display: flex
	flex-direction: column
	min-height: 0
	flex: auto
	.deactivated
		text-align: center
		margin: 32px 0
		color: $clr-secondary-text-light
	#btn-ask-question
		themed-button-primary()
		margin: 16px 0
		padding: 0 32px
		align-self: center
	.empty-placeholder
		margin-top: 16px
		padding: 0 16px
		color: $clr-secondary-text-light
		align-self: center
	.asking-form
		margin: 8px 0
		padding: 0 8px
		display: flex
		flex-direction: column
		border-bottom: border-separator()
		.bunt-input-outline-container
			textarea
				background-color: transparent
				border: none
				outline: none
				resize: vertical
				min-height: 64px
				padding: 0 8px
				font-family: $font-stack
		.submit-error
			margin-top: 8px
			padding: 0 8px
			color: $clr-danger
			font-size: 14px
		.actions
			align-self: flex-end
			margin: 16px 0
		#btn-cancel
			themed-button-secondary()
			margin: 0 16px
		#btn-submit-question
			themed-button-primary()
	.questions
		flex: auto
		min-height: 0
</style>

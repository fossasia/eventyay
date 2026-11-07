<template lang="pug">
.c-sidebar-addons
	.addons-section-header
		h2 {{ $t('Sidebar add-ons') }}
		p.subtitle {{ $t('Enhance the attendee experience on the player.') }}

	.addons-card
		.addon-row
			.addon-info
				.addon-icon
					i.mdi.mdi-message-text-outline(aria-hidden="true")
				.addon-text
					.addon-title {{ $t('Enable chat') }}
					.addon-desc {{ $t('Allow attendees to chat with each other during the live stream.') }}
			.addon-toggle
				bunt-switch(name="enable-chat", v-model="hasChat")

		.addon-nested-config(v-if="hasChat")
			.webhook-container
				button.webhook-header-btn(
					type="button"
					:aria-expanded="String(showWebhookConfig)"
					@click="toggleWebhookConfig"
				)
					.header-left
						i.mdi.mdi-api.webhook-icon(aria-hidden="true")
						span.webhook-title {{ $t('Chat Webhook Integration') }}
						span.webhook-badge(:class="webhookConfigured ? 'is-configured' : 'not-configured'")
							i.mdi(:class="webhookConfigured ? 'mdi-check-circle' : 'mdi-minus-circle-outline'" aria-hidden="true")
							| {{ webhookConfigured ? $t('Configured') : $t('Not configured') }}
					i.mdi.chevron-icon(:class="showWebhookConfig ? 'mdi-chevron-up' : 'mdi-chevron-down'" aria-hidden="true")

				.webhook-config-body(v-if="showWebhookConfig")
					p.webhook-desc {{ $t('Send chat messages and reactions to an external HTTP endpoint in real-time.') }}

					.webhook-fields-grid
						.field-group
							label.field-label
								| {{ $t('Webhook Endpoint URL') }}
								span.required-star *
							.input-wrapper
								i.mdi.mdi-link-variant.field-icon(aria-hidden="true")
								input.text-input(
									name="chat-webhook-endpoint-url"
									v-model="modules['chat.native'].config.webhook_url"
									:aria-label="$t('Webhook URL')"
									:placeholder="$t('https://example.com/webhook')"
									type="url"
									autocomplete="off"
									data-1p-ignore
									data-bwignore
									data-lpignore="true"
								)

						.field-group
							label.field-label
								| {{ $t('HMAC Signing Secret') }}
							.secret-wrapper(v-if="!isEditingSecret && modules['chat.native'].config.webhook_hmac_secret")
								.secret-masked ••••••••••••••••••••••••••••••••
								button.btn-edit-secret(type="button" @click="isEditingSecret = true")
									i.mdi.mdi-pencil(aria-hidden="true")
									| {{ $t('Edit') }}
							.input-wrapper(v-else)
								i.mdi.mdi-key-outline.field-icon(aria-hidden="true")
								input.text-input(
									name="chat-webhook-hmac-shared-key"
									v-model="modules['chat.native'].config.webhook_hmac_secret"
									:aria-label="$t('HMAC signing secret')"
									:placeholder="$t('shared-secret-key')"
									type="text"
									autocomplete="off"
									data-1p-ignore
									data-bwignore
									data-lpignore="true"
								)
							p.hint-small {{ $t('Used to sign chat webhook payloads with HMAC-SHA256.') }}

					.webhook-info-banner(v-if="modules['chat.native'].config.webhook_url")
						i.mdi.mdi-information-outline(aria-hidden="true")
						span {{ $t('Every chat message and reaction will be POSTed to this URL with an HMAC-SHA256 signature in the request headers.') }}

					.webhook-test-section(v-if="modules['chat.native'].config.webhook_url && !creating && config.id")
						button.btn-send-test(
							type="button"
							:disabled="isConfigDirty || testingWebhook"
							@click="sendTestEvent"
						)
							i.mdi(:class="testingWebhook ? 'mdi-loading mdi-spin' : 'mdi-send-outline'" aria-hidden="true")
							| {{ testingWebhook ? $t('Sending test event…') : $t('Send test event') }}
						p.hint-dirty(v-if="isConfigDirty")
							i.mdi.mdi-alert-circle-outline(aria-hidden="true")
							| {{ $t('Save changes first to test with the latest settings.') }}
						.test-result-banner(v-if="testResult" :class="testResult.success ? 'is-success' : 'is-error'")
							i.mdi(:class="testResult.success ? 'mdi-check-circle' : 'mdi-alert-circle'" aria-hidden="true")
							.result-content
								span.result-title {{ testResult.title }}
								span.result-hint(v-if="testResult.hint") {{ testResult.hint }}

		.addon-row
			.addon-info
				.addon-icon
					i.mdi.mdi-help-circle-outline(aria-hidden="true")
				.addon-text
					.addon-title {{ $t('Enable Q&A') }}
					.addon-desc {{ $t('Allow attendees to ask questions and upvote responses.') }}
			.addon-toggle
				bunt-switch(name="enable-qa", v-model="hasQuestions")

		.addon-nested-config(v-if="hasQuestions")
			.qa-options
				bunt-checkbox(v-model="modules['question'].config.active", :label="$t('Active')", name="active")
				bunt-checkbox(v-model="modules['question'].config.requires_moderation", :label="$t('Questions require moderation')", name="requires_moderation")

		.addon-row(v-if="$features.enabled('polls')")
			.addon-info
				.addon-icon
					i.mdi.mdi-chart-box-outline(aria-hidden="true")
				.addon-text
					.addon-title {{ $t('Enable Polls') }}
					.addon-desc {{ $t('Allow attendees to participate in live polls.') }}
			.addon-toggle
				bunt-switch(name="enable-polls", v-model="hasPolls")
</template>

<script>
import api from 'lib/api'
import mixin from './mixin'

export default {
	mixins: [mixin],
	data() {
		return {
			showWebhookConfig: false,
			isEditingSecret: false,
			testingWebhook: false,
			testResult: null,
			initialWebhookUrl: '',
			initialWebhookSecret: ''
		}
	},
	created() {
		this.syncInitialWebhookConfig()
	},
	watch: {
		'config.id'() {
			this.syncInitialWebhookConfig()
			this.testResult = null
		},
		'config.module_config'() {
			this.syncInitialWebhookConfig()
		},
		isConfigDirty(dirty) {
			if (dirty) {
				this.testResult = null
			}
		}
	},
	computed: {
		webhookConfigured() {
			const config = this.modules['chat.native']?.config
			return !!(config?.webhook_url && config?.webhook_hmac_secret)
		},
		isConfigDirty() {
			const config = this.modules['chat.native']?.config
			const currentUrl = config?.webhook_url || ''
			const currentSecret = config?.webhook_hmac_secret || ''
			return currentUrl !== this.initialWebhookUrl || currentSecret !== this.initialWebhookSecret
		},
		hasChat: {
			get() {
				return !!this.modules['chat.native']
			},
			set(value) {
				if (value) {
					this.addModule('chat.native', {volatile: true})
				} else {
					this.clearChatWebhookConfig()
					this.removeModule('chat.native')
					this.showWebhookConfig = false
				}
			}
		},
		hasQuestions: {
			get() {
				return !!this.modules.question
			},
			set(value) {
				if (value) {
					this.addModule('question', {
						active: true,
						requires_moderation: false
					})
				} else {
					this.removeModule('question')
				}
			}
		},
		hasPolls: {
			get() {
				return !!this.modules.poll
			},
			set(value) {
				if (value) {
					this.addModule('poll', {
						active: true
					})
				} else {
					this.removeModule('poll')
				}
			}
		}
	},
	methods: {
		syncInitialWebhookConfig() {
			const config = this.modules['chat.native']?.config
			this.initialWebhookUrl = config?.webhook_url || ''
			this.initialWebhookSecret = config?.webhook_hmac_secret || ''
		},
		toggleWebhookConfig() {
			this.showWebhookConfig = !this.showWebhookConfig
			if (!this.showWebhookConfig) {
				this.isEditingSecret = false
			}
		},
		clearChatWebhookConfig() {
			const config = this.modules['chat.native']?.config
			if (!config) return
			config.webhook_url = ''
			config.webhook_hmac_secret = ''
			this.initialWebhookUrl = ''
			this.initialWebhookSecret = ''
			this.testResult = null
		},
		async sendTestEvent() {
			const targetRoomId = this.config.id
			this.testingWebhook = true
			this.testResult = null
			try {
				const response = await api.call('room.chat.webhook.test', {
					room: targetRoomId
				})
				if (this.config.id !== targetRoomId) return
				const statusCode = response?.status_code
				if (statusCode >= 200 && statusCode <= 299) {
					this.testResult = {
						success: true,
						title: this.$t('Test event delivered successfully (HTTP {{code}}).', {code: statusCode}),
						hint: ''
					}
				} else if (statusCode === 403) {
					this.testResult = {
						success: false,
						title: this.$t('Receiver rejected the test event (HTTP 403).'),
						hint: this.$t('Check that the HMAC Signing Secret matches the receiver.')
					}
				} else if (statusCode === 404) {
					this.testResult = {
						success: false,
						title: this.$t('Receiver endpoint not found (HTTP 404).'),
						hint: this.$t('Check the Webhook URL, or verify that the receiver channel is active.')
					}
				} else {
					this.testResult = {
						success: false,
						title: this.$t('Receiver returned HTTP {{code}}.', {code: statusCode}),
						hint: ''
					}
				}
			} catch (error) {
				if (this.config.id !== targetRoomId) return
				console.error('Failed to deliver test webhook for room', targetRoomId, error)
				this.testResult = {
					success: false,
					title: this.$t('Could not deliver test event.'),
					hint: error.message || this.$t('Check that the Webhook URL is reachable.')
				}
			} finally {
				if (this.config.id === targetRoomId) {
					this.testingWebhook = false
				}
			}
		}
	}
}
</script>

<style lang="stylus">
.c-sidebar-addons
	margin-top: 24px
	display: flex
	flex-direction: column
	gap: 8px

	.addons-section-header
		margin-bottom: 8px
		h2
			font-size: 20px
			font-weight: 600
			margin: 0
			color: $clr-grey-900
		.subtitle
			font-size: 13px
			color: $clr-secondary-text-light
			margin: 2px 0 0 0

	.addons-card
		background: #ffffff
		border: 1px solid $clr-grey-200
		border-radius: 8px
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04)
		overflow: hidden

	.addon-row
		display: flex
		align-items: center
		justify-content: space-between
		padding: 16px
		gap: 16px
		&:not(:last-child)
			border-bottom: 1px solid $clr-grey-100

		.addon-info
			display: flex
			align-items: flex-start
			gap: 14px
			flex: 1

		.addon-icon
			display: flex
			align-items: center
			justify-content: center
			width: 36px
			height: 36px
			border-radius: 8px
			background: $clr-grey-100
			color: $clr-grey-700
			font-size: 20px
			flex-shrink: 0

		.addon-text
			display: flex
			flex-direction: column
			gap: 2px

		.addon-title
			font-size: 14px
			font-weight: 600
			color: $clr-grey-900

		.addon-desc
			font-size: 13px
			color: $clr-secondary-text-light
			line-height: 18px

		.addon-toggle
			flex-shrink: 0
			.bunt-switch
				margin: 0

	.addon-nested-config
		padding: 12px 16px 16px 66px
		background: $clr-grey-50
		border-bottom: 1px solid $clr-grey-100
		@media (max-width: 640px)
			padding: 12px 16px 16px 16px

	.webhook-container
		display: flex
		flex-direction: column
		gap: 10px

	.webhook-header-btn
		display: flex
		flex-direction: row
		align-items: center
		justify-content: space-between
		width: 100%
		padding: 10px 14px
		background: #ffffff
		border: 1px solid $clr-grey-300
		border-radius: 6px
		font: inherit
		cursor: pointer
		box-sizing: border-box
		line-height: normal
		transition: border-color 0.15s ease, background-color 0.15s ease
		&:hover
			border-color: $clr-grey-400
			background-color: $clr-grey-50

		.header-left
			display: inline-flex
			align-items: center
			gap: 8px
			flex: 1
			min-width: 0
			.webhook-icon
				display: inline-flex
				align-items: center
				justify-content: center
				font-size: 18px
				line-height: 1
				color: var(--clr-primary)
				flex-shrink: 0
			.webhook-title
				font-size: 13px
				font-weight: 600
				color: $clr-grey-800
				line-height: 1
			.webhook-badge
				display: inline-flex
				align-items: center
				gap: 4px
				padding: 2px 8px
				border-radius: 12px
				font-size: 11px
				font-weight: 500
				line-height: 1.4
				flex-shrink: 0
				&.is-configured
					background-color: rgba(#4CAF50, 0.12)
					color: #2E7D32
					i
						font-size: 13px
						color: #2E7D32
						line-height: 1
				&.not-configured
					background-color: $clr-grey-200
					color: $clr-grey-600
					i
						font-size: 13px
						line-height: 1

		.chevron-icon
			display: inline-flex
			align-items: center
			justify-content: center
			font-size: 20px
			line-height: 1
			color: $clr-grey-500
			flex-shrink: 0
			margin-left: 8px
			align-self: center

	.webhook-config-body
		display: flex
		flex-direction: column
		gap: 12px
		padding: 16px
		background: #ffffff
		border-radius: 6px
		border: 1px solid $clr-grey-300
		border-left: 3px solid var(--clr-primary)

		.webhook-desc
			margin: 0
			font-size: 13px
			color: $clr-secondary-text-light

		.webhook-fields-grid
			display: flex
			flex-direction: column
			gap: 12px

		.field-group
			display: flex
			flex-direction: column
			gap: 6px
			.field-label
				font-size: 13px
				font-weight: 500
				color: $clr-grey-700
				.required-star
					color: $clr-danger

		.input-wrapper
			position: relative
			display: flex
			align-items: center
			.field-icon
				position: absolute
				left: 12px
				font-size: 18px
				color: $clr-grey-500
				pointer-events: none
			.text-input
				width: 100%
				height: 40px
				padding: 0 12px 0 38px
				border: 1px solid $clr-grey-300
				border-radius: 6px
				font-size: 14px
				font-family: inherit
				background: #ffffff
				color: $clr-grey-800
				box-sizing: border-box
				outline: none
				transition: border-color 0.15s ease, box-shadow 0.15s ease
				&:focus
					border-color: var(--clr-primary)
					box-shadow: 0 0 0 2px rgba(187, 0, 17, 0.15)

		.secret-wrapper
			display: flex
			align-items: center
			justify-content: space-between
			height: 40px
			padding: 0 12px
			background: $clr-grey-50
			border: 1px solid $clr-grey-300
			border-radius: 6px
			box-sizing: border-box
			.secret-masked
				font-size: 14px
				letter-spacing: 2px
				color: $clr-grey-700
			.btn-edit-secret
				display: inline-flex
				align-items: center
				gap: 4px
				padding: 4px 10px
				font-size: 12px
				font-weight: 500
				border: 1px solid $clr-grey-300
				background: #ffffff
				border-radius: 4px
				color: $clr-grey-700
				cursor: pointer
				transition: background-color 0.15s ease
				&:hover
					background-color: $clr-grey-100
					color: $clr-grey-900

		.hint-small
			margin: 2px 0 0 0
			font-size: 12px
			color: $clr-secondary-text-light

		.webhook-info-banner
			display: flex
			align-items: flex-start
			gap: 8px
			padding: 10px 12px
			background-color: rgba(#1976D2, 0.06)
			border-radius: 6px
			font-size: 12px
			color: #1565C0
			line-height: 18px
			i
				font-size: 16px
				flex-shrink: 0
				margin-top: 1px

		.webhook-test-section
			display: flex
			flex-direction: column
			gap: 8px
			margin-top: 4px
			padding-top: 12px
			border-top: 1px solid $clr-grey-200

			.btn-send-test
				display: inline-flex
				align-items: center
				align-self: flex-start
				gap: 6px
				padding: 8px 14px
				font-size: 13px
				font-weight: 500
				color: #ffffff
				background-color: var(--clr-primary)
				border: none
				border-radius: 6px
				cursor: pointer
				transition: opacity 0.15s ease, background-color 0.15s ease
				&:hover:not(:disabled)
					opacity: 0.9
				&:disabled
					opacity: 0.5
					cursor: not-allowed

			.hint-dirty
				display: inline-flex
				align-items: center
				gap: 4px
				margin: 0
				font-size: 12px
				color: $clr-warning
				i
					font-size: 14px

			.test-result-banner
				display: flex
				align-items: flex-start
				gap: 8px
				padding: 10px 12px
				border-radius: 6px
				font-size: 12px
				line-height: 18px
				i
					font-size: 16px
					flex-shrink: 0
					margin-top: 1px
				.result-content
					display: flex
					flex-direction: column
					gap: 2px
				.result-title
					font-weight: 600
				.result-hint
					opacity: 0.9
				&.is-success
					background-color: rgba(#4CAF50, 0.12)
					color: #2E7D32
					border: 1px solid rgba(#4CAF50, 0.3)
				&.is-error
					background-color: rgba(#D32F2F, 0.08)
					color: #C62828
					border: 1px solid rgba(#D32F2F, 0.25)

	.qa-options
		display: flex
		gap: 20px
		padding-top: 4px
		flex-wrap: wrap
		.bunt-checkbox
			margin: 0
</style>

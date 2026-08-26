<template lang="pug">
.c-sidebar-addons
	h2 {{ $t('Sidebar addons') }}
	bunt-switch(name="enable-chat", v-model="hasChat", :label="$t('Enable Chat')")
	template(v-if="hasChat")
		button.webhook-toggle(
			type="button"
			:aria-expanded="String(showWebhookConfig)"
			@click="toggleWebhookConfig"
		)
			span.webhook-toggle-icon {{ showWebhookConfig ? '▼' : '►' }}
			span {{ $t('Webhook') }}
			span.webhook-configured-icon(v-if="webhookConfigured", role="img", aria-label="Webhook configured", title="Webhook configured") ✓
		.webhook-config(v-if="showWebhookConfig")
			h4 {{ $t('Chat Webhook') }}
			p.hint {{ $t('Send chat messages to an external endpoint in real-time') }}
			bunt-input-outline-container(:label="$t('Webhook URL')")
				template(#default="{focus, blur}")
					input(
						name="chat-webhook-endpoint-url"
						v-model="modules['chat.native'].config.webhook_url"
						:aria-label="$t('Webhook URL')"
						:placeholder="$t('https://example.com/webhook')"
						type="url"
						autocomplete="off"
						data-1p-ignore
						data-bwignore
						data-lpignore="true"
						@focus="focus"
						@blur="blur"
					)
			bunt-input-outline-container(v-if="!isEditingSecret && modules['chat.native'].config.webhook_hmac_secret", :label="$t('HMAC signing secret')")
				template(#default)
					.secret-value-wrapper
						span.secret-value ••••••••••••••••••••••••••••••••
						button.btn-edit-secret(type="button" @click="isEditingSecret = true") {{ $t('Edit') }}
			template(v-else)
				bunt-input-outline-container(:label="$t('HMAC signing secret')")
					template(#default="{focus, blur}")
						input(
							name="chat-webhook-hmac-shared-key"
							v-model="modules['chat.native'].config.webhook_hmac_secret"
							:aria-label="$t('HMAC signing secret')"
							:placeholder="$t('shared-secret-key')"
							type="text"
							autocomplete="off"
							data-1p-ignore
							data-bwignore
							data-lpignore="true"
							@focus="focus"
							@blur="blur"
						)
				p.hint-small {{ $t('Used to sign chat webhook payloads. This is not your Eventyay password.') }}
			p.hint-small(v-if="modules['chat.native'].config.webhook_url") {{ $t('Every chat message and reaction will be POSTed to this URL with an HMAC-SHA256 signature') }}
	bunt-switch(name="enable-qa", v-model="hasQuestions", :label="$t('Enable Q&A')")
	template(v-if="hasQuestions")
		bunt-checkbox(v-model="modules['question'].config.active", :label="$t('Active')", name="active")
		bunt-checkbox(v-model="modules['question'].config.requires_moderation", :label="$t('Questions require moderation')", name="requires_moderation")
	bunt-switch(v-if="$features.enabled('polls')", name="enable-polls", v-model="hasPolls", :label="$t('Enable Polls')")
</template>
<script>
import mixin from './mixin'

export default {
	mixins: [mixin],
	data() {
		return {
			showWebhookConfig: false,
			isEditingSecret: false
		}
	},
	created() {
		// Section starts collapsed by default, ignoring configured state
	},
	computed: {
		webhookConfigured() {
			const config = this.modules['chat.native']?.config
			return !!(config?.webhook_url && config?.webhook_hmac_secret)
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
		}
	}
}
</script>
<style lang="stylus">
.c-sidebar-addons
	.bunt-checkbox
		margin-bottom: 8px
	.webhook-toggle
		display: flex
		align-items: center
		gap: 6px
		margin: 4px 0 8px 0
		padding: 0
		border: 0
		background: transparent
		color: #333
		font: inherit
		font-size: 14px
		cursor: pointer
		.webhook-toggle-icon
			display: inline-block
			width: 1em
			font-size: 12px
			line-height: 1
	.webhook-config
		margin: 0 0 16px 0
		padding: 12px 16px
		background: rgba(0, 0, 0, 0.03)
		border-radius: 6px
		border-left: 3px solid #2196F3
		h4
			margin: 0 0 4px 0
			font-size: 14px
			color: #333
		.hint
			margin: 0 0 12px 0
			font-size: 12px
			color: #666
		.hint-small
			margin: 4px 0 0 0
			font-size: 11px
			color: #888
			font-style: italic
		.bunt-input-outline-container
			height: 56px
			margin-bottom: 8px
			input
				box-sizing: border-box
				height: 37px
				width: 100%
				border: 0
				outline: 0
				padding: 8px 8px 8px 12px
				font-size: 16px
				font-weight: 400
				background: transparent
			.secret-value-wrapper
				display: flex
				align-items: center
				justify-content: space-between
				width: 100%
				height: 37px
				padding: 0 8px 0 12px
				box-sizing: border-box
				.secret-value
					font-size: 16px
					letter-spacing: 2px
					color: #333
					transform: translateY(2px)
				.btn-edit-secret
					padding: 4px 12px
					font-size: 12px
					border: 1px solid #ccc
					background: #f5f5f5
					border-radius: 4px
					cursor: pointer
					&:hover
						background: #ebebeb
	.webhook-configured-icon
		display: inline-flex
		align-items: center
		justify-content: center
		width: 16px
		height: 16px
		background-color: #4CAF50
		color: white
		border-radius: 50%
		font-size: 10px
		font-weight: bold
		margin-left: 8px
</style>

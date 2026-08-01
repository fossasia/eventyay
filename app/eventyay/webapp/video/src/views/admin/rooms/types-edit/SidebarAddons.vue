<template lang="pug">
.c-sidebar-addons
	h2 Sidebar addons
	bunt-switch(name="enable-chat", v-model="hasChat", label="Enable Chat")
	template(v-if="hasChat")
		button.webhook-toggle(
			type="button"
			:aria-expanded="String(showWebhookConfig)"
			@click="showWebhookConfig = !showWebhookConfig"
		)
			span.webhook-toggle-icon {{ showWebhookConfig ? '▼' : '►' }}
			span Webhook
		.webhook-config(v-if="showWebhookConfig")
			h4 Chat Webhook
			p.hint Send chat messages to an external endpoint in real-time
			bunt-input-outline-container(label="Webhook URL")
				template(#default="{focus, blur}")
					input(
						name="chat-webhook-endpoint-url"
						v-model="modules['chat.native'].config.webhook_url"
						aria-label="Webhook URL"
						placeholder="https://example.com/webhook"
						type="url"
						autocomplete="off"
						data-1p-ignore
						data-bwignore
						data-lpignore="true"
						@focus="focus"
						@blur="blur"
					)
			bunt-input-outline-container(label="HMAC Secret")
				template(#default="{focus, blur}")
					input(
						name="chat-webhook-hmac-shared-key"
						v-model="modules['chat.native'].config.webhook_hmac_secret"
						aria-label="HMAC Secret"
						placeholder="shared-secret-key"
						type="password"
						autocomplete="new-password"
						data-1p-ignore
						data-bwignore
						data-lpignore="true"
						@focus="focus"
						@blur="blur"
					)
			p.hint-small(v-if="modules['chat.native'].config.webhook_url") Every chat message and reaction will be POSTed to this URL with an HMAC-SHA256 signature
	bunt-switch(name="enable-qa", v-model="hasQuestions", label="Enable Q&A")
	template(v-if="hasQuestions")
		bunt-checkbox(v-model="modules['question'].config.active", label="Active", name="active")
		bunt-checkbox(v-model="modules['question'].config.requires_moderation", label="Questions require moderation", name="requires_moderation")
	bunt-switch(v-if="$features.enabled('polls')", name="enable-polls", v-model="hasPolls", label="Enable Polls")
</template>
<script>
import mixin from './mixin'

export default {
	mixins: [mixin],
	data() {
		return {
			showWebhookConfig: false
		}
	},
	created() {
		const config = this.modules['chat.native']?.config
		if (config?.webhook_url || config?.webhook_hmac_secret) {
			this.showWebhookConfig = true
		}
	},
	computed: {
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
</style>

<template lang="pug">
.c-sidebar-addons
	h2 Sidebar addons
	bunt-switch(name="enable-chat", v-model="hasChat", label="Enable Chat")
	template(v-if="hasChat")
		.webhook-config
			h4 Chat Webhook (optional)
			p.hint Send chat messages to an external endpoint in real-time
			bunt-input(name="webhook-url", v-model="modules['chat.native'].config.webhook_url", label="Webhook URL", placeholder="https://example.com/webhook")
			bunt-input(name="webhook-secret", v-model="modules['chat.native'].config.webhook_hmac_secret", label="HMAC Secret", placeholder="shared-secret-key", type="password")
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
					this.removeModule('chat.native')
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
	}
}
</script>
<style lang="stylus">
.c-sidebar-addons
	.bunt-checkbox
		margin-bottom: 8px
	.webhook-config
		margin: 8px 0 16px 0
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
		.bunt-input
			margin-bottom: 8px
</style>

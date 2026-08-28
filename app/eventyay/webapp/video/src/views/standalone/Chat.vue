<template lang="pug">
.v-presentation-chat
	.chat-stage-header(v-if="room")
		.live-indicator
			span.pulse-dot
		h2.room-name(v-html="$emojify(room.name)")
	.chat-messages-container(ref="messagesContainer", v-if="filteredTimeline.length > 0")
		.message-wrapper(v-for="(message, index) of filteredTimeline", :key="message.event_id || index")
			chat-message(:message="message", :nextMessage="filteredTimeline[index + 1]", mode="compact", :readonly="true")
	.chat-empty-state(v-else)
		i.mdi.mdi-forum-outline
		span.empty-title {{ $t('Welcome to Live Chat!') }}
		span.empty-subtitle {{ $t('Messages sent in this room will appear here in real time.') }}
</template>

<script>
import { mapState } from 'vuex'
import ChatMessage from 'components/ChatMessage'

export default {
	components: { ChatMessage },
	props: {
		room: Object
	},
	computed: {
		...mapState('chat', ['channel', 'members', 'usersLookup', 'timeline', 'fetchingMessages']),
		module() {
			return this.room?.modules?.find(module => module.type === 'chat.native')
		},
		filteredTimeline() {
			if (!this.timeline) return []
			return this.timeline.filter(message => message.event_type !== 'channel.member' && message.content?.type !== 'deleted' && !message.replaces)
		}
	},
	watch: {
		filteredTimeline() {
			this.scrollToBottom()
		},
		module: {
			handler(module) {
				if (module) {
					this.$store.dispatch('chat/subscribe', {channel: module.channel_id, config: module.config})
				}
			},
			immediate: true
		}
	},
	mounted() {
		this.scrollToBottom()
	},
	methods: {
		scrollToBottom() {
			this.$nextTick(() => {
				const container = this.$refs.messagesContainer
				if (container) {
					container.scrollTop = container.scrollHeight
				}
			})
		}
	}
}
</script>

<style lang="stylus">
.v-presentation-chat
	display: flex
	flex-direction: column
	width: 100%
	max-width: none
	height: 100%
	margin: 0
	padding: 16px 20px
	box-sizing: border-box
	background: #ffffff
	color: #1e2327
	overflow: hidden

	.chat-stage-header
		display: none

	.chat-messages-container
		display: flex
		flex-direction: column
		gap: 8px
		flex: 1
		min-height: 0
		overflow-y: auto
		padding-right: 4px
		scroll-behavior: smooth

		&::-webkit-scrollbar
			width: 5px
		&::-webkit-scrollbar-track
			background: transparent
		&::-webkit-scrollbar-thumb
			background: rgba(0, 0, 0, 0.15)
			border-radius: 4px

		.message-wrapper
			width: 100%

	.c-chat-message
		width: 100%
		padding: 8px 0
		border-bottom: 1px solid #f3f4f6
		background: transparent

		.timestamp, .preview-card
			display: none

	.chat-empty-state
		display: flex
		flex-direction: column
		align-items: center
		justify-content: center
		flex: 1
		text-align: center
		padding: 40px 20px
		color: #4b5563

		i.mdi
			font-size: 48px
			color: var(--clr-primary, #2185d0)
			margin-bottom: 12px

		.empty-title
			font-size: 18px
			font-weight: 700
			margin-bottom: 6px
			color: #1e2327

		.empty-subtitle
			font-size: 14px
			max-width: 320px

@keyframes chat-pulse
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
	.v-presentation-chat
		max-width: 100%
		padding: 12px
</style>

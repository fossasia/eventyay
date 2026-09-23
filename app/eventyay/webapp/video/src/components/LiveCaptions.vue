<template lang="pug">
.c-live-captions(:class="{'mode-docked': docked}", :style="{ '--caption-font-size': fontSizePx + 'px' }")
	.caption-log(ref="log")
		transition-group.caption-lines(name="caption-line", tag="div")
			.caption-line(v-for="line in lines", :key="line.id") {{ line.text }}
		.caption-placeholder(v-if="docked && lines.length === 0")
			span.listening-dot
			span {{ $t('Listening for live speech... Subtitles will stream here in real-time.') }}
</template>

<script>
import { logOperational } from 'lib/operationalLog'

export default {
	name: 'LiveCaptions',
	props: {
		wsUrl: {
			type: String,
			default: null
		},
		textSize: {
			type: [Number, String],
			default: 13
		},
		docked: {
			type: Boolean,
			default: false
		}
	},
	data() {
		return {
			lines: [],
			liveId: null,
			nextId: 1,
			ws: null,
			reconnectAttempts: 0,
			maxReconnectAttempts: 5,
			reconnectTimeout: null
		}
	},
	computed: {
		fontSizePx() {
			const presets = { auto: 13, small: 12, normal: 14, large: 16 }
			if (typeof this.textSize === 'string' && presets[this.textSize] != null) {
				return presets[this.textSize]
			}
			const n = Number(this.textSize)
			if (!Number.isFinite(n)) return 13
			return Math.min(18, Math.max(12, n))
		}
	},
	watch: {
		wsUrl(newUrl) {
			this.teardown()
			this.lines = []
			this.liveId = null
			this.reconnectAttempts = 0
			if (newUrl) {
				this.connect()
			}
		}
	},
	mounted() {
		if (this.wsUrl) {
			this.connect()
		}
	},
	beforeUnmount() {
		this.teardown()
	},
	methods: {
		async connect() {
			this.clearReconnectTimer()
			if (!this.wsUrl) return

			this.ws = new WebSocket(this.wsUrl)
			this.ws.onmessage = this.onMessage
			this.ws.onopen = () => {
				this.reconnectAttempts = 0
			}
			this.ws.onclose = () => {
				this.ws = null
				// Skip reconnect after teardown / language switch (wsUrl cleared).
				if (this.wsUrl) {
					this.attemptReconnect()
				}
			}
			this.ws.onerror = () => {
				logOperational({action: 'captions.ws', outcome: 'failure', backend: 'captions', error_code: 'ws_error'})
				this.ws?.close()
			}
		},
		async teardown() {
			this.clearReconnectTimer()
			if (this.ws) {
				const ws = this.ws
				this.ws = null
				ws.onclose = null
				ws.onerror = null
				ws.onmessage = null
				ws.close()
			}
		},
		clearReconnectTimer() {
			if (this.reconnectTimeout) {
				clearTimeout(this.reconnectTimeout)
				this.reconnectTimeout = null
			}
		},
		attemptReconnect() {
			if (this.reconnectAttempts >= this.maxReconnectAttempts) {
				this.lines = [{ id: this.nextId++, text: this.$t('Captions disconnected') }]
				return
			}
			const backoffMs = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000)
			this.reconnectAttempts++
			this.reconnectTimeout = setTimeout(() => {
				this.connect()
			}, backoffMs)
		},
		async onMessage(event) {
			try {
				if (event.data instanceof Blob) {
					return
				}

				const data = JSON.parse(event.data)
				if (data.type !== 'caption' && data.type !== 'translated_caption') {
					return
				}
				const text = typeof data.text === 'string' ? data.text.trim() : ''
				if (data.status === 'clear') {
					// Keep committed finals; Voxbento clears between utterances.
					this.dropLiveLine()
					return
				}
				if (!text) return
				if (data.status === 'partial') {
					this.upsertLiveLine(text)
				} else {
					this.commitLine(text)
				}
				const maxLines = this.docked ? 24 : 2
				if (this.lines.length > maxLines) {
					const removed = this.lines.slice(0, this.lines.length - maxLines)
					if (this.liveId != null && removed.some(item => item.id === this.liveId)) {
						this.liveId = null
					}
					this.lines = this.lines.slice(-maxLines)
				}
				this.$nextTick(() => {
					if (this.$refs.log) {
						this.$refs.log.scrollTop = this.$refs.log.scrollHeight
					}
				})
			} catch (e) {
				console.error('Failed to parse caption message', e)
			}
		},
		upsertLiveLine(text) {
			const line = this.liveLine()
			if (line) {
				line.text = text
				return
			}
			this.liveId = this.nextId++
			this.lines.push({ id: this.liveId, text })
		},
		commitLine(text) {
			const line = this.liveLine()
			if (line) {
				line.text = text
			} else {
				this.lines.push({ id: this.nextId++, text })
			}
			this.liveId = null
		},
		dropLiveLine() {
			if (this.liveId == null) return
			this.lines = this.lines.filter(item => item.id !== this.liveId)
			this.liveId = null
		},
		liveLine() {
			if (this.liveId == null) return null
			return this.lines.find(item => item.id === this.liveId) || null
		}
	}
}
</script>

<style lang="stylus">
.c-live-captions
	position: absolute
	bottom: 20px
	left: 50%
	transform: translateX(-50%)
	width: calc(100% - 32px)
	max-width: 800px
	pointer-events: none
	z-index: 40
	display: flex
	flex-direction: column
	align-items: center
	text-align: center
	box-sizing: border-box

	.caption-log
		max-height: calc(3em + 12px)
		overflow-y: hidden
		text-align: center
		width: 100%

	.caption-line
		color: #ffffff
		font-weight: 600
		font-size: var(--caption-font-size, 13px)
		line-height: 1.35
		background: rgba(0, 0, 0, 0.82)
		padding: 4px 12px
		border-radius: 4px
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.6)
		display: inline-block
		margin-bottom: 4px
		max-width: 100%
		overflow-wrap: anywhere
		text-shadow: 0 1px 2px rgba(0, 0, 0, 0.8)
		letter-spacing: 0.2px

	.caption-line-enter-active
		transition: opacity 0.22s ease, transform 0.22s ease
	.caption-line-enter-from
		opacity: 0
		transform: translateY(6px)
	@media (prefers-reduced-motion: reduce)
		.caption-line-enter-active
			transition: none

	&.mode-docked
		position: relative
		bottom: auto
		left: auto
		transform: none
		width: 100%
		max-width: 100%
		height: 100%
		min-height: 0
		pointer-events: auto
		z-index: auto
		align-items: stretch
		text-align: left

		.caption-log
			flex: 1
			min-height: 0
			max-height: 100%
			overflow-y: auto
			text-align: left
			width: 100%
			padding: 0
			display: flex
			flex-direction: column
			gap: 2px

		.caption-lines
			display: flex
			flex-direction: column
			gap: 2px

		.caption-line-move
			transition: transform 0.2s ease
		@media (prefers-reduced-motion: reduce)
			.caption-line-move
				transition: none

		.caption-line
			display: block
			box-shadow: none
			text-shadow: none
			color: var(--clr-text-primary, #1e293b)
			font-weight: 500
			font-size: var(--caption-font-size, 13px)
			line-height: 1.25
			padding: 2px 8px
			border-radius: 4px
			background-color: var(--clr-grey-50, #f8f9fa)
			border-left: 3px solid var(--clr-primary, #2185d0)
			margin-bottom: 0

		.caption-placeholder
			display: flex
			align-items: center
			gap: 8px
			padding: 4px 8px
			color: var(--clr-text-secondary, #64748b)
			font-size: 13px
			font-style: italic
			line-height: 1.25

			.listening-dot
				width: 8px
				height: 8px
				border-radius: 50%
				background-color: var(--clr-primary, #2185d0)
				animation: pulse-dot 1.5s infinite
				flex: none
			@media (prefers-reduced-motion: reduce)
				.listening-dot
					animation: none

@keyframes pulse-dot
	0%
		opacity: 0.3
		transform: scale(0.8)
	50%
		opacity: 1
		transform: scale(1.3)
	100%
		opacity: 0.3
		transform: scale(0.8)
</style>

<template lang="pug">
.c-iframe-call-frame(:class="[`size-${size}`, `provider-${providerName}`]")
	.loading-state(v-if="loading && !error")
		bunt-progress-circular(size="huge", :page="true")
		span.loading-text {{ $t('Joining meeting…') }}
	.error-state(v-else-if="error")
		.mdi.mdi-alert-circle-outline.state-icon--error
		p.error-title {{ $t('Could not join meeting room.') }}
		p.error-detail(v-if="errorMsg") {{ errorMsg }}
		bunt-button.retry-btn(@click="connect") {{ $t('Retry') }}
	.iframe-viewport(v-show="!loading && !error && joinUrl")
		iframe.call-iframe(
			ref="iframeEl",
			:key="joinKey",
			:src="joinUrl",
			allow="camera *; microphone *; fullscreen *; display-capture *; autoplay *; clipboard-write *; clipboard-read *",
			allowfullscreen="true",
			allowusermedia="true",
			@load="onIframeLoaded",
			@error="onIframeError"
		)
</template>

<script>
import api from 'lib/api'
import { logOperational } from 'lib/operationalLog'

export default {
	name: 'IframeCallFrame',
	props: {
		room: {
			type: Object,
			required: true
		},
		module: {
			type: Object,
			required: true
		},
		provider: {
			type: String,
			default: ''
		},
		size: {
			type: String,
			default: 'normal'
		}
	},
	emits: ['connected', 'hangup', 'error'],
	data() {
		return {
			joinUrl: null,
			joinKey: 0,
			loading: true,
			error: null,
			errorMsg: null,
		}
	},
	computed: {
		providerName() {
			if (this.provider) return this.provider
			if (this.module?.type === 'call.zoom') return 'zoom'
			if (this.module?.type === 'call.loungemesh') return 'loungemesh'
			return 'call'
		}
	},
	async created() {
		await this.connect()
	},
	mounted() {
		this.messageHandler = (event) => {
			if (!this.$refs.iframeEl || event.source !== this.$refs.iframeEl.contentWindow) return
			if (this.joinUrl) {
				try {
					const expectedOrigin = new URL(this.joinUrl, window.location.href).origin
					if (expectedOrigin !== 'null' && event.origin !== expectedOrigin) return
				} catch (e) {}
			}
			const data = event.data || {}
			if (
				data.type === 'hangup' ||
				data === 'hangup' ||
				data.event === 'loungemesh:leave' ||
				data.action === 'loungemesh:leave' ||
				(data.source === 'loungemesh' && (data.action === 'leave' || data.type === 'hangup' || data.type === 'leave'))
			) {
				this.$emit('hangup')
			}
		}
		window.addEventListener('message', this.messageHandler)
	},
	beforeUnmount() {
		if (this.messageHandler) {
			window.removeEventListener('message', this.messageHandler)
		}
		this.cleanupMedia()
	},
	methods: {
		async connect() {
			this.loading = true
			this.error = null
			this.errorMsg = null
			this.joinUrl = null
			this.joinKey++
			const provider = this.providerName
			const rpcMethod = `${provider}.room_url`
			try {
				const response = await api.call(rpcMethod, { room: this.room.id })
				if (response?.url) {
					this.joinUrl = response.url
					this.$emit('connected')
					logOperational({ action: `${provider}.join`, outcome: 'success', backend: provider })
				} else {
					throw new Error('No join URL returned')
				}
			} catch (err) {
				this.loading = false
				this.error = err
				this.errorMsg = err?.message || err?.code || this.$t('Meeting server is currently unavailable.')
				logOperational({
					action: `${provider}.join`,
					outcome: 'failure',
					backend: provider,
					error_code: err?.code || 'join_failed'
				})
				this.$emit('error', err)
			}
		},
		onIframeLoaded() {
			this.loading = false
			logOperational({ action: 'iframe.load', outcome: 'success', backend: this.providerName })
		},
		onIframeError() {
			this.loading = false
			this.error = true
			this.errorMsg = this.$t('Meeting server is currently unavailable.')
			logOperational({ action: 'iframe.error', outcome: 'failure', backend: this.providerName, error_code: 'iframe_error' })
		},
		cleanupMedia() {
			if (this.$refs.iframeEl) {
				try {
					this.$refs.iframeEl.src = 'about:blank'
				} catch (e) {}
			}
			this.joinUrl = null
		},
		hangup() {
			this.cleanupMedia()
			this.$emit('hangup')
		}
	}
}
</script>

<style lang="stylus">
.c-iframe-call-frame
	flex: auto
	height: 100%
	width: 100%
	display: flex
	flex-direction: column
	position: relative
	overflow: hidden
	background-color: #1e293b

	.loading-state, .error-state
		flex: auto
		display: flex
		flex-direction: column
		align-items: center
		justify-content: center
		color: #f1f5f9
		gap: 16px
		padding: 24px

		.loading-text
			font-size: 16px
			color: #94a3b8
			font-weight: 500

		.state-icon--error
			font-size: 48px
			color: #ef4444

		.error-title
			font-size: 18px
			font-weight: 600
			color: #f8fafc
			margin: 0

		.error-detail
			font-size: 14px
			color: #94a3b8
			margin: 0
			text-align: center
			max-width: 480px

		.retry-btn
			background-color: #2185d0
			color: #ffffff
			border-radius: 6px

	.iframe-viewport
		flex: auto
		width: 100%
		height: 100%
		position: relative
		overflow: hidden

		.call-iframe
			border: none
			width: 100%
			height: 100%
			display: block

	&.size-tiny
		.loading-state, .error-state
			display: none
</style>

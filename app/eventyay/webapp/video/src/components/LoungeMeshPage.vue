<template lang="pug">
.c-loungemesh-page
	bunt-progress-circular(size="huge", :page="true", v-if="loading")
	.error(v-if="error") {{ error }}
	iframe-blocker(
		v-if="url",
		:src="url",
		allow="camera *; autoplay *; microphone *; fullscreen *; display-capture *",
		allowfullscreen,
		allowusermedia,
		@load="loaded"
	)
</template>
<script>
import api from 'lib/api'
import IframeBlocker from './IframeBlocker'

export default {
	components: { IframeBlocker },
	props: {
		module: {
			type: Object,
			required: true
		},
		room: {
			type: Object,
			required: true
		}
	},
	data() {
		return {
			loading: true,
			url: '',
			error: null,
		}
	},
	async mounted() {
		window.addEventListener('message', this.onMessage)
		await this.loadJoinUrl()
	},
	beforeUnmount() {
		window.removeEventListener('message', this.onMessage)
	},
	methods: {
		loaded() {
			this.loading = false
		},
		async loadJoinUrl({refresh = false} = {}) {
			this.loading = !refresh
			this.error = null
			try {
				const session = await api.call('loungemesh.room_url', { room: this.room.id })
				if (refresh && session.jwt && this.postToken(session.jwt)) {
					this.loading = false
					return
				}
				this.url = session.url
			} catch (error) {
				console.error('Failed to load LoungeMesh join URL', error)
				this.error = error?.message || error?.code || 'Could not open LoungeMesh.'
				this.loading = false
			}
		},
		allowedOrigin() {
			const candidates = [this.url, this.module?.config?.url, window.eventyay?.loungemeshUrl]
			for (const candidate of candidates) {
				if (!candidate) continue
				try {
					return new URL(candidate).origin
				} catch {
					continue
				}
			}
			return ''
		},
		postToken(jwt) {
			const iframe = this.$el?.querySelector('iframe')
			const origin = this.allowedOrigin()
			if (!iframe?.contentWindow || !origin || !jwt) return false
			iframe.contentWindow.postMessage(
				{ source: 'eventyay', type: 'loungemesh:new_token', jwt },
				origin
			)
			return true
		},
		onMessage(event) {
			const expected = this.allowedOrigin()
			if (expected && event.origin !== expected) return
			if (!event.data || event.data.source !== 'loungemesh') return
			if (event.data.type === 'token_expired') {
				this.loadJoinUrl({ refresh: true })
			}
		}
	}
}
</script>
<style lang="stylus">
.c-loungemesh-page
	flex: auto
	height: auto
	display: flex
	flex-direction: column
	position: relative
	.error
		padding: 24px
		color: $clr-danger
</style>

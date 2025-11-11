<template lang="pug">
prompt.c-qrcode-prompt(@close="$emit('close')")
	.content
		bunt-icon-button#btn-close(@click="$emit('close')") close
		h1 {{ $t('QRCodePrompt:title') }}
		bunt-progress-circular(v-if="!url")
		template(v-else)
			a.download(:href="downloadUrl", :download="`anonymous-link-room-${room.name}.svg`")
				.svg(v-html="qrcode")
				| {{ $t('QRCodePrompt:download-svg') }}
			CopyableText.url(:text="shortUrl")
</template>
<script>
import QRCode from 'qrcode'
import api from 'lib/api'
import CopyableText from 'components/CopyableText'
import Prompt from 'components/Prompt'

export default {
	components: { CopyableText, Prompt },
	props: {
		room: Object
	},
	emits: ['close'],
	data() {
		return {
			url: null,
			qrcode: null
		}
	},
	computed: {
		shortUrl() {
			return this.url ? this.url.replace(/^https?:\/\//, '') : ''
		},
		downloadUrl() {
			return this.qrcode ? `data:image/svg+xml;base64,${btoa(this.qrcode)}` : ''
		}
	},
	async created() {
		if (!this.room || !this.room.id) {
			console.error('QRCodePrompt: room or room.id is undefined')
			this.$emit('close')
			return
		}
		try {
			const { url } = await api.call('room.invite.anonymous.link', {room: this.room.id})
			this.url = url
			this.qrcode = await QRCode.toString(this.url, {type: 'svg', margin: 1})
		} catch (error) {
			console.error('Failed to generate QR code:', error)
			this.$emit('close')
		}
	}
}
</script>
<style lang="stylus">
.c-qrcode-prompt
	.prompt-wrapper
		width: 640px
		max-width: 90vw
	.content
		display: flex
		flex-direction: column
		padding: 32px
		position: relative
		align-items: center
		h1
			margin: 0
			text-align: center
		.bunt-progress-circular
			margin: auto
		a
			text-align: center
		svg
			width: 520px
			max-width: 100%
			height: auto
		.url
			margin: 16px
			font-size: 24px
	@media (max-width: 768px)
		.prompt-wrapper
			width: 95vw
			max-width: 400px
		.content
			padding: 16px
			h1
				font-size: 20px
			svg
				width: 100%
				max-width: 280px
			.url
				margin: 12px
				font-size: 16px
				word-break: break-all
</style>
